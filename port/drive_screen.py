"""Drawing the drive to a building as the game does (notes/07-the-drive.md), in the city's back
buffer with the same sprite engine. The car isn't a sprite: its picture (with what is on its
roof) sits in the back buffer and is shifted half a byte at a time as it moves.
"""
from zxport.screen import Screen, pixel_address, screen_from_bytes
from zxport.text import print_bytes

from city_screen import GHOST_SLOTS, LOGO_SLOT, MESSAGE_ROW, TEXT_ROW
from drive import LOGO_DX
from sprites import ATTRS, COPIED, Slot, SpriteData

ROAD_INK = 0x3E                 # $9539: the back buffer's colours on the road (yellow ink, white paper)
ROOF_SLOT = 5                   # the slot the roof items are drawn with ($AE34), then left behind
# $99F4: what goes on the roof, in order: the $D966 bit (or 'bait', 'traps'), x, y, sprite, y offset
ROOF = ((0x10, 0xD8, 0x48, "pk_energy_detector", 0x04), (0x08, 0xD8, 0x68, "image_intensifier", 0x05),
        (0x02, 0xD8, 0x78, "marshmallow_sensor", 0xFE), ("bait", 0xC8, 0xA8, "ghost_bait", 0xFE),
        ("traps", 0xD4, 0x98, "trap_shop", 0x06), (0x04, 0xD8, 0x58, "ghost_vacuum", 0xFF),
        (0x01, 0xE8, 0xA8, "laser_confinement", 0x04))
CAR_TOP, CAR_ROWS = 40, 0x79    # $DA90: the pixel rows the car's picture is shifted on
CAR_ATTR_ROW, CAR_ATTR_ROWS = 5, 15   # $99A4: the colour rows coloured round the car
PAINT_ROW, PAINT_ROWS = 6, 12   # $9994: a lane column coloured with the car's colour
LANE_COLUMNS = (10, 21)         # the two columns of lane markings
LANE_MARK = 0x7E                # bright white
# the car's x range that leaves a lane marking out: (column 10, column 21), for the row the
# marking number points at, and for the rows past it
LANE_GAPS = {"at": ((0x28, 0x5C), (0x80, 0xB4)), "past": ((0x20, 0x64), (0x78, 0xBC))}


class DriveView:
    """The drive's screen, made from the CityView (its back buffer, slots and text)."""

    def __init__(self, view, car_scr, sprites):
        """view: the CityView. car_scr: the 6912 bytes of drive_car_n.scr for the car bought.
        sprites: {roof item sprite name: zxport Sprite}."""
        self.view, self.car_scr = view, car_scr
        self.roof = {name: SpriteData(s) for name, s in sprites.items()}
        self.back, self.slots, self.engine = view.back, view.slots, view.engine
        self.screen = view.screen

    def start(self, drive):
        """$952D-$963D: the road, the car and its roof, PK and money. drive: a Drive."""
        c, v = drive.city, self.view
        for s in self.slots:                                          # $ADE9: everything off
            s.x = s.y = 0
        self.engine.update()
        self.back[:ATTRS] = self.car_scr[:ATTRS]                      # $9971, $9539, $A741, $9948, $99A4
        self.back[ATTRS:COPIED] = self.car_scr[ATTRS:COPIED]          # (the bottom 3 colour rows stay)
        if not c.scroller.left:                                       # $942B
            print_bytes(self.back, v.font, v.text["copyright"], 0, MESSAGE_ROW)
        self.draw_roof(c)
        v.screen = None                                               # (printed into the back buffer, then copied)
        print_bytes(self.back, v.font, v.text["pk_label"], 0, TEXT_ROW)   # $931C
        v.printed = [None, None]
        v.print_numbers(c)
        self.show()                                                   # $962D (the screen's pixels match the back buffer's)

    def draw_roof(self, c):
        """$9587: draw what was bought on the roof, with slot 5, and leave it there."""
        old = self.slots[ROOF_SLOT]
        for bit, x, y, name, dy in ROOF:
            if bit == "bait":
                if not c.bait_left:
                    continue
            elif bit == "traps":
                ys, count = [], 0
                while True:                                           # one above another
                    ys.append((y - count + 6) & 0xFF)
                    count = (count + 4) & 0xFF
                    if count == (c.traps_carried * 4) & 0xFF:
                        break
            elif not c.equipment & bit:
                continue
            if bit != "traps":
                ys = [(y + dy) & 0xFF]
            slot = Slot(self.roof[name])            # (their headers leave the colours alone)
            self.slots[ROOF_SLOT] = self.engine.slots[ROOF_SLOT] = slot
            for item_y in ys:
                slot.x, slot.y = x, item_y
                self.engine.update()
                slot.y = slot.old_y = 0
        self.slots[ROOF_SLOT] = self.engine.slots[ROOF_SLOT] = old
        old.x = old.y = old.old_x = old.old_y = 0

    def show(self):
        """$ADB2: the back buffer to the screen (but not its bottom 3 colour rows)."""
        self.screen = self.view.screen = Screen(*screen_from_bytes(self.back[:COPIED] + self.view.screen_attrs))

    def update(self, drive):
        """After a Drive.step: the drawing parts of the same step. Returns the Screen."""
        c = drive.city
        self.view.print_numbers(c)
        if drive.paint is not None:
            self.paint(drive.paint, drive.colour)
        for n in (*GHOST_SLOTS, LOGO_SLOT):                           # $96B1
            self.slots[n].y = 0
        self.engine.update()
        if drive.shift:
            self.shift_car(drive.x, drive.shift)
            self.colour_car(drive.x, drive.colour)
        logo = self.slots[LOGO_SLOT]
        logo.x, logo.y = (drive.x + LOGO_DX) & 0xFF, drive.car_y
        for n, (x, y) in zip(GHOST_SLOTS, drive.ghost_slots()):
            self.slots[n].x, self.slots[n].y = x, y
        self.engine.update()
        self.lanes(drive)
        self.engine.update()                                          # $A8F3 (nothing has moved)
        self.show()
        return self.screen

    def paint(self, column, colour):
        """$9994: colour 12 cells of a lane column with the car's colour."""
        for r in range(PAINT_ROW, PAINT_ROW + PAINT_ROWS):
            self.back[ATTRS + r * 32 + column] = colour

    def shift_car(self, x, way):
        """$96F7/$9735: move the car's picture half a byte left (RLD) or right (RRD).
        x: the car's new x."""
        b = self.back
        for r in range(CAR_TOP, CAR_TOP + CAR_ROWS):
            base = pixel_address(0, r)
            a = 0
            if way == "left":
                o = base + (x >> 3) + 7
                for i in range(10):
                    v = b[o - i]
                    b[o - i] = (v << 4 | a) & 0xFF
                    a = v >> 4
            else:
                o = (base & 0xFF00) | ((base & 0xFF) + (x >> 3) - 3) & 0xFF
                for i in range(11):
                    v = b[o + i]
                    b[o + i] = a << 4 | v >> 4
                    a = v & 0x0F

    def colour_car(self, x, colour):
        """$99A4: colour the cells round the car: the car's colour, yellow at each end."""
        b = self.back
        o = ATTRS + CAR_ATTR_ROW * 32 + (x >> 3) - 3
        for _ in range(CAR_ATTR_ROWS):
            for i in range(12):
                b[o + i] = b[o + i] & 0xC0 | (ROAD_INK if i in (0, 11) else colour)
            o += 32

    def lanes(self, drive):
        """$97C2: the lane markings move down a row: one row of each column is marked (left out
        where the car is) and the row 11 behind it is cleared. Rows 16-21 are marked too, for
        the first 6 of every 16 steps."""
        b, x = self.back, drive.x
        r = drive.count & 0x0F

        def mark(row, col, always, at):
            """Mark a cell: always, or unless the car's x is in the gap ('at' or 'past')."""
            low, high = LANE_GAPS["at" if at else "past"][col]
            if always or not low <= x < high:
                b[ATTRS + row * 32 + LANE_COLUMNS[col]] = LANE_MARK

        for col in (0, 1):
            mark(r, col, r < drive.lane_a, r == drive.lane_a)
        if r < 6:
            for col in (1, 0):
                mark(r + 16, col, r >= drive.lane_b, r == drive.lane_b - 1)
        r2 = (drive.count + 0x0B) & 0x0F
        rows = (r2, r2 + 16) if r2 < 6 else (r2,)
        for row in rows:
            for col in LANE_COLUMNS:
                b[ATTRS + row * 32 + col] &= 0x3F
