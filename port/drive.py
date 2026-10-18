"""The drive to a building (notes/07-the-drive.md), with no drawing, so it can be checked
against the original step by step. It works on the City it came from: the step counter
($D917), the roaming ghosts and their flags, PK, money, the random numbers and the bottom
line's messages all carry on through it.

Drive(city) is the set-up ($951B); each step() is one pass of the drive's loop ($965F). When
done is True the car has reached the building ($9A38).
"""
GHOST_VACUUM = 0x04                     # $D966 bit
# each car ($99DC table, $9A34): colour, height on the road, the two lane marking numbers, speed
CARS = ((0x3D, 0x76, 6, 2, 0x75), (0x38, 0x78, 5, 4, 0x90), (0x39, 0x76, 5, 3, 0xB0), (0x3B, 0x76, 5, 3, 0xFF))
CAR_START = 0xCE                        # $9573: the car starts on the right, the furthest it goes
WALL_START, WALL_END = 0x1F, 0xC6       # $9630, $9940: the left wall, which pushes the car in at the end
CAR_STEP = 4                            # pixels the car moves a step
LOGO_DX = 0x0A                          # the logo rides on the roof at the car's x + 10
GHOST_TOP, GHOST_GONE = 2, 0xE0         # a ghost's y on the road when it appears, and when it has gone
GHOST_X = (0x18, 0xCE)                  # the range of a ghost's x when it appears
DRIVE_FRAMES = 2.75                     # a step takes about 2.6-2.9 frames (measured in the simulator)
# $966F: a move between these x's (before, after) colours a lane column with the car's colour
PAINTS = {(0x22, 0x26): 10, (0x62, 0x5E): 10, (0x7A, 0x7E): 21, (0xBA, 0xB6): 21}


class Drive:
    """The state of a drive."""

    def __init__(self, city):
        """Set up the drive as $951B does. city: the City the car leaves (it changes as the
        drive goes)."""
        self.city = city
        c = city
        self.colour, self.car_y, self.lane_a, self.lane_b, self.speed = CARS[c.car]
        self.x = CAR_START                  # $D97B
        self.wall = WALL_START              # $D982
        self.count = 0                      # $D97C: steps so far
        self.road = [0, 0, 0, 0]            # $D91D: each ghost's y on the road (0: not there)
        self.ghost_x = [0, 0, 0, 0]         # their x (slots 0-3, cleared by $ADE9; the city's are kept)
        self.done = c.steps == 0            # no steps on the map: straight to the building
        for n, f in enumerate(c.flags):     # $9640: the distance left when each touched ghost appears
            if f:
                left = (c.steps - f) & 0xFF
                c.flags[n] = left if left >= 2 else 2
        # what the drawing needs to know about the last step
        self.paint = None                   # a lane column coloured with the car's colour ($9994)
        self.shift = None                   # 'left' or 'right': the car's picture moved
        self.drawn = False

    def vacuuming(self, keys):
        """True while Z is held with the ghost vacuum on the car."""
        return "fire" in keys and self.city.equipment & GHOST_VACUUM

    def step(self, keys, sync=None):
        """One step of the drive.

        keys: set of 'left', 'right', 'fire' (Z), 'status' (SPACE).
        sync: as for City.step ('message' and 'draw').
        """
        c = self.city
        c.sync = sync
        self.paint, self.shift, self.drawn = None, None, False
        if "status" in keys:
            c.status_line()
        if self.count & 7 == 0:             # $9662: PK goes up every 8 steps
            c.add_pk(1)
        self.paint = PAINTS.get((c.drive_x, self.x))   # (before the car moves)
        self.move_car(keys)
        self.move_ghosts(keys)
        self.count = (self.count + 1) & 0xFF
        self.drawn = True
        if sync:
            sync("draw")
        if "status" in keys:
            c.status_line()                 # the drawing checks SPACE again
        self.go_on()

    def move_car(self, keys):
        """$96C5: left and right, 4 pixels, unless the left wall is pushing the car right."""
        c = self.city
        if self.x < self.wall:
            self.x = (self.x + CAR_STEP) & 0xFF
            self.shift = "right"
            return
        c.drive_x = self.x
        if "left" in keys:
            if self.x >= (self.wall + CAR_STEP) & 0xFF:
                self.x -= CAR_STEP
                self.shift = "left"
        elif "right" in keys and self.x < CAR_START:
            self.x += CAR_STEP
            self.shift = "right"

    def move_ghosts(self, keys):
        """$9769: each ghost on the road floats down 2 pixels; the vacuum pulls one 1 to 32
        pixels right of the car towards the car's x + 16 and its height, where it is caught."""
        for n, gx in enumerate(self.ghost_x):
            y = self.road[n]
            if not y:
                continue
            d = (self.x - gx) & 0xFF
            if self.vacuuming(keys) and d >= 0xE0:
                if d != 0xF0:
                    self.ghost_x[n] = (gx + (1 if d > 0xF0 else -1)) & 0xFF
                if y >= self.car_y:
                    y = 0 if y == self.car_y else y - 2
                else:
                    y += 2
            else:
                y = (y + 2) & 0xFF
            self.road[n] = y

    def go_on(self):
        """$98C7: the car's speed adds up to steps along the road; at each one a touched ghost
        may appear, one that floated off is gone (roaming again), and when the steps run out
        and the road is clear the left wall moves in."""
        c = self.city
        total = c.drive_frac + self.speed
        c.drive_frac = total & 0xFF
        if total < 0x100:
            return
        if c.steps:
            c.steps -= 1
        for n in range(4):
            if c.steps and c.flags[n] == c.steps:
                r = c.random()
                while not GHOST_X[0] <= r < GHOST_X[1]:
                    r = c.random()
                self.ghost_x[n] = r
                self.road[n] = GHOST_TOP
            if self.road[n] >= GHOST_GONE:
                self.road[n] = 0
                c.flags[n] = 0
        if c.steps or any(self.road):
            return
        self.wall += CAR_STEP
        if self.wall >= WALL_END:
            self.done = True

    def ghost_slots(self):
        """Where sprite slots 0-3 go: (x, y), y 0 for a ghost not on the road."""
        return list(zip(self.ghost_x, self.road))
