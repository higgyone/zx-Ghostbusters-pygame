"""Ghostbusters port, all of it: first a setup screen for the trainer's cheats (not in the
original, port/options.py), then the controller menu, the title and its song, your name
and account, the car shop and the equipment shop; the city map with the Marshmallow Man's
attack and the mayor's reward; the drive to a building after Z and catching the ghost there
(or GHQ); and at Zuul the last scene and the ending's text screen. When the city map's game is
over (the bank forecloses), its message and the laugh.

Run from the repo root:  python port/ghostbusters.py      (needs assets/ from tools/extract_assets.py)
Keys as in the original's keyboard controls: Q up, A down, O left, P right (the arrow keys work
too; a joystick or gamepad also works), Z fire. In the menus type as on the Spectrum (backspace
or SHIFT rubs out, ENTER ends a line; ENTER skips the song). In the equipment shop the forklift
carries things into the car; 1-3 change page and E ends shopping (once you have a trap). On the
map Z drives to the building beside you (hold A for the one below), B drops bait, SPACE shows
the status line; on the drive O and P steer and Z works the ghost vacuum; at the building the
keys walk a man and Z drops the trap, brings in the second man, starts and stops the beams; at
Zuul the keys walk each man to the door. After the ending or the game over, ENTER + Ctrl
(SYMBOL SHIFT) starts a new game. Esc quits.

--city skips the start and goes straight to the map, where --pk, --bait, --detector, --sensor,
--vacuum, --car (0-3), --money and --name set what you start with.
"""
import argparse
import json
import os
import random

import numpy as np
import pygame
from zxport.beeper import RATE, VOLUME, Sounds
from zxport.keys import QAOP, Keys
from zxport.screen import PALETTE, Sprite
from zxport.text import load_font
from zxport.window import Pacer, Window, quit_asked

from city import MARSHMALLOW_SENSOR, PK_DETECTOR, City
from drive import DRIVE_FRAMES, GHOST_VACUUM, Drive
from building import BUILDING_FRAMES, Building
from city_screen import CityView
from drive_screen import DriveView
from building_screen import SPRITES as BUILDING_SPRITES, BuildingView, back_to_city, save_city_slots
from ending import Ending
from start import RUB_OUT, SPRITES as START_SPRITES, Start
from text_screen import CHAR_FRAMES as ENDING_FRAMES, CLICK_SECONDS
import options
import trainer

FRAMES_PER_SECOND = 50     # the interrupt, which moves the bottom line's messages; city.step_frames says how
                           # many frames each step of the city takes (about 2.3 for a pass)
SCALE = 3
BORDER = 16                # pixels of border round the 256x192 screen
BORDER_COLOUR = (0, 0, 0)  # the city sets the border to black ($8C35)

STEP_FRAMES = {"drive": DRIVE_FRAMES, "building": BUILDING_FRAMES, "ending": ENDING_FRAMES}   # the city's vary
SPEECH = ("ghostbusters", "he_slimed_me", "laugh")
START_FRAMES = {"char": ENDING_FRAMES, "pass": 2.12, "lift": 2.36}   # measured; the rest take a frame

KEYS = dict(QAOP, fire=[pygame.K_z], bait=[pygame.K_b], status=[pygame.K_SPACE])   # Z is the action key


SPRITES = {"logo": "logo", "ghost": "ghost_city", "keyhole": "keyhole", "key": "key", "bait": "bait_city",
           "dot": "dot", **{f"marshmallow_{n}": f"marshmallow_{n}" for n in range(1, 5)}}


def load_view(assets, back=None):
    """The city's drawing, from the files extract_assets.py wrote.

    assets: that folder. back: passed on to CityView. Returns (CityView, text.json's messages).
    """
    with open(os.path.join(assets, "city_map.scr"), "rb") as f:
        city_scr = f.read()
    folder = os.path.join(assets, "sprites")
    sprites = {key: Sprite(os.path.join(folder, name + ".png"), os.path.join(folder, name + "_mask.png"))
               for key, name in SPRITES.items()}
    with open(os.path.join(assets, "text.json")) as f:
        text = json.load(f)
    with open(os.path.join(assets, "stomped.bin"), "rb") as f:
        stomped = f.read()
    return CityView(city_scr, sprites, load_font(os.path.join(assets, "font.bin")), text, back, stomped), text


ROOF_SPRITES = ("pk_energy_detector", "image_intensifier", "marshmallow_sensor", "ghost_bait", "trap_shop",
                "ghost_vacuum", "laser_confinement")


def load_drive_view(assets, view, car):
    """The drive's drawing. assets: the extract_assets.py folder. view: the CityView.
    car: the car bought (0-3). Returns a DriveView."""
    with open(os.path.join(assets, f"drive_car_{car + 1}.scr"), "rb") as f:
        car_scr = f.read()
    folder = os.path.join(assets, "sprites")
    sprites = {name: Sprite(os.path.join(folder, name + ".png"), os.path.join(folder, name + "_mask.png"))
               for name in ROOF_SPRITES}
    return DriveView(view, car_scr, sprites)


def load_building_view(assets, view):
    """The building scene's drawing. assets: the extract_assets.py folder. view: the CityView.
    Returns a BuildingView."""
    pictures = {}
    for style in ("shop", "brick"):
        with open(os.path.join(assets, f"street_{style}.scr"), "rb") as f:
            pictures[style] = f.read()
    folder = os.path.join(assets, "sprites")
    sprites = {name: Sprite(os.path.join(folder, name + ".png"), os.path.join(folder, name + "_mask.png"))
               for name in BUILDING_SPRITES}
    return BuildingView(view, pictures, sprites)


def load_sounds(assets):
    """The speech, and the ending's click. assets: the extract_assets.py folder. Returns Sounds."""
    sounds = Sounds()
    for name in SPEECH:
        sounds.add_wav(name, os.path.join(assets, "sounds", f"speech_{name}.wav"))
    sounds.add_wav("title_song", os.path.join(assets, "sounds", "title_song.wav"))
    sounds.add("click", np.full(round(RATE * CLICK_SECONDS), int(VOLUME * 32767), np.int16))
    return sounds


def load_start(assets, text, font, words=True):
    """The start (menu, title, name, shops). assets: the extract_assets.py folder. text:
    text.json. font: the ROM's font. words: False after the first game (no song words).
    Returns a Start."""
    pictures = {}
    for name, file in [("title", "title")] + [(f"car_{n}", f"shop_car_{n}") for n in range(1, 5)]:
        with open(os.path.join(assets, file + ".scr"), "rb") as f:
            pictures[name] = f.read()
    folder = os.path.join(assets, "sprites")
    sprites = {n: Sprite(os.path.join(folder, n + ".png"), os.path.join(folder, n + "_mask.png"))
               for n in set(START_SPRITES)}
    with open(os.path.join(assets, "song.json")) as f:
        song = json.load(f)
    seconds = pygame.mixer.Sound(os.path.join(assets, "sounds", "title_song.wav")).get_length()
    start = Start(text, font, pictures, sprites, song, seconds)
    start.words = words
    return start


def typed_keys():
    """The keys held as the Spectrum's characters (letters, digits, space, ENTER; backspace
    or SHIFT rubs out). Returns a set."""
    pressed = pygame.key.get_pressed()
    chars = {chr(65 + n) for n in range(26) if pressed[pygame.K_a + n]}
    chars |= {chr(48 + n) for n in range(10) if pressed[pygame.K_0 + n]}
    for key, ch in ((pygame.K_SPACE, " "), (pygame.K_RETURN, "\r"), (pygame.K_KP_ENTER, "\r"),
                    (pygame.K_BACKSPACE, RUB_OUT), (pygame.K_LSHIFT, RUB_OUT), (pygame.K_RSHIFT, RUB_OUT)):
        if pressed[key]:
            chars.add(ch)
    return chars


def new_city(text, start, seed):
    """The city map after the start's shops ($8C1A). Returns a City."""
    city = City(text, seed=seed, money=start.money, equipment=start.equipment, traps=start.traps,
                bait=start.bait)
    city.start_money = start.start_money // 100
    city.car, city.name, city.traps_carried = start.car, start.name, start.traps
    if not start.capacity:                     # $8C20: "YOUR CAR IS LOADED TO CAPACITY."
        city.scroller.start(text["start"])
    return city


def main():
    """Open the window and run the game: the start, then the city map and what follows."""
    ap = argparse.ArgumentParser(description="Ghostbusters port.")
    ap.add_argument("--assets", default="assets", help="folder written by tools/extract_assets.py")
    ap.add_argument("--city", action="store_true",
                    help="skip the start and go straight to the city map (with the options below)")
    ap.add_argument("--pk", type=int, default=0, help="PK energy to start with (try 4600 for an alert)")
    ap.add_argument("--bait", type=int, default=0, help="ghost bait to start with")
    ap.add_argument("--detector", action="store_true", help="start with the PK energy detector")
    ap.add_argument("--sensor", action="store_true", help="start with the Marshmallow sensor")
    ap.add_argument("--vacuum", action="store_true", help="start with the ghost vacuum")
    ap.add_argument("--car", type=int, default=0, choices=range(4), help="the car (0-3)")
    ap.add_argument("--money", type=int, help="money to start with, in dollars (whole hundreds)")
    ap.add_argument("--name", default="GHOSTBUSTERS", help="your name, for the ending's account number")
    ap.add_argument("--trainer", action="append", choices=trainer.NAMES, metavar="NAME",
                    help=f"turn a cheat on (again for more): {', '.join(trainer.NAMES)}")
    ap.add_argument("--no-setup", action="store_true",
                    help="skip the setup screen (the cheats are then the saved ones, or --trainer's)")
    args = ap.parse_args()

    pygame.init()
    window = Window("Ghostbusters", SCALE, BORDER)
    keys = Keys(KEYS)
    view, text = load_view(args.assets)
    equipment = (PK_DETECTOR if args.detector else 0) | (MARSHMALLOW_SENSOR if args.sensor else 0) | \
        (GHOST_VACUUM if args.vacuum else 0)
    city = City(text, seed=[random.randrange(256) for _ in range(6)], equipment=equipment, bait=args.bait,
                **({} if args.money is None else {"money": args.money // 100 * 100}))
    city.pk, city.car, city.name = args.pk, args.car, args.name
    frames = Pacer(FRAMES_PER_SECOND)
    sounds = load_sounds(args.assets)
    frame, due, pause = 0, 0.0, 0
    # what is running: setup, start, city, drive, building, ending or over
    drive = drive_view = building = building_view = saved = ending = None
    border = BORDER_COLOUR
    start = None

    def begin():
        """After the setup screen: the start, or the city map. Returns (mode, start, shown)."""
        if args.city:
            view.start(city)
            return "city", None, view
        s = load_start(args.assets, text, view.font)
        return "start", s, s

    if args.no_setup:
        trainer.on = set(args.trainer) if args.trainer else options.load_saved()
        mode, start, shown = begin()
    else:                                      # the setup screen first (not in the original)
        setup = options.OptionsScreen(view.font, args.trainer)
        mode, shown = "setup", setup

    while True:
        events = pygame.event.get()
        if quit_asked(events):
            break
        if mode == "setup":
            go = any(e.type == pygame.KEYDOWN and setup.key(e.key) for e in events)
            setup.stick(keys.held() & {"up", "down", "fire"} if keys.stick else set())
            if go:
                trainer.on = set(setup.ticked)
                options.save(trainer.on)
                mode, start, shown = begin()
                frames.reset()
            else:
                window.show(setup.screen, BORDER_COLOUR)
                frames.passes()
            continue
        for _ in range(frames.passes()):
            frame += 1
            if pause:                              # the speech: the game does nothing else meanwhile
                pause -= 1
                continue
            if mode != "start":
                view.interrupt(city)
            due += 1
            while mode != "over" and due >= step_frames(mode, city, start, building):
                due -= step_frames(mode, city, start, building)
                if mode == "start":
                    start.step(keys.held(), typed_keys())
                    border = PALETTE[start.border]
                    if start.last in ("char", "key"):
                        sounds.play("click")
                    elif start.last == "speech":
                        sounds.play(start.speech)
                        pause = round(sounds.seconds(start.speech) * FRAMES_PER_SECOND)
                    elif start.last == "song":
                        sounds.play("title_song")
                    elif start.last == "song_end":
                        pygame.mixer.stop()
                    if start.done:
                        city = new_city(text, start, [random.randrange(256) for _ in range(6)])
                        view.start(city)
                        mode, shown, border = "city", view, BORDER_COLOUR
                elif mode == "drive":
                    drive.step(keys.held())
                    drive_view.update(drive)
                    if drive.done:
                        mode = "building"
                elif mode == "building":
                    building.step(keys.held())
                    building_view.update(building)
                    if building.speech:
                        sounds.play(building.speech)
                        pause = round(sounds.seconds(building.speech) * FRAMES_PER_SECOND)
                    if building.done and building.ending:      # Zuul: on to the text screen
                        ending = Ending(city, building.ending == "won", view.font, text)
                        mode, building = "ending", None
                    elif building.done:
                        city.after_building()
                        back_to_city(view, city, saved)
                        mode, shown, building = "city", view, None
                elif mode == "ending":
                    ending.step()
                    if ending.last == "char":
                        sounds.play("click")
                        shown, border = ending, PALETTE[ending.border]
                    elif ending.last == "speech":
                        sounds.play("laugh")
                        pause = round(sounds.seconds("laugh") * FRAMES_PER_SECOND)
                    else:                          # the game waits on its menu keys: ENTER + SYMBOL
                        mode = "over"              # SHIFT (Ctrl here) starts a new game
                else:
                    city.step(keys.held())
                    view.update(city)
                    if city.event and city.event[0] == "drive":
                        saved = save_city_slots(view)
                        drive = Drive(city)
                        mode = "building" if drive.done else "drive"   # (no steps on the map: straight there)
                        if not drive.done:
                            drive_view = load_drive_view(args.assets, view, city.car)
                            drive_view.start(drive)
                            shown = drive_view
                    elif city.event:                   # the bank forecloses: its message and the laugh
                        ending = Ending(city, "foreclosed", view.font, text)
                        mode = "ending"
                if mode == "building" and building is None:
                    building = Building(city)
                    building_view = building_view or load_building_view(args.assets, view)
                    building_view.start(building)
                    shown = building_view
        if mode == "over" and "\r" in typed_keys() and pygame.key.get_mods() & pygame.KMOD_CTRL:
            start = shown = load_start(args.assets, text, view.font, words=False)
            mode, due = "start", 0.0
        flash = (frame // 16) % 2 == 1         # the Spectrum swaps FLASH every 16 frames
        if shown.screen:                       # (a new scene has none until its first drawing)
            window.show(shown.screen, border, flash)

def step_frames(mode, city, start, building):
    """How many frames the next step of a mode takes (the start's: as long as its last)."""
    if mode == "start":
        return START_FRAMES.get(start.last, 1)
    if mode == "building" and building:
        return building.step_frames
    return STEP_FRAMES.get(mode, city.step_frames)


if __name__ == "__main__":
    main()
