"""Save Ghostbusters' pictures (PNG) and sounds (WAV), read from your own copy of the tape.

    python tools/extract_assets.py "game/Ghostbusters (1984)(Activision)(48K-128K).tap"

The tape is loaded in SkoolKit's simulator (its own loader runs), then:
- the sprites are decoded here in Python, from the data in memory;
- the city map, the title logo, the buildings (Zuul too), the cars and the ending are drawn by calling the game's own routines,
  because they are packed in a format that only the game's code unpacks;
- the text the port prints is copied out of memory (text.json), and the ROM's font saved (font.bin);
- the speech and the title song are recorded from the speaker while the game's own
  routines play them.
See notes/03-assets.md for where each one lives and how it is stored.
"""
import argparse
import hashlib
import json
import os
import tempfile

from PIL import Image

from zxkit import sim
from zxkit.play import Player
from zxkit.screen import SCREEN_SIZE, colour, save_rom_font, screen_image

# SHA-1 of $5E00-$D8FF once loaded: the 1984 Activision tape (notes/01-choosing-a-copy.md).
# The re-releases have their code at other addresses, so the addresses below would be wrong.
GAME_SHA1 = "e3912ad93802f63cb9db37dfc4c3e0aa59042703"
GAME_RANGE = (0x5E00, 0xD900)

BACK_BUFFER = 0xE000          # the game draws here, laid out like the screen, then copies it to $4000

SPRITES_START, SPRITES_END = 0x7151, 0x7767
STOMPED = 0x672D              # the stomped building picture, 4 bytes by 32 rows ($929D)
LOGO_SPRITE = 0x7103          # stands alone, before the others
SPRITE_NAMES = {
    0x7103: "logo", 0x7151: "ghost_city", 0x7195: "keyhole", 0x71B9: "key", 0x71D5: "bait_city",
    0x71F9: "marshmallow_1", 0x723D: "marshmallow_2", 0x7281: "marshmallow_3", 0x72C5: "marshmallow_4",
    0x7309: "dot", 0x7311: "man_standing", 0x7365: "man_walking", 0x73B9: "man_slimed",
    0x73FF: "ghost", 0x7443: "trap_shut", 0x7467: "trap_open", 0x74A7: "trap_stream_top",
    0x7517: "trap_stream", 0x754B: "beam_up", 0x756F: "beam_down", 0x7593: "pk_energy_detector",
    0x75BF: "image_intensifier", 0x75E7: "marshmallow_sensor", 0x762F: "trap_shop", 0x7663: "ghost_bait",
    0x76AB: "laser_confinement", 0x76D7: "ghost_vacuum", 0x7717: "forklift", 0x7757: "forklift_fork",
}


# name: (picture list for $A741, colour lists for $A32A, applied in turn)
PICTURES = {
    "title_logo": (0xB2E9, [0xB2AC]),
    "haunted_building": (0xA3C2, [0xA3CF]),
    "building": (0xA3B8, [0xA367]),
    "zuul": (0xA3C2, [0xA3CF, 0xA69A]),     # the haunted building, recoloured by the Zuul scene ($A426)
}
ENDING = (0xA4F7, 0xA565)     # the ending's words: from after the $5000 reward to before its speech
CARS = 0x99DC                 # 4 picture lists (2 bytes each), then 4 colours at +8 (2 bytes apart)

# digitised speech played by $CAC0 (HL = the sample: 2-byte length, then 1 bit per speaker step)
SPEECH = {"speech_ghostbusters": 0xCB24, "speech_laugh": 0xCF8D, "speech_he_slimed_me": 0xD555}
SONG = 0xAEE7                 # the title song, with its words on screen
SONG_LINES = 0xB9EA           # its lines of words

# text the port prints: name -> (address, length)
TEXT = {
    "copyright": (0x7960, 32),      # the city's bottom line when no message is scrolling ($942B)
    "status": (0x7767, 0x42),       # SPACE in the city ($932D); the port puts the numbers in
    "no_traps": (0x77A9, 0x27), "alert": (0x77D0, 0x15), "attack": (0x77E5, 0x5A),
    "few_men": (0x789B, 0x36), "no_power": (0x78D1, 0x25), "start": (0x78F6, 0x1F),
    "mayor": (0x7915, 0x3C), "no_bait": (0x7951, 0x0F), "go_to_zuul": (0x8078, 0x43),
    "pk_label": (0x949A, 0x11),     # row 22's label, printed again by $931C
    "crossed": (0x783F, 0x5C),      # crossed streams at a building ($9CA9)
    "ghq_sign": (0x7983, 0x0C),     # GHOSTBUSTERS over GHQ's door ($A038)
    # the ending's text screen ($A4EB-$A562), with $8B92's control bytes (position, clear screen)
    "end_lost": (0x814E, 0x66), "end_won": (0x81B5, 0x59), "end_credit": (0x820F, 0x56),
    "end_account": (0x8266, 0x1D), "end_write": (0x8284, 0x2B),
    "foreclosed": (0x80BB, 0x92),   # the bank's game over ($916E)
    # the start ($8300-$87F6, notes/10-the-start.md), also with control bytes
    "menu": (0x7F2B, 144), "keys": (0x7FBC, 187), "name": (0x7980, 195), "account_q": (0x7A44, 24),
    "account_number_q": (0x7AE9, 30), "invalid": (0x7B08, 24), "welcome": (0x7A5D, 139),
    "cars": (0x7B21, 141), "car_prompt": (0x7BAF, 124), "car_1": (0x7E1C, 61), "car_2": (0x7E5A, 65),
    "car_3": (0x7E9C, 69), "car_4": (0x7EE2, 72), "forklift": (0x7CB8, 76),
    "page_1": (0x7C2C, 139), "page_2": (0x7D05, 139), "page_3": (0x7D91, 138),
}
TITLE = (0xB2E9, 0xB2AC)      # the title logo's pictures and colours ($8371)
# the two street scenes' pictures ($9AAB), saved without colours: the port colours them
STREET_PICTURES = {"street_shop": 0xA3B8, "street_brick": 0xA3C2}


def sprite_images(ram, addr):
    """Draw one sprite and its mask.

    ram: 48K of memory (index 0 is $4000). addr: the sprite's header.
    Returns (picture, mask, address after the sprite). The picture has its ink pixels in the
    header's ink colour and the rest see-through; the game often colours sprites from the
    screen instead, so the port may recolour them. The mask is white where the sprite hides
    the background (the game clears those pixels before drawing the picture).
    """
    g = lambda a: ram[a - 0x4000]
    width, height, attr = g(addr) - 1, g(addr + 1), g(addr + 2)
    ink = colour(attr & 7, bool(attr & 0x40)) + (255,)
    picture = addr + 4
    mask = picture + width * height
    pic_img = Image.new("RGBA", (width * 8, height), (0, 0, 0, 0))
    mask_img = Image.new("RGBA", (width * 8, height), (0, 0, 0, 0))
    for y in range(height):
        for x in range(width * 8):
            i, bit = y * width + x // 8, 0x80 >> (x % 8)
            if g(picture + i) & bit:
                pic_img.putpixel((x, y), ink)
            if not g(mask + i) & bit:
                mask_img.putpixel((x, y), (255, 255, 255, 255))
    return pic_img, mask_img, mask + width * height


def city_map(z80):
    """Have the game draw the city map ($9294): the packed screen, the buildings, the ZUUL and
    GHQ labels and the text line at the bottom.

    z80: snapshot of the started game. Returns 6912 bytes of screen memory.
    """
    p = Player(z80)
    p.call(0x9294)
    return bytes(p.sim.memory[BACK_BUFFER:BACK_BUFFER + SCREEN_SIZE])


def drive_road(z80, car):
    """Have the game set up the drive's road with a car on it ($9530-$9586: clear, the car's
    picture mirrored and coloured), without the copyright line.

    z80: snapshot of the started game. car: 0-3. Returns 6912 bytes of the back buffer.
    """
    p = Player(z80)
    p.sim.memory[0xD983] = car
    p.sim.memory[0xD973] = 1           # as if a message were scrolling, so $942B prints nothing
    p.call(0x9530, stop=0x9587)
    return bytes(p.sim.memory[BACK_BUFFER:BACK_BUFFER + SCREEN_SIZE])


def drawn_picture(z80, pictures, colours=None, car_colour=None):
    """Have the game draw a packed picture into its back buffer.

    z80: snapshot of the loaded game. pictures: picture list for $A741.
    colours: colour lists for $A32A, applied in turn. car_colour: for a car, its colour; the
    game's code at $8821 then mirrors the left half into the right and colours it.
    Returns 6912 bytes of screen memory.
    """
    p = Player(z80)
    p.call(0x9971)                       # clear the screen and back buffer
    for c in colours or []:
        p.call(0xA32A, IY=c)
    p.call(0xA741, DE=pictures)
    if car_colour is not None:
        p.sim.memory[0xD984] = car_colour
        p.call(0x8821, stop=0x884C)      # stop before it copies to the screen
    return bytes(p.sim.memory[BACK_BUFFER:BACK_BUFFER + SCREEN_SIZE])


def ending_screen(z80):
    """Have the game print its ending (the city's reward, the bank and the account number).

    z80: snapshot of the started game. The money is set to $20000, so the account number
    shown is the one for that.
    Returns 6912 bytes of screen memory.
    """
    p = Player(z80)
    p.call(0x9971)
    p.sim.memory[0xD963:0xD966] = [0x00, 0x00, 0x02]
    p.call(ENDING[0], stop=ENDING[1])
    return bytes(p.sim.memory[0x4000:0x4000 + SCREEN_SIZE])


def song_words(z80):
    """Time the song's words: when each word turns white ($B605), in seconds from the song's
    first note, the end of each note (when the colours go back and ENTER is looked at), and
    the lines of words ($B9EA: each a count of spaces, the words with each
    word's last letter in lower case, and a count of spaces to clear after them).

    z80: snapshot of the started game. Returns {'words': [seconds], 'notes': [seconds], 'lines': [text]}.
    """
    p = Player(z80)
    m, r = p.sim.memory, p.sim.registers
    def line(a):          # a count of spaces, the letters, then a count of spaces after them
        e = a + 1
        while m[e] >= 0x20:
            e += 1
        return bytes(m[a:e + 1]).decode("latin-1")
    lines = [line(m[SONG_LINES + 2 * n] | m[SONG_LINES + 2 * n + 1] << 8) for n in range(1, 64)]
    p.call(SONG, stop=0xAFBD)                  # the first note's first click
    start, words, used = r[25], [], 0
    while p.run_to(0xB605, 30) and len(words) < 1000:
        words.append(round((r[25] - start) / 3500000, 4))
        used = (m[0xB5E5] | m[0xB5E6] << 8) - SONG_LINES   # $B63F's place in the list of lines
    text = lines[:used // 2 + 2]               # the first entry is never shown; one more is printed
    p = Player(z80)                            # again, for the end of each note ($AF85: the colours go back)
    r = p.sim.registers
    p.call(SONG, stop=0xAFBD)
    start, notes = r[25], []
    while p.run_to(0xAF85, 30) and len(notes) < 5000:
        notes.append(round((r[25] - start) / 3500000, 4))
        p.run_to(0xAF88, 1)
    return {"words": words, "notes": notes, "lines": text}


def record(z80, wav, addr, **regs):
    """Have the game play a sound and save it.

    z80: snapshot of the started game. wav: output path. addr: the routine that plays it.
    regs: registers it needs (e.g. HL=0xCB24).
    Returns the path written.
    """
    p = Player(z80)
    p.tracer.audio_log.clear()
    p.call(addr, max_seconds=400, **regs)      # the song takes about 210 seconds
    p.save_sound(wav)
    return wav


class WrongCopy(Exception):
    """The tape isn't the copy the port was made from."""


def extract(tape, out, any_copy=False):
    """Save every picture, sound, text and font file the port reads.

    tape: the user's Ghostbusters tape (.tap/.tzx/.z80, or a .zip of one).
    out: folder to write the files to.
    any_copy: go on even if the tape isn't the 1984 Activision one (raises WrongCopy otherwise).
    Returns the number of files written.
    """
    os.makedirs(os.path.join(out, "sprites"), exist_ok=True)
    os.makedirs(os.path.join(out, "sounds"), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        loaded = sim.load(tape, os.path.join(tmp, "loaded.z80"))
        start, end = GAME_RANGE
        if hashlib.sha1(sim.ram(loaded)[start - 0x4000:end - 0x4000]).hexdigest() != GAME_SHA1 and not any_copy:
            raise WrongCopy("this isn't the 1984 Activision Ghostbusters (the re-releases have their code "
                            "in other places); use that copy, or --any-copy to try anyway")
        # let the game's start-up ($8300) run: it builds the back buffer's row table at $DA40
        z80 = sim.run(loaded, 20, os.path.join(tmp, "started.z80"))
        ram = sim.ram(z80)
        written = []

        addr, addrs = SPRITES_START, [LOGO_SPRITE]
        while addr < SPRITES_END:      # the sprites follow one another
            addrs.append(addr)
            addr = sprite_images(ram, addr)[2]
        for addr in addrs:
            picture, mask, _ = sprite_images(ram, addr)
            name = SPRITE_NAMES.get(addr, f"sprite_{addr:04X}")
            written.append(save(picture, out, "sprites", name))
            written.append(save(mask, out, "sprites", name + "_mask"))

        city = city_map(z80)
        written.append(save(screen_image(city, 1), out, "", "city_map"))
        with open(os.path.join(out, "city_map.scr"), "wb") as f:   # the raw screen, for the port to draw on
            f.write(city)
        written.append(f.name)
        for n in range(4):
            with open(os.path.join(out, f"drive_car_{n + 1}.scr"), "wb") as f:   # the drive's road with car n on it
                f.write(drive_road(z80, n))
            written.append(f.name)
        for name, pictures in STREET_PICTURES.items():
            with open(os.path.join(out, name + ".scr"), "wb") as f:
                f.write(drawn_picture(z80, pictures))
            written.append(f.name)
        with open(os.path.join(out, "title.scr"), "wb") as f:      # the title's back buffer
            f.write(drawn_picture(z80, TITLE[0], [TITLE[1]]))
        written.append(f.name)
        for n in range(4):                                          # the car shop's pictures ($87F9)
            pictures = ram[CARS + 2 * n - 0x4000] | ram[CARS + 2 * n + 1 - 0x4000] << 8
            with open(os.path.join(out, f"shop_car_{n + 1}.scr"), "wb") as f:
                f.write(drawn_picture(z80, pictures, car_colour=ram[CARS + 8 + 2 * n - 0x4000]))
            written.append(f.name)
        with open(os.path.join(out, "stomped.bin"), "wb") as f:    # a building the Marshmallow Man stomped on
            f.write(bytes(ram[STOMPED - 0x4000:STOMPED - 0x4000 + 4 * 32]))
        written.append(f.name)

        for name, (pictures, colours) in PICTURES.items():
            written.append(save(screen_image(drawn_picture(z80, pictures, colours), 1), out, "", name))
        written.append(save(screen_image(ending_screen(z80), 1), out, "", "ending"))
        for n in range(4):
            pictures = ram[CARS + 2 * n - 0x4000] | ram[CARS + 2 * n + 1 - 0x4000] << 8
            car_colour = ram[CARS + 8 + 2 * n - 0x4000]
            written.append(save(screen_image(drawn_picture(z80, pictures, car_colour=car_colour), 1),
                                out, "", f"car_{n + 1}"))

        text = {name: bytes(ram[a - 0x4000:a - 0x4000 + n]).decode("latin-1") for name, (a, n) in TEXT.items()}
        with open(os.path.join(out, "text.json"), "w") as f:
            json.dump(text, f, indent=1)
        written.append(f.name)
        written.append(save_rom_font(os.path.join(out, "font.bin")))   # the ROM's font, for the text lines

        for name, sample in SPEECH.items():
            written.append(record(z80, os.path.join(out, "sounds", name + ".wav"), 0xCAC0, HL=sample))
        written.append(record(z80, os.path.join(out, "sounds", "title_song.wav"), SONG))
        with open(os.path.join(out, "song.json"), "w") as f:
            json.dump(song_words(z80), f, indent=0)
        written.append(f.name)
    return len(written)


def save(img, out, folder, name):
    """Save an image as out/folder/name.png.

    Returns the path written.
    """
    path = os.path.join(out, folder, name + ".png")
    img.save(path)
    return path


def main():
    """Command line: TAPE [--out assets]."""
    ap = argparse.ArgumentParser(description="Save Ghostbusters' pictures and sounds from your own tape.")
    ap.add_argument("tape", help="your Ghostbusters .tap/.tzx (or a .zip of one)")
    ap.add_argument("--out", default="assets", help="folder to write to (default assets)")
    ap.add_argument("--any-copy", action="store_true", help="don't stop if it isn't the 1984 Activision tape")
    args = ap.parse_args()
    try:
        print(f"wrote {extract(args.tape, args.out, args.any_copy)} files to {args.out}")
    except WrongCopy as e:
        raise SystemExit(f"{args.tape}: {e}")


if __name__ == "__main__":
    main()
