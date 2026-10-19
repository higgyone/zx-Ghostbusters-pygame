"""Keyboard and joystick to the directions and buttons a game reads.

A game lists its controls by name, e.g. QAOP = {"up": [pygame.K_q], ...}; held() says which
names are held. A joystick or gamepad also works, even one plugged in after start-up: its stick
or hat gives up, down, left and right, and any button gives "fire".
"""
import pygame

# The usual Spectrum layouts. The arrow keys are added to each (they were the cursor keys 5-8).
QAOP = {"up": [pygame.K_q], "down": [pygame.K_a], "left": [pygame.K_o], "right": [pygame.K_p], "fire": [pygame.K_SPACE]}
SINCLAIR = {"up": [pygame.K_9], "down": [pygame.K_8], "left": [pygame.K_6], "right": [pygame.K_7], "fire": [pygame.K_0]}
CURSOR = {"up": [pygame.K_7], "down": [pygame.K_6], "left": [pygame.K_5], "right": [pygame.K_8], "fire": [pygame.K_0]}
ARROWS = {"up": [pygame.K_UP], "down": [pygame.K_DOWN], "left": [pygame.K_LEFT], "right": [pygame.K_RIGHT]}


class Keys:
    """Which of a game's controls are held."""

    def __init__(self, layout, arrows=True, joystick=True):
        """layout: {name: [pygame key codes]}. arrows: add the arrow keys to up/down/left/right.
        joystick: read the first joystick or gamepad plugged in, now or later (pygame must be
        initialised first, and its events read, e.g. with pygame.event.get, to see one plugged in)."""
        self.layout = {name: list(codes) for name, codes in layout.items()}
        if arrows:
            for name, codes in ARROWS.items():
                self.layout.setdefault(name, []).extend(codes)
        self.joystick = joystick
        self._joy = None

    @property
    def stick(self):
        """The joystick being read (a pygame Joystick), or None. Finds one plugged in since the
        last look and drops one unplugged."""
        if not self.joystick or not pygame.joystick.get_init() or not pygame.joystick.get_count():
            self._joy = None
        elif self._joy is None:
            self._joy = pygame.joystick.Joystick(0)
        return self._joy

    def held(self, pressed=None):
        """Which controls are held now.

        pressed: a pygame key state (pygame.key.get_pressed()); None reads it now.
        Returns a set of names from the layout (plus the joystick's).
        """
        pressed = pressed if pressed is not None else pygame.key.get_pressed()
        out = {name for name, codes in self.layout.items() if any(pressed[c] for c in codes)}
        if self.stick:
            try:
                out |= self._stick()
            except pygame.error:     # unplugged since the last look
                self._joy = None
        return out

    def _stick(self):
        """The joystick's directions and fire, as names."""
        s = self.stick
        x = s.get_axis(0) if s.get_numaxes() else 0
        y = s.get_axis(1) if s.get_numaxes() > 1 else 0
        hx, hy = s.get_hat(0) if s.get_numhats() else (0, 0)
        out = set()
        if x < -0.5 or hx < 0:
            out.add("left")
        if x > 0.5 or hx > 0:
            out.add("right")
        if y < -0.5 or hy > 0:
            out.add("up")
        if y > 0.5 or hy < 0:
            out.add("down")
        if any(s.get_button(i) for i in range(s.get_numbuttons())):
            out.add("fire")
        return out
