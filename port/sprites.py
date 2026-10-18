"""Ghostbusters' sprite engine ($AB88), copied closely, on the port's own copy of the game's
back buffer (6912 bytes laid out like the screen, as at $E000).

The game has 16 sprite slots ($DF00, 16 bytes each). Each pass it finds the first slot whose
position changed, takes that slot and every later one off the back buffer (last first),
putting back what was under them, then draws them again at their new places (first first),
saving what is under them. A sprite hides pixels with its mask, then adds its picture, and
can colour its cells. Colours saved under a sprite come back when it moves, even if the city
was recoloured in between, so the port has to keep these copies just as the game does.
"""
import numpy as np
from zxport.screen import pixel_address

SPRITE_Y_OFFSET = 32      # sprite y is screen row + 32 (the game's row table at $DC00 starts 32 rows early)
ATTRS, END = 6144, 6912   # where the colours start and end in the buffer
SLOTS = 16


def mirrored(picture, hide):
    """$AE01: flip a sprite left to right as the game does. It takes the picture and mask
    bytes two at a time, as if every sprite were 2 bytes wide, and swaps and flips each pair.
    For a sprite 1 byte wide (the beams) that also swaps each pair of rows, which is why the
    beams of a man facing left look jagged. picture, hide: 0/1 arrays. Returns the two flipped."""
    h, w = picture.shape
    stream = np.concatenate([np.packbits(picture, axis=1).ravel(), np.packbits(1 - hide, axis=1).ravel()])
    pairs = stream.reshape(-1, 2)[:, ::-1]
    flipped = np.unpackbits(pairs.reshape(-1, 1), axis=1)[:, ::-1].reshape(2, h, w)
    return flipped[0], 1 - flipped[1]


class SpriteData:
    """A sprite's picture and mask as bytes, shifted 0, 2, 4 and 6 pixels as the game keeps
    them ($AE34), one byte wider than the picture."""

    def __init__(self, sprite, mirror=False):
        """sprite: a zxport Sprite (picture and hide arrays).
        mirror: True to flip it left to right first, as $AE01 does (e.g. ghosts facing left)."""
        picture, hide = sprite.picture, sprite.hide
        if mirror:
            picture, hide = mirrored(picture, hide)
        h, w = picture.shape
        self.height, self.width = h, w // 8 + 1
        self.shifts = []
        for shift in range(4):
            pic = np.zeros((h, self.width * 8), np.uint8)
            keep = np.ones((h, self.width * 8), np.uint8)
            pic[:, 2 * shift:2 * shift + w] = picture
            keep[:, 2 * shift:2 * shift + w] = 1 - hide
            self.shifts.append((np.packbits(pic, axis=1).tolist(), np.packbits(keep, axis=1).tolist()))


class Slot:
    """One sprite slot: where it is, where it was drawn, and what is saved under it."""

    def __init__(self, data=None, colour=None):
        """data: a SpriteData, or None for an empty slot. colour: (ink bits to set, bits to
        keep), as header bytes 7 and 8; None if the sprite leaves the colours alone ($FF)."""
        self.data, self.colour = data, colour
        self.x = self.y = 0              # +3, +4: where it is now (y 0: not shown)
        self.old_x = self.old_y = 0      # +5, +6: where it was drawn
        self.saved = []                  # the pixel bytes under it (on-screen rows only)
        self.saved_attrs = []            # the colours under it
        self.attr_rows = 0               # +9


PLAY_ROWS = 176           # sprites are only drawn on the top 22 character rows (the text lines are below)


def row_base(y):
    """Offset of a sprite row's first byte, or None when the row is outside the play area
    (the game's row table at $DC00 has 0 there).
    """
    row = y - SPRITE_Y_OFFSET
    return pixel_address(0, row) if 0 <= row < PLAY_ROWS else None


def attr_start(x, y, rows):
    """Where a sprite's colours start ($AD30): (offset, rows left), skipping rows above the
    screen; offset is None if none are left."""
    row = (y >> 3) - SPRITE_Y_OFFSET // 8
    while row < 0:
        rows -= 1
        if rows == 0:
            return None, 0
        row += 1
    return ATTRS + row * 32 + (x >> 3), rows


class SpriteEngine:
    """Draws the slots into a back buffer the way the game does."""

    def __init__(self, back, slots):
        """back: bytearray(6912). slots: 16 Slots (empty ones too: the game checks all)."""
        self.back, self.slots = back, slots

    def _put(self, offset, value):
        if offset < END:                # a sprite at the very bottom right could run past the end
            self.back[offset] = value

    def erase(self, s):
        """$ABB7: put back what was under a slot."""
        if not s.old_y or not s.data:
            return
        d, n = s.data, 0
        for i in range(d.height):
            base = row_base(s.old_y + i)
            if base is None:
                continue
            for b in range(d.width):
                self._put(base + (s.old_x >> 3) + b, s.saved[n])
                n += 1
        if s.colour:
            offset, rows = attr_start(s.old_x, s.old_y, s.attr_rows)
            cols = d.width - (1 if s.old_x & 7 == 0 else 0)
            n = 0
            while offset is not None and rows:
                for b in range(cols):
                    self._put(offset + b, s.saved_attrs[n])
                    n += 1
                offset += 32
                rows -= 1
                if offset >= END:
                    break

    def draw(self, s):
        """$AC80: draw a slot where it is now, saving what is under it."""
        s.old_x, s.old_y = s.x, s.y
        if not s.y or not s.data:
            return
        d = s.data
        pic, keep = d.shifts[(s.x & 7) >> 1]
        s.saved = []
        for i in range(d.height):
            base = row_base(s.y + i)
            if base is None:
                continue
            for b in range(d.width):
                o = base + (s.x >> 3) + b
                under = self.back[o] if o < END else 0
                s.saved.append(under)
                self._put(o, under & keep[i][b] | pic[i][b])
        if s.colour:
            ink, mask = s.colour
            s.attr_rows = ((s.y & 7) + d.height + 7) >> 3
            offset, rows = attr_start(s.x, s.y, s.attr_rows)
            cols = d.width - (1 if s.x & 7 == 0 else 0)
            s.saved_attrs = []
            while offset is not None and rows:
                for b in range(cols):
                    under = self.back[offset + b] if offset + b < END else 0
                    s.saved_attrs.append(under)
                    self._put(offset + b, under & mask | ink)
                offset += 32
                rows -= 1
                if offset >= END:
                    break

    def update(self):
        """$AB88: redraw from the first slot that moved, if any did."""
        first = next((n for n, s in enumerate(self.slots) if (s.x, s.y) != (s.old_x, s.old_y)), None)
        if first is None:
            return
        for s in reversed(self.slots[first:]):
            self.erase(s)
        for s in self.slots[first:]:
            self.draw(s)
