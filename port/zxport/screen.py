"""A Spectrum screen for a port: 256x192 pixels on or off, plus a colour (attribute) for each
8x8 cell, kept apart the way the Spectrum keeps them and turned into a picture at the end.
"""
import numpy as np
import pygame
from PIL import Image

WIDTH, HEIGHT = 256, 192
FLASH, BRIGHT = 0x80, 0x40   # attribute bits

# Spectrum colours: normal, then bright
PALETTE = [(0, 0, 0), (0, 0, 205), (205, 0, 0), (205, 0, 205), (0, 205, 0), (0, 205, 205), (205, 205, 0), (205, 205, 205),
           (0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]


def pixel_address(x, y):
    """Offset in screen memory of the byte holding pixel (x, y): x 0-255, y 0-191."""
    return ((y & 0xC0) << 5) | ((y & 0x07) << 8) | ((y & 0x38) << 2) | (x >> 3)


def load_scr(path):
    """Read a raw Spectrum screen (6912 bytes).

    path: the .scr file. Returns (pixels, attrs): a 192x256 array of 0/1, and a 24x32 array of
    attribute bytes (ink, paper, bright, flash).
    """
    with open(path, "rb") as f:
        return screen_from_bytes(f.read())


def screen_from_bytes(data):
    """Split 6912 bytes of Spectrum screen memory into (pixels, attrs), as load_scr."""
    pixels = np.zeros((HEIGHT, WIDTH), np.uint8)
    for y in range(HEIGHT):
        # the Spectrum's screen rows are stored out of order: thirds, then character rows, then pixel rows
        row = pixel_address(0, y)
        pixels[y] = np.unpackbits(np.frombuffer(bytes(data[row:row + 32]), np.uint8))
    attrs = np.frombuffer(bytes(data[6144:6912]), np.uint8).reshape(24, 32).copy()
    return pixels, attrs


class Sprite:
    """A sprite picture and its mask, as 0/1 arrays (rows x columns)."""

    def __init__(self, picture_png, mask_png=None):
        """Load a sprite saved as PNGs (non-transparent pixels count as set).

        picture_png: the picture (ink pixels drawn, the rest see-through).
        mask_png: the mask (set where the sprite hides what is under it); None means the
        sprite hides nothing, so it is only ORed on.
        """
        self.picture = _bits(picture_png)
        self.hide = _bits(mask_png) if mask_png else np.zeros_like(self.picture)


def _bits(png):
    """A PNG as a 0/1 array: 1 where the pixel isn't transparent."""
    return (np.array(Image.open(png).convert("RGBA"))[:, :, 3] > 0).astype(np.uint8)


class Screen:
    """Pixels and colours, drawn into a pygame surface."""

    def __init__(self, pixels=None, attrs=None):
        """pixels: 192x256 array of 0/1. attrs: 24x32 attribute bytes. None gives a blank
        screen (black ink on white paper, as the Spectrum starts)."""
        self.pixels = np.zeros((HEIGHT, WIDTH), np.uint8) if pixels is None else pixels.copy()
        self.attrs = np.full((24, 32), 0x38, np.uint8) if attrs is None else attrs.copy()

    def draw(self, sprite, left, top):
        """Draw a sprite at a screen position: clear the mask's pixels, then add the picture
        (screen = screen AND NOT mask OR picture, as most Spectrum games do). Colours are left
        alone. Parts off the screen are not drawn.

        sprite: a Sprite. left, top: screen pixel of its top-left corner.
        """
        h, w = sprite.picture.shape
        r0, r1 = max(0, top), min(HEIGHT, top + h)
        c0, c1 = max(0, left), min(WIDTH, left + w)
        if r0 >= r1 or c0 >= c1:
            return
        pic = sprite.picture[r0 - top:r1 - top, c0 - left:c1 - left]
        hide = sprite.hide[r0 - top:r1 - top, c0 - left:c1 - left]
        self.pixels[r0:r1, c0:c1] = (self.pixels[r0:r1, c0:c1] & (1 - hide)) | pic

    def colour(self, cells, ink, keep=0):
        """Colour 8x8 cells: each attribute becomes (attribute AND keep) OR ink.

        cells: (cell row, cell column) pairs. ink: bits to set. keep: bits of the old
        attribute to keep (0 replaces it with ink).
        """
        for r, c in cells:
            if 0 <= r < 24 and 0 <= c < 32:
                self.attrs[r, c] = self.attrs[r, c] & keep | ink

    def to_surface(self, scale=1, flash_swapped=False):
        """The screen as a pygame surface.

        scale: how many window pixels per Spectrum pixel. flash_swapped: True to draw FLASH
        cells with ink and paper swapped (the Spectrum swaps them every 16 frames, 0.32 s).
        Returns a new surface.
        """
        ink = self.attrs & 7 | (self.attrs >> 3) & 8          # bright adds 8
        paper = (self.attrs >> 3) & 7 | (self.attrs >> 3) & 8
        if flash_swapped:
            flashing = (self.attrs & FLASH) != 0
            ink, paper = np.where(flashing, paper, ink), np.where(flashing, ink, paper)
        ink = np.repeat(np.repeat(ink, 8, 0), 8, 1)
        paper = np.repeat(np.repeat(paper, 8, 0), 8, 1)
        colours = np.array(PALETTE, np.uint8)[np.where(self.pixels == 1, ink, paper)]
        surface = pygame.surfarray.make_surface(colours.transpose(1, 0, 2))
        if scale != 1:
            surface = pygame.transform.scale(surface, (WIDTH * scale, HEIGHT * scale))
        return surface
