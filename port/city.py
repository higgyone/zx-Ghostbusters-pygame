"""The city map's rules (notes/05-city-map.md), with no drawing, so they can be checked
against the original pass by pass. One call to step() is one pass of the game's loop
($8CD7).

All of the city map is here: the logo on the roads, the random numbers, hauntings, PK energy,
the roaming ghosts, the Keymaster and the Gatekeeper, alerts, bait, the equipment lights,
fire beside a building, the messages along the bottom line, the end, and the Marshmallow Man's
two scenes (notes/06-marshmallow-scenes.md), after which the city map carries on. During a
scene one call to step() is one step of the scene (see step_frames). What happens next (the
drive, the game over) is reported in City.event for other parts of the port.
"""
from zxport import bcd

import trainer

ROAD_ROWS = (0x34, 0x5C, 0x84, 0xAC)              # y of the horizontal roads
ROAD_COLUMNS = (0x18, 0x48, 0x78, 0xA8, 0xD8)     # x of the vertical roads
LEFT, RIGHT, TOP, BOTTOM = 0x18, 0xD8, 0x34, 0xAC  # the ends of the roads
LOGO_START = (0x60, 0xAC)                          # $8C77
STEP = 2                                           # pixels per pass

ZUUL, GHQ = 10, 17                                 # building numbers (row x 4 + column)
QUIET, STIRRING, HAUNTED = 0, 1, 2
HAUNT_TIME = 0x99                                  # a haunted building's timer starts here
GHOST_STARTS = ((0x01, 0xF0), (0x20, 0x01), (0xF0, 0xDC), (0xEF, 0x10))   # $9492: the 4 roaming ghosts
ZUUL_SPOT = (0x90, 0x70)                           # where the roaming ghosts head
WALKER_STARTS = ((0x00, 0xB0), (0x00, 0x38))       # the Keymaster and the Gatekeeper ($8CA2)
WALKER_TARGET_X = (0x98, 0x88)                     # $94AB: x of each one's way into Zuul
WALKER_COLUMNS = (0x18, 0x48, 0x78, 0xA8, 0xD8)    # their crossroads ($91EB)
WALKER_ROWS = (0x38, 0x60, 0x88, 0xB0)
RIGHT_, LEFT_, DOWN_, UP_ = 1, 2, 4, 8             # their directions
REDRAW_EVERY = 0x40                                # passes between colour redraws ($9196)
SPOT_OFFSETS = ((0xF8, 0xF8), (0x08, 0xF8), (0xF8, 0x08), (0x08, 0x08))  # $94AD: each ghost's place
# the Marshmallow Man's pieces in sprite slots 8-13: (sprite, mirrored)
MARSHMALLOW_PARTS = (("marshmallow_1", False), ("marshmallow_2", False), ("marshmallow_3", False),
                     ("marshmallow_3", True), ("marshmallow_4", True), ("marshmallow_4", False))
NONE = 0x15                                        # $D967 when no building is beside the logo
PK_DETECTOR, MARSHMALLOW_SENSOR = 0x10, 0x02       # $D966 bits
DETECTOR_LIGHT = (0x03, 0xF8)                      # magenta ink on a stirring building ($926A)
SENSOR_LIGHT = (0x38, 0xC7)                        # white paper on the building beside the logo
STATUS_DIGITS = (0x12, 0x13, 0x24, 0x35)           # $7779, $777A, $778B, $779C in the status line
PASS_FRAMES = 50 / 22                              # a pass takes about 2.27 frames (measured in the simulator)
ATTACK_FRAMES = 16                                 # frames between the attack's steps ($8A0F)
MAYOR_FRAMES = 2.9                                 # a step of the walk to the bait (measured: one draw)
MAYOR_WAIT = 100                                   # frames the mayor's reward waits ($8B2E)
DAMAGE, REWARD = 4000, 2000                        # dollars ($8A94, $8B28)
MAX_MONEY = 999999                                 # $AB23: adding stops at $999999


class Scroller:
    """The bottom line's messages ($8B69, moved along by the interrupt at $A6A6, 50 times a
    second): 31 spaces, the message, then the copyright line, shown 32 characters at a time,
    half a character further every 3 frames."""

    def __init__(self, copyright_line):
        """copyright_line: the 32 characters left showing when a message has gone."""
        self.copyright = copyright_line
        self.buffer = ""          # $FC00
        self.left = 0             # $D973: whole steps still to go; 0 = nothing scrolling
        self.pos = 0              # $D975 - $FC00
        self.frame = 6            # $D974: counts frames, 6 to 1

    def start(self, text):
        """$8B69: start a message."""
        self.buffer = " " * 31 + text + self.copyright
        self.left = 32 + len(text)
        self.pos = 0

    def interrupt(self):
        """One frame. Returns ('print', 32 characters), ('shift',) for half a character, or
        None."""
        self.frame = (self.frame - 1) & 0xFF
        if self.frame == 0:
            self.frame = 6
            if self.left:
                self.left -= 1
                self.pos += 1
                return ("print", self.buffer[self.pos - 1:self.pos + 31])
        elif self.frame == 3 and self.left:
            return ("shift",)
        return None


def signed_distance(a, b):
    """$AB81 after SUB: |a - b| worked out on bytes (so 128 apart stays 128)."""
    d = (a - b) & 0xFF
    return (-d) & 0xFF if d & 0x80 else d


class City:
    """The state of the city map."""

    def __init__(self, text, x=LOGO_START[0], y=LOGO_START[1], steps=0, money=7400, seed=(1, 2, 3, 4, 5, 6),
                 equipment=0, traps=1, bait=0):
        """Start the city as $8C1A does.

        text: the messages (assets/text.json). x, y: the logo ($DF43, $DF44). steps: the step
        counter ($D917). money: dollars ($D965-$D963, BCD). seed: the random number bytes
        ($D906-$D90B). equipment: what was bought ($D966 bits). traps: empty traps ($D971).
        bait: ghost bait left ($D96E).
        """
        self.text = text
        self.x, self.y, self.steps = x, y, steps
        self.dot = False        # True on a pass where the logo left a dot (for the drawing)
        self.recolour = False   # True on a pass where the city's colours are redrawn
        self.lights = []        # (building, ink, keep) coloured by the equipment this pass
        self.drawn = True       # False on a pass that ended before the drawing
        self.event = None       # set when the city map ends: ('drive', building) or ('game_over',)
        self.scene = None       # 'attack', 'mayor' or 'mayor_wait' while a Marshmallow scene runs
        self.scene_step = None  # what this step was: None (a pass), 'draw', 'arrive' or 'end' (scene steps)
        self.scene_count = 0    # $D979: the attack's frame count
        self.rebuild = False    # True on the step the buildings are drawn again ($929D)
        self.sync = None        # the check script's hook (see step)
        self.seed = list(seed)
        self.money = money
        self.start_money = money // 100             # $D9D4/$D9D3: hundreds of dollars
        self.pk = 0                                   # $D916/$D915, kept here as a plain number
        self.buildings = [QUIET] * 20                 # $D927
        self.timers = [0] * 20                        # $D93B
        self.buildings[15] = STIRRING
        self.buildings[7] = HAUNTED
        self.timers[7] = HAUNT_TIME
        self.men, self.traps, self.power = 3, traps, 0x99   # $D970, $D971, $D972 (BCD)
        self.equipment = equipment
        self.tick = 2                                 # $D913
        self.ghosts = [list(p) for p in GHOST_STARTS]  # $DF03/$DF04, $DF13/$DF14, ...
        self.flags = [0] * 4                          # $D919: 0 = roaming
        self.parts = [[0, 0] for _ in range(6)]       # $DF83/$DF84...: the Marshmallow Man's pieces, slots 8-13
        self.bait_dot = [0, 0]                        # $DFE3/$DFE4: slot 14, on the bait at the mayor's reward
        self.stomped = [0] * 20                       # $D94F: buildings the Marshmallow Man stomped on
        self.walkers = [list(p) for p in WALKER_STARTS]  # $DF53/$DF54, $DF63/$DF64
        self.directions = [RIGHT_, RIGHT_]            # $D925/$D926; 0 = arrived at Zuul
        self.redraw_count = 0x10                      # $D9DC
        self.alert = 0                                # $D969: 0 none, 1 warning, 2 alert, 3 attack
        self.spot = [0, 0]                            # $D96A/$D96B: where the Marshmallow Man forms
        self.spot_building = 0                        # $D97A
        self.bait_left = bait                         # $D96E
        self.bait_down = 0                            # $D96F
        self.bait = [0, 0]                            # $DF73/$DF74 (y 0: not shown)
        self.beside = [NONE, NONE]                    # $D967/$D968: the building picked, the other
        self.scroller = Scroller(text["copyright"])
        self.car = 0                                  # $D983: which car was bought (0-3)
        self.traps_carried = 1                        # $D9CA: traps on the car's roof
        self.drive_x = 0                              # $D97D: the car's x before its last move on a drive
        self.drive_frac = 0                           # $D918: the drive's distance, below one step
        self.name = ""                                # $D9A2: the player's name (for the account number)
        self.laser = 0x10                             # $D9DA: room left in the laser confinement system
        self.facing = 0                               # $D99E: the way the last man moved faced (0 right, 1 left)
        self.street_colours = (0x38, 0x47)            # $A3EC, $A3F1: the last brick street's colours (GHQ uses one)

    # --- small helpers -------------------------------------------------------------------

    def random(self):
        """$A8D2: the next random number (0-255). Adds three of the six seed bytes, moves them
        all up one, and puts the sum, inverted, at the front."""
        s = self.seed
        a = s[4] + s[0]
        a = (a & 0xFF) + s[1] + (a >> 8)
        s[1:6] = s[0:5]
        s[0] = (a & 0xFF) ^ 0xFF
        return s[0]

    def pk_high(self):
        """PK's top two digits as the game's BCD byte ($D916)."""
        return bcd.to_bcd(self.pk // 100)

    def add_money_bcd(self, b, c):
        """$AAFE: add B (hundreds) and C (dollars) to the money in BCD, as the game does,
        stopping at $999999."""
        hi, mid, lo = bcd.to_bytes(self.money, 3)
        lo, carry = bcd.add(lo, c)
        mid, carry = bcd.add(mid, b, carry)
        hi, carry = bcd.add(hi, 0, carry)
        self.money = MAX_MONEY if carry else bcd.from_bytes([hi, mid, lo])

    def after_building(self):
        """$9FBD-$A02B: back from a building: it is quiet now whatever happened, the bait is
        picked up, and each touched roaming ghost is untouched again, back at its start
        unless bait was down or an alert was on."""
        n = self.beside[0]
        if n < 20 and self.buildings[n] == HAUNTED:
            self.buildings[n] = QUIET
        for g, (flag, start) in enumerate(zip(self.flags, GHOST_STARTS)):
            if flag:
                if not self.bait_down and self.alert < 2:
                    self.ghosts[g] = list(start)
                self.flags[g] = 0
        self.bait[1] = 0
        self.bait_down = 0
        self.event = None

    def add_pk(self, n):
        """$AA85: add to PK energy, stopping at 9999."""
        self.pk = min(self.pk + n, 9999)

    def haunted(self):
        """The buildings that are haunted now, as a set of numbers."""
        return {n for n, state in enumerate(self.buildings) if state == HAUNTED}

    def state(self, n):
        """A building's state, read as the game does: past building 19 it reads on into the
        timers, as the original does when the logo is in odd places."""
        table = self.buildings + self.timers
        return table[n] if n < len(table) else 0

    def message(self, name):
        """Start one of the bottom line's messages (text.json)."""
        self.start_message(self.text[name])

    def start_message(self, text):
        """$8B69: start a message along the bottom line (telling the check script first)."""
        if self.sync:
            self.sync("message")
        self.scroller.start(text)

    def count_step(self):
        """$91A7: add 2 to the step counter, stopping at $FF."""
        self.steps = min(self.steps + 2, 0xFF)

    # --- the parts of a pass, in the order the game does them -----------------------------

    def status_line(self):
        """$932D: while SPACE is held, the status line (backpack power, empty traps, men)."""
        line = list(self.text["status"])
        for pos, ch in zip(STATUS_DIGITS, f"{self.power:02X}{self.traps}{self.men}"):
            line[pos] = ch
        self.start_message("".join(line))

    def marshmallow_check(self):
        """$8CE5: with bait down during an alert, the mayor pays (the scene at $8AA9). Without
        bait, during an alert, each roaming ghost that reached its place round the spot
        becomes part of the Marshmallow Man; when all four have, he attacks ($89E9).
        Returns True if a scene starts (the rest of the pass is skipped)."""
        if self.bait_down:
            if self.alert == 2:
                self.start_mayor()
                return True
            return False
        if self.alert != 2:
            return False
        there = 0
        for n, g in enumerate(self.ghosts):
            dx, dy = SPOT_OFFSETS[n]
            if g[1] == 0:
                there += 1
            elif g[1] == (self.spot[1] + dy) & 0xFF and g[0] == (self.spot[0] + dx) & 0xFF:
                self.parts[n] = list(g)
                g[1] = 0
                there += 1
        if there == 4:
            self.alert = 3
            self.start_attack()
            return True
        return False

    def alerts(self):
        """$8D51: the Marshmallow alerts, from PK's hundreds digit once PK is 4700 or more."""
        hi = self.pk_high()
        if hi < 0x47:
            self.alert = 0
            return
        digit = hi & 0x0F
        if digit >= 7:
            if self.alert == 0:
                self.alert = 1             # the warning
        elif digit:
            if self.alert == 1:
                self.alert = 0
        elif self.alert == 1:
            if any(self.flags):
                self.alert = 0
                return
            self.message("alert")
            while True:                    # a random building 4-15, not Zuul
                n = (self.random() & 0x0F) + 4
                if n < 0x10 and n != ZUUL:
                    break
            self.spot_building = n
            self.spot = [(n & 3) * 0x30 + 0x30, (n >> 2) * 0x28 + 0x0C]
            self.alert = 2

    def drop_bait(self, keys):
        """$8DCD: B drops bait where the logo is, if there is any left."""
        if "bait" not in keys or self.bait_down:
            return
        if not self.bait_left:
            self.message("no_bait")
            return
        self.bait_left -= 1
        self.bait = [self.x, (self.y + 4) & 0xFF]
        self.bait_down = 1

    def count_down_timers(self):
        """$8E02: half the time, every haunted building's timer counts down. One that reaches
        0 goes quiet, and its ghost adds 300 to PK."""
        if self.random() & 1:
            return
        for n in range(20):
            if self.timers[n]:
                self.timers[n] -= 1
                if self.timers[n] == 0:
                    self.buildings[n] = QUIET
                    self.add_pk(300)

    def new_haunting(self):
        """$8E28: four random tests (each stops the rest if it fails), then a building goes up
        one state: quiet -> stirring -> haunted (timer restarts at $99)."""
        if self.random() >= 0x64:
            return
        if (self.random() << 1) & 0xFF >= (self.pk_high() + 2) & 0xFF:
            return
        n = self.random() & 0x1F
        if n >= 20 or n in (ZUUL, GHQ):
            return
        if not self.random() & 1:
            return
        if self.buildings[n] + 1 < HAUNTED:
            self.buildings[n] += 1
        else:
            self.timers[n] = HAUNT_TIME
            self.buildings[n] = HAUNTED

    def find_beside(self, keys):
        """$8E6B: which building is beside the logo: the one above, or below while down is
        held; none on a vertical road or past the ends. (At the right-hand end the column
        comes out as 4, i.e. the first building of the next row, as in the original.)"""
        col = None
        a = 0x18
        for c in range(4):
            if a >= self.x:
                break
            a += 0x2F
            if a >= self.x:
                col = c
                break
            a += 1
        else:
            if 0xD8 >= self.x:
                col = 4
        if col is None:
            self.beside = [NONE, NONE]
            return
        above = (((self.y - 0x34) & 0xFF) >> 3 & 0xFC) + col
        below = above + 4
        self.beside = [below, above] if "down" in keys else [above, below]

    def equipment_lights(self):
        """$8EB7: with the PK energy detector, stirring buildings beside the logo turn magenta
        (on a vertical road, the ones either side); with the Marshmallow sensor, during the
        warning, the building beside the logo turns white."""
        self.lights = []
        if self.beside[0] == NONE and self.equipment & PK_DETECTOR:
            a, c = (self.y - 0x35) & 0xFF, 1
            while a >= 0x27:
                c = (c + 1) & 0xFF
                a = (a - 0x28) & 0xFF
            c = (c << 2) & 0xFF
            x = self.x
            if x < 0x48:
                first, b = False, 0
            elif x < 0x78:
                first, b = True, 0
            elif x < 0xA8:
                first, b = True, 1
            else:
                first, b = x != 0xD8, 2
            if first:
                self.light(b + c, DETECTOR_LIGHT)
                b += 1
            self.light(b + c, DETECTOR_LIGHT)
            return
        if self.equipment & PK_DETECTOR:
            self.light(self.beside[0], DETECTOR_LIGHT)
            self.light(self.beside[1], DETECTOR_LIGHT)
        if self.equipment & MARSHMALLOW_SENSOR and self.alert == 1:
            self.lights.append((self.beside[0], *SENSOR_LIGHT))

    def light(self, n, colour):
        """Colour building n if it is stirring ($926A)."""
        if self.state(n) == STIRRING:
            self.lights.append((n, *colour))

    def walker_step(self, n):
        """$91B7: the Keymaster (0) or the Gatekeeper (1) moves 1 pixel; at the map's edge or a
        crossroads it picks a direction (random below PK 9500, else towards Zuul). From PK
        5000, at its way into Zuul it goes in and stops (direction 0)."""
        pos, d = self.walkers[n], self.directions[n]
        x, y = pos
        stuck = False
        if d & RIGHT_:
            stuck = x == 0xD8
            if not stuck:
                pos[0] = x + 1
        elif d & LEFT_:
            stuck = x == 0x18
            if not stuck:
                pos[0] = x - 1
        elif d & DOWN_:
            stuck = y == 0xB0
            if not stuck:
                pos[1] = y + 1
        else:
            stuck = y == 0x38
            if not stuck:
                pos[1] = y - 1
        if stuck or (pos[0] in WALKER_COLUMNS and pos[1] in WALKER_ROWS):
            new = self.pick_direction(pos)
            if new != d:
                self.directions[n] = new
                return
        if self.pk_high() >= 0x50 and pos[0] == WALKER_TARGET_X[n] and pos[1] == 0x88:
            pos[1] = 0x80
            self.directions[n] = 0

    def pick_direction(self, pos):
        """$9231: a new direction for a walker at pos."""
        if self.pk_high() >= 0x95:
            if pos[1] == 0x88:
                return RIGHT_ if pos[0] < 0x88 else LEFT_
            return DOWN_ if pos[1] < 0x88 else UP_
        # one of the 4, by rotating a set carry left (r & 3) times (0 means 256 times, i.e. 4)
        return (8, 1, 2, 4)[self.random() & 3]

    @staticmethod
    def towards(g, tx, ty):
        """Move a ghost 1 pixel on x and on y towards (tx, ty) ($8FDB, $93FA)."""
        if g[0] != tx:
            g[0] += -1 if g[0] > tx else 1
        if g[1] != ty:
            g[1] += -1 if g[1] > ty else 1

    def move_ghosts(self):
        """$8FBE: each roaming ghost moves 1 pixel on x and on y: to its place round the bait
        when it is down, round the spot during an alert, else (if not flagged) towards Zuul.
        One already at Zuul adds 100 to PK and starts again."""
        for n, g in enumerate(self.ghosts):
            dx, dy = SPOT_OFFSETS[n]
            if self.bait_down:
                if g[1]:
                    self.towards(g, (self.bait[0] + dx) & 0xFF, (self.bait[1] + dy) & 0xFF)
                continue
            if self.alert == 2:
                if g[1]:
                    self.towards(g, (self.spot[0] + dx) & 0xFF, (self.spot[1] + dy) & 0xFF)
                continue
            if self.flags[n]:
                continue
            if g[0] == ZUUL_SPOT[0]:
                if g[1] == ZUUL_SPOT[1]:
                    self.add_pk(100)
                    g[:] = GHOST_STARTS[n]
                    continue
            else:
                g[0] += -1 if g[0] > ZUUL_SPOT[0] else 1
            if g[1] != ZUUL_SPOT[1]:
                g[1] += -1 if g[1] > ZUUL_SPOT[1] else 1

    def pk_tick(self):
        """$8F63: count down to the next tick; on it the walkers step, PK goes up 1, the next
        tick is set ((PK's top byte from $A1) / 8 passes away) and the roaming ghosts move."""
        self.tick = bcd.sub(self.tick, 1)[0]     # SUB 1 / DAA, though the tick is set in binary
        if self.tick:
            return
        for n in range(2):
            if self.directions[n]:
                self.walker_step(n)
        self.add_pk(1)
        if self.alert == 2:
            self.tick = 1                  # every pass during an alert
        else:
            self.tick = ((0xA1 - self.pk_high()) & 0xFF) >> 3
        self.move_ghosts()

    def fire(self, keys):
        """$9061/$94B5: Z beside a building drives there, unless a message says why not (too
        few men, no backpack power, no empty traps). Zuul only once the Keymaster and the
        Gatekeeper are both there, and then nowhere else. A stirring building has a 1 in 4
        chance of becoming haunted on the way.
        Returns True if the pass ends here (a message, or the drive)."""
        if "fire" not in keys or self.beside[0] == NONE:
            return False
        n = self.beside[0]
        arrived = not (self.directions[0] | self.directions[1])
        if (n == ZUUL) != arrived:
            return True
        if n not in (GHQ, ZUUL):
            for ok, name in ((self.men >= 2, "few_men"), (self.power, "no_power"), (self.traps, "no_traps")):
                if not ok:
                    self.message(name)
                    return True
            if self.state(n) == STIRRING and self.random() < 0x40 and n < 20:
                self.buildings[n] = HAUNTED
        self.event = ("drive", n)
        return True

    def touch_ghosts(self):
        """$906E: a roaming ghost within 16 of the logo (|dx| + |dy|, on bytes) gets flagged
        with the step counter (or 1), and stops."""
        for n, (gx, gy) in enumerate(self.ghosts):
            near = (signed_distance(self.x, gx) + signed_distance(self.y, gy)) & 0xFF < 0x10
            if near and not self.flags[n]:
                self.flags[n] = self.steps or 1

    def leave_dot(self):
        """$90A3: when the logo is level with a road (y & 7 is 4: every 8 rows), it
        leaves a dot under itself, before it moves (the drawing puts it there)."""
        self.dot = self.y & 7 == 4

    def move_logo(self, keys):
        """$90C1: move the logo 2 pixels for each direction held, along the roads only.

        keys: set of 'up', 'down', 'left', 'right' held this pass.
        Left and right work on a horizontal road, then up and down on a vertical one (checked
        after the move across, as in the original). Opposite keys cancel out, except at the
        end of a road: there the original skips the second key ($90DE, $911D), so left and
        right together at the left end, or up and down at the top, do nothing.
        """
        if self.y in ROAD_ROWS:
            if "left" in keys and self.x == LEFT:
                pass                       # blocked, and right isn't checked
            else:
                if "left" in keys:
                    self.count_step()
                    self.x -= STEP
                if "right" in keys and self.x != RIGHT:
                    self.count_step()
                    self.x += STEP
        if self.x in ROAD_COLUMNS:
            if "up" in keys and self.y == TOP:
                pass                       # blocked, and down isn't checked
            else:
                if "up" in keys:
                    self.count_step()
                    self.y -= STEP
                if "down" in keys and self.y != BOTTOM:
                    self.count_step()
                    self.y += STEP

    def end_check(self):
        """$913E: once the Keymaster and the Gatekeeper are both at Zuul (and no alert is on),
        every building goes quiet but Zuul, which is haunted. With less money than at the
        start the game is over; otherwise "GO TO ZUUL..." scrolls by (and while any message
        scrolls, the colours are redrawn every pass).
        Returns True if the colours are redrawn now (skipping the usual count)."""
        if self.directions[0] | self.directions[1] or self.alert >= 2:
            return False
        self.buildings = [QUIET] * 20
        self.buildings[ZUUL] = HAUNTED
        if self.money // 100 < self.start_money:
            self.event = ("game_over",)
            return False
        if self.scroller.left:
            self.recolour = True
            return True
        self.message("go_to_zuul")
        return False

    def redraw_colours(self):
        """$9185: every $40 passes, on the pass just before a tick, the city's colours are
        redrawn and the haunted buildings coloured again (so a building's colour changes up
        to 2.5 seconds after its state does). The screen shows it on the next pass."""
        self.redraw_count = (self.redraw_count - 1) & 0xFF
        if self.redraw_count:
            return
        if self.tick != 1:
            self.redraw_count = 1          # try again next pass
            return
        self.redraw_count = REDRAW_EVERY
        self.recolour = True

    # --- the Marshmallow Man's scenes (notes/06-marshmallow-scenes.md) ------------------

    def scene_draw(self, keys):
        """A scene's drawing ($A8F3), which checks SPACE too."""
        self.drawn = True
        if self.sync:
            self.sync("draw")
        if "status" in keys:
            self.status_line()

    def start_attack(self):
        """$89E9: the legs take their second pose (slot 13 for 11, slot 12 under 10)."""
        p = self.parts
        p[5][1], p[4][0], p[5][0] = p[3][1], p[2][0], p[3][0]
        p[3][1] = 0
        self.scene, self.scene_count, self.scene_step = "attack", 0, "draw"

    def attack_step(self):
        """$8A06: every 16 frames the legs swap pose and he moves down a pixel; after 256
        frames he breaks back into the ghosts, does $4000 of damage and the building at the
        spot is stomped. Returns 'draw' or 'end'."""
        self.scene_count = (self.scene_count + ATTACK_FRAMES) & 0xFF
        p = self.parts
        if self.scene_count == 0:
            for n, g in enumerate(self.ghosts):          # $8A57
                g[1] = p[n][1] or p[n + 2][1]
                p[n][1] = 0
                self.flags[n] = 0
            p[4][1] = p[5][1] = 0
            self.bait_down = self.alert = 0
            self.message("attack")
            if trainer.MONEY not in trainer.on:
                self.money = self.money - DAMAGE if self.money >= DAMAGE else 0   # $AB58 stops at 0
            self.stomped[self.spot_building] = (self.stomped[self.spot_building] + 1) & 0xFF
            self.rebuild = True
            self.scene = None
            return "end"
        if self.scene_count & 0x10:
            p[4][1], p[3][1] = (p[2][1] + 1) & 0xFF, (p[5][1] + 1) & 0xFF
            p[2][1] = p[5][1] = 0
        else:
            p[2][1], p[5][1] = (p[4][1] + 1) & 0xFF, (p[3][1] + 1) & 0xFF
            p[3][1] = p[4][1] = 0
        p[0][1] = (p[0][1] + 1) & 0xFF
        p[1][1] = (p[1][1] + 1) & 0xFF
        return "draw"

    def start_mayor(self):
        """$8AA9: the ghosts still roaming become the Marshmallow Man's pieces where they are,
        and the walk to the bait starts."""
        for n, g in enumerate(self.ghosts):
            if g[1]:
                self.parts[n] = list(g)
                g[1] = 0
        self.scene = "mayor"
        self.scene_step = self.mayor_step()

    def mayor_step(self):
        """$8ACF: each piece moves a pixel towards its place round the bait; when all four are
        there, a dot on the bait, the reward and the message. Returns 'draw' or 'arrive'."""
        places = [[(self.bait[0] + dx) & 0xFF, (self.bait[1] + dy) & 0xFF] for dx, dy in SPOT_OFFSETS]
        for part, place in zip(self.parts, places):
            if part[1]:                                  # $93FA leaves a hidden piece alone
                self.towards(part, *place)
        if self.parts[:4] != places:
            return "draw"
        self.bait_dot = list(self.bait)                  # $8B0C
        self.scene = "mayor_wait"
        return "arrive"

    def mayor_reward(self):
        """$8B1B, after the arrival's drawing: the message, the alert ends, +$2000."""
        self.message("mayor")
        self.alert = 0
        self.money = min(self.money + REWARD, MAX_MONEY)

    def mayor_end(self):
        """$8B33, after a 2 second wait: the pieces turn back into the roaming ghosts, and the
        dot and the bait go."""
        for g, part in zip(self.ghosts, self.parts):
            g[0], g[1] = part
            part[1] = 0
        self.bait_dot[1] = self.bait[1] = 0
        self.alert = self.bait_down = 0
        self.scene = None

    @property
    def step_frames(self):
        """How many frames the next step takes, for the port's timing."""
        return {None: PASS_FRAMES, "attack": ATTACK_FRAMES, "mayor": MAYOR_FRAMES,
                "mayor_wait": MAYOR_WAIT}[self.scene]

    def step(self, keys, sync=None):
        """One pass of the city loop, or one step of a Marshmallow scene. The sprites are
        drawn after move_logo ($A8F3), so dot and lights are for before the drawing and
        recolour for after it. A pass can end early (drawn is then False); event says when
        the city map is over.

        keys: set of 'up', 'down', 'left', 'right', 'fire' (Z), 'bait' (B), 'status' (SPACE).
        sync: called with 'message' as a message starts, 'draw' just before the drawing's
        SPACE check and 'end' just before the end check, which all touch the scroller (for
        the check script, to run the interrupts that came before them in the original).
        """
        self.recolour, self.drawn, self.dot, self.lights, self.rebuild = False, False, False, [], False
        self.sync = sync
        if self.scene:
            self.scene_tick(keys)
            return
        self.scene_step = None
        if "status" in keys:
            self.status_line()
        if self.marshmallow_check():
            self.scene_draw(keys)
            if self.scene_step == "arrive":
                self.mayor_reward()
            return
        self.alerts()
        self.drop_bait(keys)
        self.count_down_timers()
        self.new_haunting()
        self.find_beside(keys)
        self.equipment_lights()
        self.pk_tick()
        if self.fire(keys):
            return
        self.touch_ghosts()
        self.leave_dot()
        self.move_logo(keys)
        self.scene_draw(keys)              # the drawing checks SPACE again
        if sync:
            sync("end")
        if self.end_check() or self.event:
            return
        self.redraw_colours()

    def scene_tick(self, keys):
        """One step of the scene that is running (see step)."""
        if self.scene == "attack":
            self.scene_step = self.attack_step()
            if self.scene_step == "draw":
                self.scene_draw(keys)
        elif self.scene == "mayor":
            self.scene_step = self.mayor_step()
            self.scene_draw(keys)
            if self.scene_step == "arrive":
                self.mayor_reward()
        else:
            self.mayor_end()
            self.scene_step = "end"
            self.scene_draw(keys)
