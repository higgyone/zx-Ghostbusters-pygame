"""Printing text on a Screen with an 8x8 font, as the Spectrum's ROM does.

The ROM's font is copyrighted, so no port includes it: a game's extract_assets.py saves it
from the simulator (zxkit) as font.bin, 768 bytes, characters 32-127 with 8 bytes each,
just as it sits in the ROM at $3D00.
"""
import numpy as np

from .screen import pixel_address

FIRST_CHAR = 32


def load_font(path):
    """Read a font saved as font.bin.

    path: the file. Returns a (96, 8, 8) array of 0/1: character, row, column.
    """
    with open(path, "rb") as f:
        data = np.frombuffer(f.read(), np.uint8)
    return np.unpackbits(data).reshape(-1, 8, 8)


def print_at(screen, font, text, col, row):
    """Print text in 8x8 cells, replacing the pixels there (colours are left alone).

    screen: a zxport Screen. font: from load_font. text: the characters (32-127; others print
    as '?'). col, row: the first character's cell (0-31, 0-23). Text past the right edge is
    not printed.
    """
    for i, ch in enumerate(text):
        c = col + i
        if not 0 <= c < 32:
            continue
        code = ord(ch) - FIRST_CHAR
        if not 0 <= code < len(font):
            code = ord("?") - FIRST_CHAR
        screen.pixels[row * 8:row * 8 + 8, c * 8:c * 8 + 8] = font[code]


def print_bytes(data, font, text, col, row):
    """As print_at, but into screen memory bytes (6912, laid out like $4000), for a port that
    keeps its own copy of the game's screen or back buffer.

    data: a bytearray. The rest as print_at.
    """
    for i, ch in enumerate(text):
        c = col + i
        if not 0 <= c < 32:
            continue
        code = ord(ch) - FIRST_CHAR
        if not 0 <= code < len(font):
            code = ord("?") - FIRST_CHAR
        for line in range(8):
            data[pixel_address(c * 8, row * 8 + line)] = int(np.packbits(font[code][line])[0])
