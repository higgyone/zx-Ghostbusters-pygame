"""Drawing the city map as the game does: its own copy of the back buffer ($E000), the
sprite engine, the haunted buildings' colours, and the two text lines at the bottom.
"""
from zxport.screen import Screen, pixel_address, screen_from_bytes
from zxport.text import print_at, print_bytes

from city import MARSHMALLOW_PARTS
from sprites import ATTRS, COPIED, END, Slot, SpriteData, SpriteEngine

LOGO_SLOT, GHOST_SLOTS, WALKER_SLOTS, BAIT_SLOT, PART_SLOTS = 4, (0, 1, 2, 3), (5, 6), 7, (8, 9, 10, 11, 12, 13)
BAIT_DOT_SLOT = 14
BAIT_COLOUR = (0x05, 0xF8)       # cyan ink
PART_COLOUR = (0x47, 0x00)       # bright white on black: the Marshmallow Man forming
# the Marshmallow Man's pieces in slots 8-13 (city.MARSHMALLOW_PARTS), and a dot in slot 14 (the mayor's reward)
LOGO_COLOUR = (0x02, 0xF8)       # the logo sprite's header ($7105): red ink, the cell's paper kept
WALKER_COLOURS = ((0x00, 0xF8), (0x01, 0xF8))   # black keyhole, blue key
HAUNTED_COLOUR = (0x82, 0xF8)    # $9365: red ink and FLASH, the paper kept
# $943B: each building's colour cells: first cell (row, column) and how many rows, 4 cells wide
BUILDING_CELLS = [((1, 5 + 6 * c), 2) for c in range(4)] + \
                 [((4 + 5 * r, 5 + 6 * c), 4) for r in range(3) for c in range(4)] + \
                 [((19, 5 + 6 * c), 2) for c in range(4)]
# Past building 19 the game's table runs on into other bytes, so "building" 20 is 4 columns
# by 85 rows from $555A of the real screen and 21 is 81 rows from $4847 (further ones land
# outside the screen; the port leaves them out). The next screen copy covers what they do,
# except the bottom 3 colour rows: building 20 colours columns 26-29 there.
STRAY_BUILDINGS = {20: (0x155A, 0x55), 21: (0x0847, 0x51)}   # (screen offset, rows)
# $635A: where the buildings are drawn, as bands of pixel rows (first row, rows) and columns
# (first byte, bytes): the 4-wide ones are buildings 0-19, row by row
BUILDING_BANDS = ((8, 16), (32, 32), (72, 32), (112, 32), (152, 16))
BUILDING_COLUMNS = ((0, 3), (5, 4), (11, 4), (17, 4), (23, 4), (29, 3))
PK_COLUMN, MONEY_COLUMN = 0x12, 0x19   # where $AAAB and $AB2E print, on text row 22
TEXT_ROW, MESSAGE_ROW = 22, 23
DOT_BYTES = (24, 25, 27, 28)           # $90A3: the dot's bytes in the logo's saved background
DOT_BITS = (0x01, 0x80, 0x01, 0x80)


def building_cells(n):
    """The 8x8 cells of building n (0-19), as (row, column) pairs."""
    (row, col), rows = BUILDING_CELLS[n]
    return [(row + r, col + c) for r in range(rows) for c in range(4)]


def number_text(digits, col, prefix):
    """How the game prints a number ($AAC0): leading zeros as spaces, and the prefix just
    before the first digit that isn't 0.

    digits: the digits, e.g. '0350'. col: the first digit's column. prefix: ' ' or '$'.
    Returns {column: character}.
    """
    out, zero = {}, " "
    for i, d in enumerate(digits):
        if d == "0":
            out[col + i] = zero
        else:
            if zero != "0":
                out[col + i - 1] = prefix
                zero = "0"
            out[col + i] = d
    return out


def pk_text(pk):
    """Row 22's PK energy ($AAAB). Returns {column: character}."""
    return number_text(f"{pk:04d}", PK_COLUMN, " ")


def money_text(money):
    """Row 22's money ($AB2E). Returns {column: character}."""
    out = number_text(f"{money // 100:04d}00", MONEY_COLUMN, "$")
    if money == 0:
        out.update({0x1D: "$", 0x1E: "0"})
    return out


class CityView:
    """The city map's back buffer and sprites, updated pass by pass from a City."""

    def __init__(self, city_scr, sprites, font, text, back=None, stomped=None):
        """city_scr: the 6912 bytes of city_map.scr (the back buffer's colours come back from
        it on each redraw). sprites: {'logo', 'ghost', 'keyhole', 'key', 'bait', 'dot',
        'marshmallow_1'...'marshmallow_4': zxport Sprite}.
        font: from zxport.text.load_font. text: assets/text.json.
        back: a back buffer to start from (bytearray), or None to start as $8C1A does.
        stomped: the picture of a stomped building ($672D, 4 bytes by 32 rows), or None.
        """
        self.city_scr, self.stomped = bytes(city_scr), stomped
        self.base_attrs = bytes(city_scr[ATTRS:END])
        self.font, self.text = font, text
        self.slots = [Slot() for _ in range(16)]
        for n in GHOST_SLOTS:            # the two that start on the right face left
            self.slots[n] = Slot(SpriteData(sprites["ghost"], mirror=n >= 2))
        self.slots[LOGO_SLOT] = Slot(SpriteData(sprites["logo"]), LOGO_COLOUR)
        for n, name, colour in zip(WALKER_SLOTS, ("keyhole", "key"), WALKER_COLOURS):
            self.slots[n] = Slot(SpriteData(sprites[name]), colour)
        self.slots[BAIT_SLOT] = Slot(SpriteData(sprites["bait"]), BAIT_COLOUR)
        for n, (name, mirror) in enumerate(MARSHMALLOW_PARTS):
            self.slots[8 + n] = Slot(SpriteData(sprites[name], mirror), PART_COLOUR)
        self.slots[BAIT_DOT_SLOT] = Slot(SpriteData(sprites["dot"]))
        self.back = bytearray(back if back is not None else city_scr)
        self.engine = SpriteEngine(self.back, self.slots)
        self.printed = [None, None]      # the PK and money on the text line
        self.screen = None
        self.screen_attrs = bytearray(self.back[COPIED:END])   # the screen's bottom colours, never copied over

    def start(self, city):
        """Finish setting up as $8CBD-$8CD4 do: the numbers, the haunted buildings' colours,
        the copyright line. city: a City."""
        if any(city.stomped):
            self.rebuild(city)
        self.print_numbers(city)
        self.screen = Screen(*screen_from_bytes(self.back))    # $8CC6: the whole back buffer
        self.recolour(city)
        print_bytes(self.back, self.font, self.text["copyright"], 0, MESSAGE_ROW)

    def print_numbers(self, city):
        """$AAAB/$AB2E: print PK or money into the back buffer when it changes (each is
        printed by the routine that changes it)."""
        for n, (value, text) in enumerate(((city.pk, pk_text), (city.money, money_text))):
            if self.printed[n] == value:
                continue
            self.printed[n] = value
            for col, ch in text(value).items():
                print_bytes(self.back, self.font, ch, col, TEXT_ROW)
                if self.screen:                # it prints on the screen as well
                    print_at(self.screen, self.font, ch, col, TEXT_ROW)

    def rebuild(self, city):
        """$929D: draw the buildings again into the back buffer (over any sprites there), the
        stomped ones with the stomped picture. The others, and the ZUUL and GHQ labels the game
        prints on them afterwards, come back as they are in city_map.scr."""
        for r, (top, rows) in enumerate(BUILDING_BANDS):
            for c, (col, width) in enumerate(BUILDING_COLUMNS):
                n = r * 4 + c - 1
                stomped = width == 4 and city.stomped[n] and self.stomped
                for y in range(rows):
                    o = pixel_address(col * 8, top + y)
                    if stomped:
                        self.back[o:o + 4] = self.stomped[4 * y:4 * y + 4]
                    else:
                        self.back[o:o + width] = self.city_scr[o:o + width]

    def recolour(self, city):
        """$9198: the city's colours again, then the haunted buildings in flashing red."""
        self.back[ATTRS:END] = self.base_attrs
        for n in city.haunted():
            self.colour_building(n, *HAUNTED_COLOUR)

    def colour_building(self, n, ink, keep):
        """$926A: colour building n's cells in the back buffer (past 19, see STRAY_BUILDINGS)."""
        if n < len(BUILDING_CELLS):
            for r, c in building_cells(n):
                o = ATTRS + r * 32 + c
                self.back[o] = self.back[o] & keep | ink
        elif n in STRAY_BUILDINGS:
            start, rows = STRAY_BUILDINGS[n]
            for o in range(start, start + rows * 32, 32):
                for c in range(4):
                    if COPIED <= o + c < END:
                        self.screen_attrs[o + c - COPIED] = self.screen_attrs[o + c - COPIED] & keep | ink
                        if self.screen:
                            r, col = divmod(o + c - ATTRS, 32)
                            self.screen.attrs[r, col] = self.screen_attrs[o + c - COPIED]

    def interrupt(self, city):
        """One frame of the bottom line's scroller ($A6A6), on the back buffer and the screen."""
        act = city.scroller.interrupt()
        if not act:
            return
        if act[0] == "print":
            print_bytes(self.back, self.font, act[1], 0, MESSAGE_ROW)
            if self.screen:
                print_at(self.screen, self.font, act[1], 0, MESSAGE_ROW)
            return
        for line in range(8):                  # RLD along the row: half a character left
            o = pixel_address(0, MESSAGE_ROW * 8 + line)
            row = int.from_bytes(self.back[o:o + 32], "big")
            self.back[o:o + 32] = ((row << 4) & ((1 << 256) - 1)).to_bytes(32, "big")
            if self.screen:
                y = MESSAGE_ROW * 8 + line
                self.screen.pixels[y, :-4] = self.screen.pixels[y, 4:].copy()
                self.screen.pixels[y, -4:] = 0

    def update(self, city):
        """After a City.step: the drawing parts of the same pass.

        city: a City. Returns the Screen as the game shows it after this pass.
        """
        for n, ink, keep in city.lights:
            self.colour_building(n, ink, keep)
        self.print_numbers(city)
        if city.rebuild:
            self.rebuild(city)
        if not city.drawn:
            return self.screen
        logo = self.slots[LOGO_SLOT]
        if city.dot:
            for n, bit in zip(DOT_BYTES, DOT_BITS):
                if n < len(logo.saved):
                    logo.saved[n] |= bit
        logo.x, logo.y = city.x, city.y
        for n, g in zip(GHOST_SLOTS, city.ghosts):
            self.slots[n].x, self.slots[n].y = g
        for n, w in zip(WALKER_SLOTS, city.walkers):
            self.slots[n].x, self.slots[n].y = w
        self.slots[BAIT_SLOT].x, self.slots[BAIT_SLOT].y = city.bait
        for n, part in zip(PART_SLOTS, city.parts):
            self.slots[n].x, self.slots[n].y = part
        self.slots[BAIT_DOT_SLOT].x, self.slots[BAIT_DOT_SLOT].y = city.bait_dot
        self.engine.update()
        self.screen = Screen(*screen_from_bytes(self.back[:COPIED] + self.screen_attrs))   # $ADB2
        if city.recolour:
            self.recolour(city)
        return self.screen
