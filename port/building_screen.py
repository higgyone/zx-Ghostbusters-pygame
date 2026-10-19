"""Drawing the scene at a building (notes/08-the-building.md) as the game does: the street's
picture and colours in the city's back buffer, and the scene's own 16 sprite slots. Also
going back to the city map afterwards ($9FBD-$A02B, then $8CBD).
"""
from zxport.screen import Screen, screen_from_bytes
from zxport.text import print_at, print_bytes

from city import GHQ, ZUUL
from city_screen import (BAIT_DOT_SLOT, BAIT_SLOT, GHOST_SLOTS, HAUNTED_COLOUR, LOGO_SLOT, MESSAGE_ROW,
                         PART_SLOTS, TEXT_ROW, WALKER_SLOTS)
from sprites import ATTRS, COPIED, END, Slot, SpriteData, SpriteEngine
from text_screen import BLANK_ATTR
# $A32A colour tables: (column, row, width, height, colour)
SHOP = [(0, 0, 3, 6, 8), (30, 0, 2, 5, 8), (0, 5, 2, 4, 32), (0, 15, 2, 1, 32), (7, 7, 18, 1, 120),
        (9, 8, 14, 3, 112), (7, 11, 18, 1, 58), (13, 8, 1, 3, 120), (18, 8, 1, 3, 120), (9, 12, 1, 4, 112),
        (15, 12, 2, 4, 112), (22, 12, 1, 4, 112), (7, 2, 3, 1, 120), (12, 2, 3, 1, 120), (17, 2, 3, 1, 120),
        (22, 2, 3, 1, 120)]       # $A367
SHOP_AWNING, SHOP_WINDOWS = 6, (5, 9, 10, 11)   # the entries $9A5E-$9A7B change
BRICK = [(0, 0, 3, 6, 8), (30, 0, 2, 5, 8), (0, 5, 2, 4, 32), (0, 15, 2, 1, 32), (7, 7, 18, 1, 120),
         (6, 7, 19, 9, 56), (11, 8, 9, 8, 71), (10, 9, 1, 7, 7), (20, 9, 1, 7, 7), (7, 2, 3, 1, 120),
         (12, 2, 3, 1, 120), (17, 2, 3, 1, 120), (22, 2, 3, 1, 120)]   # $A3CF (also GHQ's and Zuul's)
BRICK_WALL, BRICK_DOOR = 5, 6     # the entries $9A91/$9A9E change (and they stay changed)
GHQ_COLOURS = [(6, 7, 19, 9, 56), (11, 9, 9, 7, 71), (10, 8, 1, 8, 16), (20, 8, 1, 8, 16)]   # $A411
ZUUL_COLOURS = [(6, 7, 19, 9, 56), (10, 9, 11, 7, 71)]   # $A69A
GHQ_SIGN = (9, 7)                 # $A035: column and text row of GHOSTBUSTERS
# sprites whose header sets a colour: (ink, bits kept)
COLOURS = {"trap_stream_top": (0x03, 0xF8), "trap_stream": (0x02, 0xF8)}
SPRITES = ("man_standing", "man_walking", "man_slimed", "ghost", "trap_open", "trap_shut", "trap_stream_top",
           "trap_stream", "beam_up", "marshmallow_1", "marshmallow_2", "marshmallow_3", "marshmallow_4")


def paint(back, table):
    """$A32A: colour rectangles of the back buffer."""
    for col, row, width, height, colour in table:
        for r in range(row, row + height):
            o = ATTRS + r * 32 + col
            back[o:o + width] = bytes([colour]) * width


class BuildingView:
    """The building scene's screen, in the CityView's back buffer."""

    def __init__(self, view, pictures, sprites):
        """view: the CityView. pictures: {'shop', 'brick': the street's .scr bytes}.
        sprites: {name: zxport Sprite} for SPRITES."""
        self.view, self.pictures = view, pictures
        self.back = view.back
        self.data = {}
        for name in SPRITES:
            for mirror in (False, True):
                self.data[(name, mirror)] = SpriteData(sprites[name], mirror)
        self.slots = [Slot() for _ in range(16)]
        self.engine = SpriteEngine(self.back, self.slots)
        self.screen = None

    def start(self, building):
        """$9A3D-$9B25 (and $A02E-$A03D at GHQ): the street, PK and money."""
        v, c, b = self.view, building.city, self.back
        b[:ATTRS] = self.pictures[building.style][:ATTRS]          # $9971 and $A741
        b[ATTRS:COPIED] = bytes([BLANK_ATTR]) * (COPIED - ATTRS)
        if building.style == "shop":
            table = list(SHOP)
            awning, window = building.colours
            table[SHOP_AWNING] = table[SHOP_AWNING][:4] + (awning,)
            for n in SHOP_WINDOWS:
                table[n] = table[n][:4] + (window,)
        else:
            table = list(BRICK)
            table[BRICK_WALL] = table[BRICK_WALL][:4] + (c.street_colours[0],)
            table[BRICK_DOOR] = table[BRICK_DOOR][:4] + (c.street_colours[1],)
        paint(b, table)
        if building.number == ZUUL:
            paint(b, ZUUL_COLOURS)                                  # $A426
        if building.number == GHQ:
            paint(b, GHQ_COLOURS)
            print_bytes(b, v.font, v.text["ghq_sign"], *GHQ_SIGN)
        print_bytes(b, v.font, v.text["pk_label"], 0, TEXT_ROW)    # $931C
        print_bytes(b, v.font, v.text["copyright"], 0, MESSAGE_ROW)   # $9430
        v.screen = None
        v.printed = [None, None]
        v.print_numbers(c)
        for s in self.slots:
            s.x = s.y = s.old_x = s.old_y = 0
            s.data = None
        self.screen = None

    def update(self, building):
        """Repeat a Building.step's drawings. Returns the Screen."""
        c = building.city
        for op, slots, pk, money in building.ops:
            for s, (x, y, kind) in zip(self.slots, slots):
                if kind is not None:
                    s.data, s.colour = self.data[kind], COLOURS.get(kind[0])
                s.x, s.y = x, y
            pk_now, money_now = c.pk, c.money          # the numbers as they were then
            c.pk, c.money = pk, money
            self.view.print_numbers(c)
            c.pk, c.money = pk_now, money_now
            self.engine.update()
            if op == "draw":
                self.show()
        return self.screen

    def show(self):
        """$ADB2: the back buffer to the screen (not its bottom 3 colour rows)."""
        self.screen = self.view.screen = Screen(*screen_from_bytes(self.back[:COPIED] + self.view.screen_attrs))

def save_city_slots(view):
    """$951B: what the city's sprite slots were, to come back to after the building.
    view: the CityView. Returns a list of (old_x, old_y) for the 16 slots."""
    return [(s.old_x, s.old_y) for s in view.slots]


def back_to_city(view, city, saved):
    """$9FBD-$A02B and $8CBD-$8CD4: the city map drawn again, its sprites back where they
    were (the first 8 drawn afresh), the numbers, the screen, the haunted colours, the
    copyright line. view: the CityView. city: the City, after City.after_building().
    saved: from save_city_slots."""
    view.back[:] = view.city_scr
    view.rebuild(city)                                  # $9294 (and the stomped buildings)
    for n, (s, (old_x, old_y)) in enumerate(zip(view.slots, saved)):
        s.old_x, s.old_y = old_x, (0 if n < 8 else old_y)
    view.slots[LOGO_SLOT].x, view.slots[LOGO_SLOT].y = city.x, city.y
    for n, g in zip(GHOST_SLOTS, city.ghosts):
        view.slots[n].x, view.slots[n].y = g
    for n, w in zip(WALKER_SLOTS, city.walkers):
        view.slots[n].x, view.slots[n].y = w
    view.slots[BAIT_SLOT].x, view.slots[BAIT_SLOT].y = city.bait
    for n, part in zip(PART_SLOTS, city.parts):
        view.slots[n].x, view.slots[n].y = part
    view.slots[BAIT_DOT_SLOT].x, view.slots[BAIT_DOT_SLOT].y = city.bait_dot
    view.screen = None
    view.printed = [None, None]
    view.print_numbers(city)                            # $8CBD
    view.engine.update()                                # $8CC3
    view.screen_attrs = bytearray(view.back[COPIED:END])
    view.screen = Screen(*screen_from_bytes(view.back))  # $8CC6: all of it
    for n in city.haunted():                            # $8CD1 ($9365): only the haunted ones, so the
        view.colour_building(n, *HAUNTED_COLOUR)        # sprites keep their colours
    if not city.scroller.left:                          # $8CD4
        print_bytes(view.back, view.font, view.text["copyright"], 0, MESSAGE_ROW)
        print_at(view.screen, view.font, view.text["copyright"], 0, MESSAGE_ROW)   # $AA73 prints on both
    return view.screen
