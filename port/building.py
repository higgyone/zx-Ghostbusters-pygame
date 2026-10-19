"""At the building (notes/08-the-building.md): the street scene where the men catch the ghost,
and GHQ. No drawing here, so it can be checked against the original step by step.

The scene is written as a Python generator that follows the game's code in order, stopping
(yield) at each drawing ($A8F3). Building.step() runs it to the next drawing. Its 16 sprite
slots are kept as positions and the picture each slot shows, and every drawing is recorded in
`ops` for the drawing code to repeat.
"""
from zxport import bcd

import trainer
from city import GHQ, HAUNTED, MARSHMALLOW_PARTS, QUIET, SPOT_OFFSETS, ZUUL, signed_distance

IMAGE_INTENSIFIER, LASER = 0x08, 0x01        # $D966 bits
# $A1AD: the 8 directions (0 up, then clockwise), as the bytes added to x and y
DIRS = ((0x00, 0xFE), (0x02, 0xFE), (0x02, 0x00), (0x02, 0x02), (0x00, 0x02), (0xFE, 0x02), (0xFE, 0x00), (0xFE, 0xFE))
# $A26B: the direction for each mix of keys (up 8, down 4, left 2, right 1); 8 = don't move
KEY_DIRS = (8, 2, 6, 8, 4, 3, 5, 8, 0, 1, 7, 8, 8, 8, 8, 8)
NO_MOVE = 8
# $D98A: a man's 4 pictures: facing (0 right, 1 left) + 2 for the second walking frame
MAN_FRAMES = (("man_standing", False), ("man_standing", True), ("man_walking", False), ("man_walking", True))
MAN_START = (0xDF, 0xB5)                 # $9B38: where the men walk in
MAN2_START = (0xE0, 0xB5)                # $9BD6
GHOST_START = (0xE0, 0x80)               # $9B65
MAN_X, MAN_Y = 0x18, (0x8E, 0xB6)        # $A1BD: the pavement (x up to the right-hand limit)
GHOST_X, GHOST_Y = (0x18, 0xE0), (0x38, 0x80)   # $A11E
TRAP_CARRIED = 8                         # $D99D while the first man carries the trap
STREAM_UP, STREAM_DOWN = 0xFA, 0x06      # $D9A1: the trap's stream rises, then falls, 6 pixels a step
CATCH = 0x0C                             # $9DE3: how close to the stream's top the ghost has to be
BUILDING_FRAMES = 2.4                    # a step takes about 2.1-2.6 frames (measured in the simulator)
ZUUL_FRAMES = 2.8                        # a step at Zuul (measured: notes/09)
GHQ_STEPS = (0x10, 0x10)                 # $A05F, $A073: steps before the second and third men come out
LASER_ROOM_GHQ = 10                      # $A0BD
# Zuul ($A426)
MARSHMALLOW_START = (0x80, 0xA0)         # $A44D: his place ($D96A, $D96B)
MARSHMALLOW_X = (0x70, 0x80)             # $A5D1: he wanders between these
ZUUL_MAN_START = (0xE0, 0xB4)            # $A461
ZUUL_WALK_IN, SQUASHED_WAIT = 40, 48     # $A46B, $A4BF: steps
DOOR_X, DOOR_Y = (0x78, 0x90), 0x90      # $A48D: the doorway
HIGH_ENOUGH = 0x6C                       # $A4A5: the man gets in while the Marshmallow Man's y is below this
ZUUL_REWARD = (0x50, 0x00)               # $A4F1: $5000


class Building:
    """The scene at the building beside the logo, made from the City (which it changes)."""

    def __init__(self, city):
        """Set up as $9A38-$9B48 do. city: the City."""
        c = self.city = city
        self.number = c.beside[0]                    # $D967
        self.right_limit = 0xE2                      # $D9D6
        self.style, self.colours = "brick", None     # the street's picture and its colours
        if self.number not in (GHQ, ZUUL):
            if c.random() & 1:                       # $9A4E
                self.style = "shop"
                while True:
                    awning = (c.random() & 7) + 1
                    if awning < 6:
                        break
                while True:
                    window = c.random() & 7
                    if window >= 4:
                        break
                self.colours = (awning + 0x38, window << 3)
            else:
                while True:
                    brick = c.random() & 0x38
                    if brick:
                        break
                c.street_colours = (brick, 0x38 if brick & 0x20 else 0x07)   # kept in the table ($A3EC, $A3F1)
        self.pos = [[0, 0] for _ in range(16)]
        self.kind = [MAN_FRAMES[0], MAN_FRAMES[1], MAN_FRAMES[2], MAN_FRAMES[3], ("man_slimed", False),
                     ("ghost", False), ("ghost", True), ("trap_open", False)] + [None] * 8
        self.count = self.steps = self.ghost_dir = 0     # $D99A, $D99B, $D99C
        self.trap = TRAP_CARRIED                     # $D99D
        self.facing1 = self.facing2 = 0              # $D99F, $D9A0
        self.speed = 0                               # $D9A1
        self.keys = set()
        self.sync = None
        self.ops = []                                # this step's drawings: ('ab88' or 'draw', slots)
        self.speech = None                           # the speech this step ends with
        self.done = False
        self.pos[0] = list(MAN_START)
        self.walk(0, 6)                              # $9B44
        self.state = c.buildings[self.number] if self.number < 20 else QUIET   # $D9D7
        self.ending = None                           # at Zuul: 'won' or 'lost' when it is over
        self.bob = 0                                 # $D979: the Marshmallow Man's bobbing
        self.step_frames = ZUUL_FRAMES if self.number == ZUUL else BUILDING_FRAMES
        if self.number == ZUUL:
            self.gen = self.zuul()
            return
        if self.number == GHQ:
            self.gen = self.ghq()
            return
        if self.state == HAUNTED:
            self.pos[5] = list(GHOST_START)
        self.gen = self.street()

    # --- stepping ----------------------------------------------------------------------

    def step(self, keys, sync=None):
        """Run to the next drawing. keys: set of 'up', 'down', 'left', 'right', 'fire',
        'status'. sync: the check script's hook ('draw', 'message')."""
        self.keys, self.sync, self.city.sync = keys, sync, sync
        self.ops, self.speech = [], None
        if self.done:
            return
        if "status" in keys and self.last == "draw":   # $A8F9, just after the last drawing
            self.city.status_line()
        try:
            self.last = next(self.gen)
        except StopIteration:
            self.last, self.done = None, True

    last = None                                  # what the last step stopped at: 'draw', 'wait' or 'speech'

    def record(self, op):
        """Note a sprite drawing ('ab88') or a drawing and screen copy ('draw')."""
        self.ops.append((op, [(x, y, k) for (x, y), k in zip(self.pos, self.kind)],
                         self.city.pk, self.city.money))

    def draw(self):
        """$A8F3: draw, copy to the screen, and stop until the next step."""
        self.record("draw")
        if self.sync:
            self.sync("draw")
        yield "draw"

    def tick_and_draw(self):
        """$A0E1: the PK tick, then the drawing; without the image intensifier the ghost
        (slot 5) is left out of some drawings."""
        c = self.city
        c.tick = (c.tick - 1) & 0xFF
        if c.tick == 0:
            c.tick = (-c.pk_high() & 0xFF) >> 2
            c.add_pk(1)
        if not c.equipment & IMAGE_INTENSIFIER and c.random() > signed_distance(self.count, 0):
            y, self.pos[5][1] = self.pos[5][1], 0
            yield from self.draw()
            self.pos[5][1] = y
        else:
            yield from self.draw()

    def fire(self):
        return "fire" in self.keys

    def wait_release(self):
        """A busy wait for Z to be let go: no drawing."""
        while self.fire():
            yield "wait"

    # --- movers ------------------------------------------------------------------------

    def walk(self, n, d):
        """$A1BD: move slot n 2 pixels in direction d (a man), turning first if he faces the
        other way, and step his walking frame."""
        c = self.city
        turned = False
        if d & 3:
            facing = d >> 2
            turned = facing != c.facing
            c.facing = facing
        if not turned:
            dx, dy = DIRS[d]
            p = self.pos[n]
            x = (p[0] + dx) & 0xFF
            if x < MAN_X or x >= self.right_limit:
                x = (x - dx) & 0xFF
            p[0] = x
            y = (p[1] + dy) & 0xFF
            if y < MAN_Y[0] or y >= MAN_Y[1]:
                y = (y - dy) & 0xFF
            p[1] = y
        self.steps = (self.steps + 1) & 0xFF
        self.kind[n] = MAN_FRAMES[c.facing | (self.steps & 2)]

    def walk_keys(self, n):
        """$A235: move man n with the keys."""
        k = self.keys
        d = KEY_DIRS[("up" in k) << 3 | ("down" in k) << 2 | ("left" in k) << 1 | ("right" in k)]
        if d != NO_MOVE:
            self.walk(n, d)

    def ghost_move(self):
        """$A11E: the ghost turns a little at random and moves 4 pixels, unless that takes it
        off its area; every 8 moves it swaps slots (5 and 6: it faces the other way)."""
        c = self.city
        r = c.random()
        d = self.ghost_dir + (2 if r & 0x80 else 0)
        self.ghost_dir = d = (d - 1) & 7
        src = 5 if self.pos[5][1] else 6
        self.count = (self.count + 1) & 0xFF
        dst = 6 if self.count & 8 else 5
        dx, dy = DIRS[d]
        x = ((dx << 1) + self.pos[src][0]) & 0xFF
        if x < GHOST_X[0] or x >= GHOST_X[1]:
            x = (x - 2 * dx) & 0xFF
        self.pos[dst][0] = x
        y = (((dy << 1) & 0xFF) + self.pos[src][1]) & 0xFF
        if y < GHOST_Y[0] or y >= GHOST_Y[1]:
            y = (y - 2 * dy) & 0xFF
        self.pos[src][1] = 0
        self.pos[dst][1] = y

    def ghost_slot(self):
        """The ghost's slot now (5, or 6 when 5 is hidden)."""
        return 5 if self.pos[5][1] else 6

    # --- the street ----------------------------------------------------------------------

    def street(self):
        """$9B6F-$9FBC: the scene at a building that isn't GHQ or Zuul."""
        c = self.city
        haunted = self.state == HAUNTED
        p, trap = self.pos, self.pos[7]
        while True:                                  # $9B6F: the first man and the trap
            yield from self.tick_and_draw()
            if haunted:
                self.ghost_move()
            self.walk_keys(0)
            if self.trap == 0:
                if self.fire():
                    break
                continue
            if self.trap == TRAP_CARRIED:
                trap[0] = (p[0][0] + (0xEA if c.facing else 0x0E)) & 0xFF
            trap[1] = (p[0][1] - self.trap + 0x0E) & 0xFF
            if self.trap != TRAP_CARRIED:
                self.trap -= 1
                continue
            if not self.fire():
                continue
            if not haunted:                          # $9F37: nothing here, back to the car
                self.trap = 0
                yield from self.carry_off()
                return
            self.trap = 7
        self.facing1 = c.facing                      # $9BD0: the second man
        p[1][:] = MAN2_START
        self.walk(1, 6)
        yield from self.wait_release()
        while True:
            yield from self.tick_and_draw()
            self.ghost_move()
            self.walk_keys(1)
            if self.fire():
                break
        yield from self.wait_release()
        if (yield from self.beams()):
            return
        caught = yield from self.open_trap()
        if caught:
            p[5][1] = 0                              # $9EDF
            self.speech = "ghostbusters"
            yield "speech"
            yield from self.carry_off()
        else:
            yield from self.slimed()

    def beams(self):
        """$9C03-$9D28: the beams, until Z or the backpacks run out. Returns True if the
        streams crossed (the scene is over)."""
        c, p = self.city, self.pos
        self.facing2 = c.facing
        self.kind[8:12] = [("beam_up", self.facing1 != 0)] * 4
        self.kind[12:16] = [("beam_up", self.facing2 != 0)] * 4
        for n in range(8, 16):
            p[n] = [0, 0]
        while True:
            yield from self.tick_and_draw()
            self.step_firing(0, self.facing1)
            self.step_firing(1, self.facing2)
            self.place_beam(0, 8, self.facing1)
            self.place_beam(1, 12, self.facing2)
            gap = 0x02 if self.facing1 == self.facing2 else 0x20
            if (p[11][0] - p[15][0]) & 0xFF < gap:   # $9CA9: crossed streams
                c.start_message(c.text["crossed"])
                if trainer.POWER not in trainer.on:
                    c.power = 0
                self.trap = 0
                self.kind[0] = self.kind[1] = ("man_slimed", False)
                return True
            g = self.ghost_slot()
            self.push_ghost(11, g, self.facing1)
            self.push_ghost(15, g, self.facing2)
            if self.count & 1 == 0:                  # the beams flicker
                for n in range(8, 16):
                    p[n][1] = 0
                if self.count & 7 == 0 and trainer.POWER not in trainer.on:
                    c.power = bcd.sub(c.power, 1)[0]
                    if c.power == 0:
                        c.start_message(c.text["no_power"])
                        return False
            self.ghost_move()
            if self.fire():
                return False

    def step_firing(self, n, facing):
        """$A27B: while firing, a man can step the way he faces."""
        self.city.facing = facing
        if facing == 0:
            if "right" in self.keys:
                self.walk(n, 2)
        elif "left" in self.keys:
            self.walk(n, 6)

    def place_beam(self, man, first, facing):
        """$A293: a man's beam: 4 sprites going up and out the way he faces."""
        p = self.pos
        bx, cx = (0x0E, 0x08) if facing == 0 else (0xFA, 0xF8)
        p[first] = [(p[man][0] + bx) & 0xFF, (p[man][1] - 0x0A) & 0xFF]
        for n in range(first + 1, first + 4):
            p[n] = [(p[n - 1][0] + cx) & 0xFF, (p[n - 1][1] - 0x10) & 0xFF]

    def push_ghost(self, tip, g, facing):
        """$A2CD: a ghost below a beam's end and near the line the beam would carry on along
        is turned left or right, away from it."""
        p = self.pos
        d = (p[g][1] - p[tip][1]) & 0xFF
        if d & 0x80:
            return
        c = d >> 1
        x = (p[tip][0] + c if facing & 1 else p[tip][0] - c) & 0xFF
        if signed_distance(x, p[g][0]) < 8:
            self.ghost_dir = 2 if x < p[g][0] else 6

    def open_trap(self):
        """$9D2B-$9E39: the trap's stream rises and falls; a ghost near its top is caught.
        Returns True if it was."""
        p = self.pos
        for n in range(8, 16):
            p[n][1] = 0
        self.record("ab88")
        self.kind[11] = ("trap_stream_top", False)
        self.kind[8:11] = [("trap_stream", False)] * 3
        for n in range(8, 12):
            p[n] = [0, 0]
        self.trap = 0
        self.speed = STREAM_UP
        top, trap = p[11], p[7]
        top[:] = [trap[0], (trap[1] - 0x14) & 0xFF]
        for n in (8, 9, 10):
            p[n][0] = (top[0] + 8) & 0xFF
        while True:
            yield from self.draw()
            top[1] = (top[1] + self.speed) & 0xFF
            gap = ((((trap[1] - top[1]) & 0xFF) - 0x0C) & 0xFF) >> 2
            y = top[1]
            for n in (8, 9, 10):
                y = (y + gap) & 0xFF
                p[n][1] = y
            if self.trap == 0:
                g = self.ghost_slot()
                if signed_distance(p[g][1], top[1]) < CATCH and signed_distance(p[g][0], top[0]) < CATCH:
                    self.trap = 1
                else:
                    self.ghost_move()
            if self.trap:                            # $9E00: the ghost rides with the stream
                p[5][:] = [top[0], top[1]]
                p[6][1] = 0
            d = (trap[1] - top[1]) & 0xFF
            if d < 0x14:
                if not self.speed & 0x80:
                    break
            elif d >= 0x68:
                self.speed = STREAM_DOWN
        self.right_limit = 0xFF
        saved = list(trap)                           # $A2FD: the trap shuts
        for n in range(7, 12):
            p[n][1] = 0
        self.record("ab88")
        self.kind[7] = ("trap_shut", False)
        trap[:] = saved
        return self.trap != 0

    def carry_off(self):
        """$9EEA-$9FBC: the men walk to the trap (after a catch), pick it up and walk off to
        the right; then the building is paid for."""
        c, p = self.city, self.pos
        while True:
            if self.trap:
                self.to_trap(0, 0, self.facing1)
                self.facing1 = c.facing
                self.to_trap(1, 0x18, self.facing2)
                self.facing2 = c.facing
                if not (signed_distance(p[7][0], p[0][0]) < 4 and signed_distance(p[7][0] + 0x18, p[1][0]) < 4):
                    yield from self.draw()
                    continue
                self.trap = 0
            if p[1][0] >= 0xF0 or p[0][0] >= 0xE0:
                break
            p[7][:] = [(p[0][0] + 0x0E) & 0xFF, (p[0][1] + 8) & 0xFF]
            self.walk(0, 2)
            self.walk(1, 2)
            yield from self.draw()
        n = self.number                              # $9F7A
        if c.buildings[n] == HAUNTED:
            c.buildings[n] = QUIET
            if trainer.TRAPS in trainer.on:
                pass
            elif c.equipment & LASER and c.laser:
                c.laser -= 1
            else:
                c.traps = (c.traps - 1) & 0xFF
            pay = c.timers[n] << 4
            c.timers[n] = 0
            c.add_money_bcd(pay >> 8, pay & 0xFF)

    def to_trap(self, n, offset, facing):
        """$A17F: walk man n towards the trap: up or down until level with it, then across
        until his x - offset is the trap's."""
        c, p = self.city, self.pos
        c.facing = facing
        d = (p[n][1] - p[7][1]) & 0xFF
        if d >= 4:
            self.walk(n, 4 if p[n][1] < p[7][1] else 0)
            return
        x = (p[n][0] - offset) & 0xFF
        if x != p[7][0]:
            self.walk(n, 2 if x < p[7][0] else 6)

    def slimed(self):
        """$9E43-$9F78: a missed ghost flies at one of the men and slimes him, then off."""
        c, p = self.city, self.pos
        man = p[0] if c.random() & 0x80 else p[1]
        g = p[5]
        if p[6][1]:
            g[1], p[6][1] = p[6][1], 0
        while True:
            if (g[0] - man[0]) & 0xFF >= 4:
                g[0] = (g[0] - 3 if g[0] >= man[0] else g[0] + 3) & 0xFF
            d = (g[1] - man[1]) & 0xFF
            if d < 4:
                if (g[0] - man[0]) & 0xFF < 4:
                    break
            else:
                g[1] = (g[1] + 3 if (d - 4) & 0x80 else g[1] - 3) & 0xFF
            yield from self.draw()
        p[4][:] = [man[0], (man[1] + 0x10) & 0xFF]
        man[1] = 0
        if trainer.MEN not in trainer.on:
            c.men = (c.men - 1) & 0xFF
        while True:
            g[0] = (g[0] - 3 if g[0] < 0x80 else g[0] + 3) & 0xFF
            if g[0] >= 0xF0:
                break
            yield from self.draw()
        self.speech = "he_slimed_me"
        yield "speech"

    # --- Zuul ----------------------------------------------------------------------------

    def zuul(self):
        """$A426-$A4F7: walk two of 3 men past the Marshmallow Man into Zuul. Sets ending."""
        c, p = self.city, self.pos
        self.kind[8:14] = list(MARSHMALLOW_PARTS)    # $93BD, with no colour of their own
        self.bob = self.count = 0                    # $D979, $D99A (men inside)
        c.spot = list(MARSHMALLOW_START)
        c.men = 3
        while True:
            p[4][1] = 0                              # $A45C: the next man
            p[0][:] = ZUUL_MAN_START
            for _ in range(ZUUL_WALK_IN):
                self.walk(0, 6)
                self.marshmallow()
                yield from self.draw()
            while True:                              # $A480: walk him to the door
                self.marshmallow()
                yield from self.draw()
                self.walk_keys(0)
                x, y = p[0]
                if y < DOOR_Y and DOOR_X[0] <= x < DOOR_X[1]:
                    break
            squashed = c.spot[1] >= HIGH_ENOUGH
            if not squashed:                         # $A4DE: in
                self.count += 1
                if self.count == 2:
                    c.add_money_bcd(*ZUUL_REWARD)
                    self.ending = "won"
                    return
            else:                                    # $A4A9: squashed
                p[4][:] = [p[0][0], (p[0][1] + 0x10) & 0xFF]
                p[0][1] = 0
                yield from self.draw()
                for _ in range(SQUASHED_WAIT):
                    self.marshmallow()
                    yield from self.draw()
            if not (squashed and trainer.MEN in trainer.on):
                c.men = (c.men - 1) & 0xFF           # $A4CB
            if (c.men + self.count) & 0xFF < 2:
                self.ending = "lost"
                return

    def marshmallow(self):
        """$A570: place the Marshmallow Man's pieces (arms and legs swap every 8 steps), then
        bob him up or down and move him 2 pixels left or right at random."""
        c, p = self.city, self.pos
        p[12][1] = p[13][1] = 0
        x, y = c.spot
        if self.bob & 0x10:
            p[10][1] = p[11][1] = 0
            slots = (8, 9, 12, 13)
        else:
            slots = (8, 9, 10, 11)
        for n, (dx, dy) in zip(slots, SPOT_OFFSETS):        # $94B4 down to $94AD
            p[n][:] = [(x + dx) & 0xFF, (y + dy) & 0xFF]
        self.bob = (self.bob + 2) & 0xFF
        t = self.bob & 0x3F
        if t >= 0x20:
            t ^= 0x3F
        c.spot[1] = 0x88 - t
        if c.random() & 0x80:
            if x + 2 < MARSHMALLOW_X[1]:
                c.spot[0] = x + 2
        elif x - 2 >= MARSHMALLOW_X[0]:
            c.spot[0] = x - 2

    # --- GHQ -----------------------------------------------------------------------------

    def ghq(self):
        """$A02E-$A0C4: three men walk out of GHQ; everything is restocked."""
        c, p = self.city, self.pos
        self.right_limit = 0xFF
        for n in range(3):
            p[n] = [0x80, 0]
        p[0][1] = 0x8F
        for _ in range(GHQ_STEPS[0]):
            self.ghq_walk(0)
            yield from self.draw()
        p[1][1] = 0x8F
        for _ in range(GHQ_STEPS[1]):
            self.ghq_walk(0)
            self.ghq_walk(1)
            yield from self.draw()
        p[2][1] = 0x8F
        while True:
            for n in range(3):
                self.ghq_walk(n)
            yield from self.draw()
            if not p[2][1]:
                break
        c.men, c.traps, c.power, c.laser = 3, c.traps_carried, 0x99, LASER_ROOM_GHQ

    def ghq_walk(self, n):
        """$A0C5: a man walks down and to the right, then right, and is gone past x $F0."""
        p = self.pos[n]
        if not p[1]:
            return
        self.walk(n, 3 if p[1] < 0xB4 else 2)
        if p[0] >= 0xF0:
            p[1] = 0
