"""Spectrum screen memory to images.

The screen is 6912 bytes: 6144 bytes of pixels (256x192, one bit each, in the Spectrum's
interleaved row order) then 768 bytes of colour attributes (one per 8x8 cell).
"""
from PIL import Image

SCREEN_SIZE = 6912


def colour(index, bright):
    """RGB of a Spectrum colour.

    index: 0-7 (black, blue, red, magenta, green, cyan, yellow, white).
    bright: True for the BRIGHT version.
    Returns an (r, g, b) tuple.
    """
    level = 255 if bright else 205
    return (level if index & 2 else 0, level if index & 4 else 0, level if index & 1 else 0)


def pixel_address(x, y):
    """Offset into screen memory of the byte holding pixel (x, y).

    x: 0-255. y: 0-191.
    Returns 0-6143. Bit (7 - x % 8) of that byte is the pixel.
    """
    return ((y & 0xC0) << 5) | ((y & 0x07) << 8) | ((y & 0x38) << 2) | (x >> 3)


def screen_image(scr, scale=2, flash=False):
    """Draw a screen.

    scr: 6912 bytes of screen memory (address $4000 onwards).
    scale: how many times bigger than 256x192 to make the image.
    flash: True to draw FLASH cells with ink and paper swapped.
    Returns a PIL image.
    """
    img = Image.new("RGB", (256, 192))
    px = img.load()
    for cy in range(24):
        for cx in range(32):
            attr = scr[6144 + cy * 32 + cx]
            bright = bool(attr & 0x40)
            ink, paper = colour(attr & 7, bright), colour((attr >> 3) & 7, bright)
            if flash and attr & 0x80:
                ink, paper = paper, ink
            for row in range(8):
                y = cy * 8 + row
                byte = scr[pixel_address(cx * 8, y)]
                for bit in range(8):
                    px[cx * 8 + bit, y] = ink if byte & (0x80 >> bit) else paper
    if scale != 1:
        img = img.resize((256 * scale, 192 * scale), Image.NEAREST)
    return img


def is_blank(scr):
    """Whether a screen shows nothing: every pixel the same colour.

    scr: 6912 bytes of screen memory.
    Returns True or False.
    """
    return screen_image(scr, scale=1).getcolors(1) is not None


def contact_sheet(images, labels, columns=4):
    """Lay out images in a grid with a label above each.

    images: list of PIL images, all the same size.
    labels: one string per image.
    columns: images per row.
    Returns a PIL image.
    """
    from PIL import ImageDraw
    w, h = images[0].size
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGB", (w * columns, (h + 16) * rows), "white")
    draw = ImageDraw.Draw(sheet)
    for i, (img, label) in enumerate(zip(images, labels)):
        x, y = (i % columns) * w, (i // columns) * (h + 16)
        draw.text((x + 3, y + 2), label, fill="black")
        sheet.paste(img, (x, y + 16))
    return sheet


FONT_START, FONT_SIZE = 0x3D00, 768   # the 48K ROM's font: characters 32-127, 8 bytes each


def save_rom_font(path):
    """Save the 48K ROM's font (from the ROM that comes with SkoolKit) for zxport.text.

    The ROM is copyrighted, so ports don't include it: each game's extract_assets.py calls
    this to write font.bin next to the game's other assets.
    path: the file to write. Returns path.
    """
    import os
    import skoolkit
    rom = os.path.join(os.path.dirname(skoolkit.__file__), "resources", "48.rom")
    with open(rom, "rb") as f:
        data = f.read()[FONT_START:FONT_START + FONT_SIZE]
    with open(path, "wb") as f:
        f.write(data)
    return path
