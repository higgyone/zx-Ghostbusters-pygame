"""The start ($8300-$87F6, notes/10-the-start.md): the controller menu, the title and its
song, your name and account, the car shop and the equipment shop. Then the city map.

Start.step() runs it to its next stopping point, as the other scenes' steps do. What each
step stopped at is in Start.last, so the game knows how long it takes:
- 'char'  a character typed by $8B92 (CHAR_FRAMES), with a click;
- 'frame' a frame spent waiting for a key;
- 'key'   a key taken in a typed line (a frame, with a click);
- 'speech' (Start.speech names it), 'song' (the song starts), 'word' (a frame where a word
  turned white), 'song_end' (ENTER stopped it);
- 'pass'  a pass of the equipment shop, drawn ($85C7); 'lift' a forklift step ($8917).
"""
import trainer
from building_screen import paint
from sprites import Slot, SpriteData, SpriteEngine
from text_screen import ATTRS, COPIED, TextScreen, pixel_row
from zxport.text import print_bytes

SCAN = " \nMNB\rLKJHPOIUY09876" "12345QWERTASDFG\nZXCV"   # $887F's order; \n: either SHIFT ($0A)
RUB_OUT = "\n"
LINE = 20                                  # $88C1: the most characters in a typed line
BORDER_BYTE = 0xD9CB - 0xD9B6              # where a long line reaches the border colour
START_MONEY = 10000                        # $8447: the bank's advance
NAME_RED = [(0, 12, 21, 1, 0x32)]          # $83A7: the name in red
NUMBER_RED = [(0, 15, 9, 1, 0x32)]         # $83E6: the account number in red
MONEY_RED = [(9, 13, 23, 1, 0x32)]         # $84DB: your money in the car shop
MONEY_AT = (0x19, 22)                      # $AB2E: where $AAFB prints the money
SHOP_ROW = 0x68 // 8                       # $84F9, $8583: the row the shops' last text starts
CARS = ((0x20, 5), (0x48, 9), (0x60, 11), (0x99, 7))   # $89E1: price (hundreds, BCD), items carried
VIEW_BORDER = 0                            # $8518: OUT ($FE),$38

# the equipment ($99F4, one column each): equipment bit, place in the car (x, y), price (hundreds,
# BCD); and $9A25: how far below the forklift it rides
ITEMS = ((0x10, 0xA8, 0x48, 0x04), (0x08, 0xA8, 0x68, 0x08), (0x02, 0xA8, 0x78, 0x08),
         (0x00, 0x98, 0xA8, 0x04), (0x00, 0xA4, 0x98, 0x06), (0x04, 0xA8, 0x58, 0x05),
         (0x01, 0xB8, 0xA8, 0x80))
CARRY_Y = (0x04, 0x05, 0xFE, 0xFE, 0x06, 0xFF, 0x04)
BAIT, TRAP, NONE = 3, 4, 0xFF
VACUUM, LASER = 0x04, 0x01                 # their equipment bits
BAIT_BOUGHT = 5                            # $872F
ROW_X, ROW_Y = (0x28, 0x28, 0x28), (0x48, 0x68, 0x88)   # $9A2C: the forklift's place at rows 0-2
CAR_ROW = 3
LIFT, LIFT_CARRYING, FORK = 7, 8, 9        # slots: the forklift empty, carrying (mirrored), its fork
LIFT_START, FORK_START = (0x28, 0x48), (0x10, 0x55)    # $89BA
ITEM_X = 0x10                              # $84C5, $89AA
NEW_TRAP = (0x10, 0x6E)                    # $8716
# what each page shows ($858B, $8788, $87C9): (slot, y, row, equipment bit it needs to be
# without, or None)
PAGES = {1: [(0, 0x4C, 0, 0x10), (1, 0x6D, 1, 0x08), (2, 0x86, 2, 0x02)],
         2: [(BAIT, 0x46, 0, "bait"), (TRAP, 0x6E, 1, None), (5, 0x87, 2, 0x04)],
         3: [(6, 0x4C, 0, 0x01)]}
SPRITES = ("pk_energy_detector", "image_intensifier", "marshmallow_sensor", "ghost_bait", "trap_shop",
           "ghost_vacuum", "laser_confinement", "forklift", "forklift", "forklift_fork")
LIFT_COLOUR = (0x02, 0xF8)                 # the forklift's header: red ink

# the song's words ($AEE7): row 18 sung (green, the word white), row 20 next (red)
SUNG_ROW, NEXT_ROW = 18, 20
SUNG_INK, NEXT_INK, WORD_INK = 0x04, 0x02, 0x47
FIRST_COL = 9                              # $AEE8: $5A49


def bcd_bytes(money):
    """Money in dollars as the BCD bytes ($D965, $D964). Returns (hi, mid)."""
    d = f"{money // 100 % 10000:04d}"
    return int(d[:2], 16), int(d[2:], 16)


def from_bcd(hi, mid):
    """Dollars from the BCD bytes ($D965, $D964), even if they aren't really BCD."""
    return (((hi >> 4) * 10 + (hi & 15)) * 100 + (mid >> 4) * 10 + (mid & 15)) * 100


class Start(TextScreen):
    """The start, on its own back buffer and screen, with the shop's sprite slots."""

    def __init__(self, text, font, pictures, sprites, song, song_seconds=0.0):
        """text: assets/text.json. font: zxport.text.load_font. pictures: {'title', 'car_1'..'car_4':
        .scr bytes}. sprites: {name: zxport Sprite}. song: assets/song.json. song_seconds: the
        recording's length."""
        super().__init__(font)
        self.text, self.pictures, self.song_data, self.song_seconds = text, pictures, song, song_seconds
        self.data = [SpriteData(sprites[name], n == LIFT_CARRYING) for n, name in enumerate(SPRITES)]
        self.slots = [Slot() for _ in range(16)]
        self.engine = SpriteEngine(self.back, self.slots)
        self.buffer = [0] * 300                    # $D9B6: the typed line (and what follows it)
        self.keys, self.chars = set(), set()       # held now: joystick names, and characters
        self.last, self.speech, self.done = None, None, False
        self.phase = None                          # what it waits for: 'menu', 'keys', 'song', 'line' or 'shop'
        self.asking, self.line_open = None, False  # (for the check tool)
        self.waiting = None                        # in a typed line: 'release' or 'press'
        self.words = True                          # $8390: the song's words are only shown once
        self.controls = 0                          # $D904
        self.name = " " * LINE                     # $D9A2
        self.money = self.start_money = START_MONEY
        self.car = 0                               # $D983
        self.capacity = 0                          # $D9D5: room left in the car
        self.equipment = self.traps = self.bait = 0   # $D966, $D9CA, $D96E
        self.carried = NONE                        # $D9CC: what the forklift carries
        self.gen = self.run()

    # --- running ------------------------------------------------------------------------

    def step(self, keys=(), chars=()):
        """Run to the next stopping point. keys: joystick names held ('up', 'down', 'left',
        'right', 'fire'). chars: keys held as characters (see SCAN)."""
        if self.done:
            return
        self.keys, self.chars = set(keys), set(chars)
        try:
            self.last = next(self.gen)
        except StopIteration:
            self.last, self.done = None, True

    def key(self):
        """$887F: the first key held, in the game's order, or None."""
        return next((ch for ch in SCAN if ch in self.chars), None)

    def run(self):
        """$8309-$87F6."""
        yield from self.menu()
        yield from self.title()
        while True:
            money = yield from self.name_and_account()
            if money is not None:
                break
        self.money = self.start_money = money        # $8451
        self.equipment = self.traps = self.bait = 0
        for n, s in enumerate(self.slots):           # $846B-$84D3: the shop's sprites
            s.data = self.data[n] if n < len(self.data) else None
            s.colour = LIFT_COLOUR if n in (LIFT, LIFT_CARRYING) else None
            s.x = ITEM_X if n < 8 else 0
            s.y = 0
        self.engine.update()
        yield from self.car_shop()
        yield from self.equipment_shop()

    # --- the menu and the title ---------------------------------------------------------

    def menu(self):
        """$834E-$836D: pick the controls; the keyboard's are shown until ENTER."""
        yield from self.message(self.text["menu"])
        self.phase = "menu"
        while True:
            k = self.key()
            if k and "1" <= k <= "4":
                break
            yield "frame"
        self.controls = int(k) - 1
        if self.controls == 0:
            yield from self.message(self.text["keys"])
            self.phase = "keys"
            while "\r" not in self.chars:
                yield "frame"

    def title(self):
        """$836E-$838D: the logo, "Ghostbusters!" and the laugh, then the song."""
        self.clear()
        self.back[:COPIED] = self.pictures["title"][:COPIED]
        self.copy()
        for name in ("ghostbusters", "laugh"):
            self.speech = name
            yield "speech"
        yield from self.song()
        self.words = False

    def song(self):
        """$AEE7: the song, with its words (the first time). ENTER stops it."""
        times = self.song_data["words"] if self.words else []
        if self.words:
            self.lines = ["\x00\x00"] + self.song_data["lines"]   # (the list's first entry is never shown)
            self.calls = 0                            # $B5E5: how far down the list
            self.sung = self.next_col = FIRST_COL     # $B5E8, $BA4E: colour cells from row 18
            self.scan = ""                            # $B5DF: the line being sung, from the next word
            self.song_colours()                       # $B5ED
            self.next_line()                          # $B63F, twice
            self.next_line()
            self.shown()
        self.phase = "song"
        yield "song"
        # the song's moments: a word turning white (before its note), the end of a note
        # ($AF85: the colours go back, then ENTER stops the song)
        events = sorted([(t, 1) for t in times] + [(t, 2) for t in self.song_data["notes"]])
        frame = 0
        for when, what in events:
            while frame < when * 50:
                yield "frame"
                frame += 1
            if what == 1:
                self.word()
                self.shown()
                yield "word"
                frame += 1
            else:
                if self.words:
                    self.song_colours()
                    self.shown()
                if "\r" in self.chars:
                    yield "song_end"
                    return
        while frame < self.song_seconds * 50:
            yield "frame"
            frame += 1

    def song_colours(self):
        """$B5ED: row 18 green, row 20 red."""
        for row, ink in ((SUNG_ROW, SUNG_INK), (NEXT_ROW, NEXT_INK)):
            self.scr[ATTRS + row * 32:ATTRS + row * 32 + 32] = bytes([ink]) * 32

    def word(self):
        """$B605: the next word turns white; at the end of a line, the next line first."""
        self.song_colours()
        while True:
            n = 0
            for i, ch in enumerate(self.scan):
                if ord(ch) < 0x20:
                    break
                n += 1
                if ord(ch) >= 0x60:                   # its last letter
                    self.scan = self.scan[i + 1:]
                    for c in range(self.sung, self.sung + n):
                        o = ATTRS + SUNG_ROW * 32 + c
                        if o < len(self.scr):
                            self.scr[o] = self.scr[o] & 0xF8 | WORD_INK
                    self.sung += n
                    return
            self.next_line()

    def next_line(self):
        """$B63F: row 20 moves up to row 18, and the next line comes in on row 20."""
        self.sung = self.next_col
        self.scan = self.line_at(self.calls)[1:]
        line = self.line_at(self.calls + 1)
        self.calls += 1
        for y in range(8):                            # the pixels of text row 20 up to row 18
            src, dst = pixel_row(NEXT_ROW * 8 + y), pixel_row(SUNG_ROW * 8 + y)
            self.scr[dst:dst + 32] = self.scr[src:src + 32]
        self.next_col, at = 0, 0
        for _ in range(ord(line[0])):                 # the spaces before
            self.song_char(at, " ")
            at += 1
            self.next_col += 1
        for ch in line[1:-1]:
            self.song_char(at, chr(ord(ch) - 0x20) if ord(ch) >= 0x60 else ch)
            at += 1
        for _ in range(ord(line[-1])):                # $B6A7: and after
            self.song_char(at, " ")
            at += 1

    def line_at(self, n):
        """Line n of the song's words (a blank one past the end)."""
        return self.lines[n] if n < len(self.lines) else "\x00\x00"

    def song_char(self, at, ch):
        """$B6B7: a character from the ROM's font straight onto the screen, at cell number at
        from the start of row 20 (it runs on into row 21 past the end of the row)."""
        row = NEXT_ROW + at // 32
        if row < 24:
            print_bytes(self.scr, self.font, ch, at % 32, row)

    # --- the name and the account -------------------------------------------------------

    def line(self, asking):
        """$88C1: a typed line, into the buffer. Each key is taken once it has been let go
        and pressed again; SHIFT rubs out. asking: what for ('name', 'account', 'number',
        'car'), kept in self.asking for the check tool. Returns the buffer as a string.

        The game counts 20 characters down in B, but rubbing out prints a space with $AA3A,
        which leaves B at 0. So after a rub-out the count starts again from 256, and a long
        line runs on past the buffer into the game's other variables. The port keeps the one
        that shows: $D9CB, the border colour the clicks set."""
        b, pos = LINE, 0
        self.phase, self.asking, self.line_open = "line", asking, True
        while True:
            self.waiting = "release"
            while self.key():                         # $88B4
                yield "frame"
            self.waiting = "press"
            while not self.key():
                yield "frame"
            self.waiting = None
            k = self.key()
            self.click()
            if k == RUB_OUT:
                if pos:
                    self.col -= 1
                    self.put(" ")
                    self.col -= 1
                    pos -= 1
                    b = 0
                yield "key"
                continue
            self.buffer[pos] = ord(k)
            if pos == BORDER_BYTE:
                self.border_colour = ord(k)
            if k == "\r":
                self.line_open = False
                yield "key"
                break
            self.put(k)
            pos += 1
            b = (b - 1) & 0xFF
            self.line_open = b > 0
            yield "key"
            if not b:
                break
        return "".join(chr(c) for c in self.buffer[:LINE])

    def name_and_account(self):
        """$83A1-$8450. Returns the money to start with, or None if the account number was
        wrong (the name is asked for again)."""
        from account import check_byte
        yield from self.message(self.text["name"])
        paint(self.back, NAME_RED)
        self.copy()
        typed = yield from self.line("name")
        name = typed.split("\r")[0][:LINE] if "\r" in typed else typed
        self.name = name.ljust(LINE)[:LINE]
        yield from self.message(self.text["account_q"])
        answer = yield from self.line("account")
        if answer[0] != "Y":
            yield from self.message(self.text["welcome"])
            return START_MONEY
        paint(self.back, NUMBER_RED)
        yield from self.message(self.text["account_number_q"])
        number = yield from self.line("number")
        n = 0
        for ch in number[:8]:
            n = n << 3 | ord(ch) & 7
        mid, check, hi = n >> 16 & 0xFF, n >> 8 & 0xFF, n & 0xFF
        if check != check_byte(hi, mid, self.name):
            yield from self.message(self.text["invalid"])
            return None
        return from_bcd(hi, mid)

    # --- the car shop -------------------------------------------------------------------

    def car_shop(self):
        """$84D5-$8588: look at the cars, then buy one."""
        while True:
            yield from self.message(self.text["cars"])
            paint(self.back, MONEY_RED)
            self.money_here()
            self.row = SHOP_ROW
            yield from self.message(self.text["car_prompt"])
            while True:
                typed = yield from self.line("car")
                if typed[0] == " ":                   # look at a car
                    n = ord(typed[1]) - 0x31
                    if not 0 <= n <= 3:               # (the game takes " 0" too, and shows rubbish)
                        break
                    self.car_picture(n)
                    self.border = VIEW_BORDER
                    self.col = self.row = 0
                    yield from self.message(self.text[f"car_{n + 1}"])
                    continue
                n = ord(typed[0]) - 0x31
                if not 0 <= n <= 3:
                    break
                price, self.capacity = CARS[n]
                hi, mid = bcd_bytes(self.money)
                if not hi and mid < price:
                    break
                if price == 0x99:                     # $15000: two takes, $9900 and $5100
                    if hi < 2 and mid < 0x50:
                        break
                    self.take(9900)
                    self.take(5100)
                else:
                    self.take(from_bcd(0, price))
                self.car = n
                self.car_picture(n)
                self.col, self.row = MONEY_AT
                self.money_here()
                self.row = SHOP_ROW
                yield from self.message(self.text["forklift"])
                return

    def money_here(self):
        """$AB32 with $D96C/$D96D set to space and $: the money at the print position."""
        self.print_money(self.money)

    def take(self, dollars):
        """$AB58: money off, stopping at $0 (not with the trainer's infinite money)."""
        if trainer.MONEY not in trainer.on:
            self.money = max(0, self.money - dollars)

    def car_picture(self, n):
        """$87F9: the car's picture over the whole screen, in its colour."""
        self.clear()
        pic = self.pictures[f"car_{n + 1}"]
        self.back[:] = pic
        self.scr[ATTRS:] = pic[ATTRS:]
        self.border_colour = (pic[ATTRS] >> 3) & 7
        self.copy()

    # --- the equipment shop -------------------------------------------------------------

    def equipment_shop(self):
        """$858B-$87F6: the forklift carries things into the car. E ends it, with a trap."""
        page = 1
        self.phase = "shop"
        while True:
            yield from self.page(page)
            while True:
                self.engine.update()                  # $85C7: $A8F3
                self.copy()
                yield "pass"
                yield from self.shop_keys()
                k = self.key()
                if k in ("1", "2", "3"):
                    page = int(k)
                    break
                if k == "E" and self.traps:
                    return

    def page(self, page):
        """$89A7 and a page's text and things for sale."""
        for s in self.slots:                          # $ADE9
            s.x = s.y = 0
        self.engine.update()
        for n in range(7):
            self.slots[n].x = ITEM_X
        self.slots[LIFT].x, self.slots[LIFT].y = LIFT_START
        self.slots[FORK].x, self.slots[FORK].y = FORK_START
        self.lift_row = self.back_row = 0             # $D9D0, $D9D1
        self.rows = [NONE] * 3                        # $D9CD-$D9CF
        yield from self.message(self.text[f"page_{page}"])
        for slot, y, row, without in PAGES[page]:
            have = self.bait if without == "bait" else without is not None and self.equipment & without
            if not have:
                self.slots[slot].y = y
                self.rows[row] = slot
        # $85C2, $87BD, $87E4: nothing carried (but not on page 2 with the vacuum bought, or
        # page 3 with the laser)
        if page == 1 or not self.equipment & (VACUUM if page == 2 else LASER):
            self.carried = NONE

    def shop_keys(self):
        """$85CA-$877A: the joystick moves the forklift; fire picks up, puts down or buys."""
        k = self.keys
        if self.carried == NONE:
            if "up" in k and self.lift_row not in (0, CAR_ROW):
                yield from self.lift(self.lift_row - 1)
            if "down" in k and self.lift_row + 1 < CAR_ROW:
                yield from self.lift(self.lift_row + 1)
        left = True
        if self.lift_row != CAR_ROW and "right" in k:
            if self.carried == NONE:
                left = False                          # ($8607: straight on to fire)
            else:
                bit, car_x, car_y, price = ITEMS[self.carried]
                if self.carried == TRAP:
                    car_y = (car_y - 4 * self.traps) & 0xFF
                self.car_place = (car_x, car_y)
                yield from self.lift(CAR_ROW)
        if left and self.lift_row == CAR_ROW and "left" in k:
            yield from self.lift(self.back_row)
        yield from self.fire()

    def fire(self):
        """$8648-$877A."""
        if "fire" not in self.keys:
            return
        if self.carried == NONE:                      # $8737: pick up
            if self.lift_row != CAR_ROW:
                self.back_row = self.lift_row
                item = self.rows[self.lift_row]
                if item != NONE:
                    self.carried = item
                    self.rows[self.lift_row] = NONE
                    lift, carrying, fork = (self.slots[n] for n in (LIFT, LIFT_CARRYING, FORK))
                    carrying.x = lift.x
                    fork.x = self.slots[item].x = (lift.x + 0x10) & 0xFF
                    carrying.y, lift.y = lift.y, 0
        elif self.lift_row != CAR_ROW:                # $865E: put down
            self.rows[self.lift_row] = self.carried
            self.put_down()
        else:                                         # $86A4: buy
            item = self.carried
            bit, car_x, car_y, price = ITEMS[item]
            hi, mid = bcd_bytes(self.money)
            if self.capacity and (hi or mid >= price):
                self.take(from_bcd(0, price))
                self.col, self.row = MONEY_AT
                self.money_here()
                self.capacity -= 1
                self.equipment |= bit
                s = self.slots[item]
                s.y = s.old_y = 0                     # (left drawn in the car)
                if item == TRAP:
                    s.x, s.y = NEW_TRAP
                    self.rows[1] = TRAP
                    self.traps += 1
                elif item == BAIT:
                    self.bait = BAIT_BOUGHT
                self.put_down()
        while "fire" in self.keys:                    # $8777: till fire is let go
            yield "frame"

    def put_down(self):
        """$8667: the forklift lets go of what it carries."""
        lift, carrying, fork = (self.slots[n] for n in (LIFT, LIFT_CARRYING, FORK))
        item = self.slots[self.carried]
        self.carried = NONE
        lift.x = carrying.x
        fork.x = (carrying.x - 0x18) & 0xFF
        if self.lift_row != CAR_ROW:
            item.x = (fork.x - 8) & 0xFF
        lift.y, carrying.y = carrying.y, 0

    def lift(self, row):
        """$8917: the forklift goes to a row (or the car), 4 pixels a step, drawn each step."""
        to_x, to_y = self.car_place if row == CAR_ROW else (ROW_X[row], ROW_Y[row])
        item = self.slots[self.carried] if self.carried != NONE else self.slots[15]
        lift = self.slots[LIFT] if self.slots[LIFT].y else self.slots[LIFT_CARRYING]
        fork = self.slots[FORK]
        while True:
            if lift.y != to_y:
                y = (lift.y + 4 if lift.y < to_y else lift.y - 4) & 0xFF
                if item.y:
                    item.y = (CARRY_Y[self.carried] + y) & 0xFF
                lift.y = y
                fork.y = (y + 0x0D) & 0xFF
            if lift.x == to_x:
                if lift.y == to_y:
                    break
            else:
                x = (lift.x + 4 if lift.x < to_x else lift.x - 4) & 0xFF
                lift.x = x
                item.x = fork.x = (x + 0x10 if self.carried != NONE else x - 0x18) & 0xFF
            self.engine.update()
            self.copy()
            yield "lift"
        self.lift_row = row

