"""The game's text screens: $8B92 types a message a character at a time into the back buffer
and the screen, with a click for each one. The menu, the shops and the ending use it.
"""
import numpy as np
from zxport.screen import Screen, screen_from_bytes

from sprites import ATTRS, COPIED

BLANK_ATTR = 0x38                # $9971: white paper, black ink
CHAR_FRAMES = 2.08               # frames per character typed (measured: $A8FC waits for the next frame)
CLICK_SECONDS = 0.041            # $8C0F: the speaker is on while a character is copied to the screen


class TextScreen:
    """A back buffer and a screen (as the game keeps them), and $8B92's print position."""

    def __init__(self, font):
        """font: from zxport.text.load_font."""
        self.font = font
        self.glyphs = [[int(np.packbits(font[c][line])[0]) for line in range(8)] for c in range(len(font))]
        self.back, self.scr = bytearray(6912), bytearray(6912)
        self.col = self.row = 0          # $8B92's C, and E / 8
        self.border_colour = 0           # $D9CB: what each click sets the border to
        self.border = 0                  # the border's colour now (0-7)
        self._screen, self.changed = None, False

    def message(self, text):
        """$8B92: print text with its control bytes, copying to the screen after each
        character. Yields 'char' after each one."""
        chars = iter(text)
        for ch in chars:
            a = ord(ch)
            if a & 0x80 and a & 0x40:        # down so many rows
                self.down(((a << 3) & 0xFF) // 8)
            elif a & 0x80:                   # right so many columns
                self.col = (a + self.col) & 0x1F
            elif a == 0x0D:
                self.col = 0
                self.down(1)
            elif a == 0x0E:                  # clear the screen in a colour (the next byte)
                self.wipe(ord(next(chars)))
            elif a == 0x0B:
                self.col = self.row = 0
            else:
                self.click()
                self.put(ch)
                self.copy()
                yield "char"

    def down(self, rows):
        """Move down so many rows, as $8BA9 does: in pixels, as a byte, less 192 while past
        the bottom."""
        e = (self.row * 8 + rows * 8) & 0xFF
        while e >= 0xC0:
            e -= 0xC0
        self.row = e // 8

    def clear(self):
        """$9971: both pixel buffers cleared, and their top 21 colour rows set to $38."""
        for buf in (self.back, self.scr):
            buf[:ATTRS] = bytes(ATTRS)
            buf[ATTRS:COPIED] = bytes([BLANK_ATTR]) * (COPIED - ATTRS)

    def wipe(self, colour):
        """$8BC2 (the $0E byte): clear, then the back buffer's colours and the screen's bottom
        8 rows of colours in the given colour, and the border to its paper. Home."""
        self.clear()
        self.back[ATTRS:] = bytes([colour]) * 768
        self.scr[ATTRS + 512:] = bytes([colour]) * 256
        self.border_colour = (colour & 0x38) >> 3
        self.col = self.row = 0

    def click(self):
        """$8C0F: the speaker clicks and the border takes $D9CB's colour."""
        self.border = self.border_colour & 7

    def put(self, ch):
        """$AA3A: a character on both the back buffer and the screen, then one column on.
        Past column 31 it goes on in the same 256 bytes of the screen, as the game adds the
        column to the low byte only (so row 23 runs on into row 16)."""
        code = ord(ch) - 0x20 if 0x20 <= ord(ch) < 0x80 else ord("?") - 0x20
        glyph = self.glyphs[code]
        for line in range(8):
            base = pixel_row(self.row * 8 + line)
            o = (base & ~0xFF) | ((base + self.col) & 0xFF)
            self.back[o] = self.scr[o] = glyph[line]
        self.col += 1
        self.changed = True

    def copy(self):
        """$ADB2: the back buffer to the screen (not its bottom 3 colour rows)."""
        self.scr[:COPIED] = self.back[:COPIED]
        self.shown()

    def shown(self):
        """Say the screen bytes have changed (the Screen is made again when next asked for)."""
        self.changed = True

    @property
    def screen(self):
        """The screen as a zxport Screen, or None before anything is shown."""
        if self.changed:
            self._screen, self.changed = Screen(*screen_from_bytes(bytes(self.scr))), False
        return self._screen

    def print_money(self, money):
        """$AB32: the money in whole hundreds, $ before its first digit, leading zeros as spaces."""
        lead = " "
        digits = f"{money // 100:04d}00"
        if not money:                     # $AB4C: all zero
            for ch in digits:
                self.put(lead)
            self.col = 0x1D
            self.put("$")
            self.put("0")
            return
        for d in digits:
            if d == "0" and lead == " ":
                self.put(lead)
                continue
            if lead != "0":
                self.col -= 1
                self.put("$")
                lead = "0"
            self.put(d)


def pixel_row(y):
    """Where pixel row y starts in a screen's bytes."""
    return ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
