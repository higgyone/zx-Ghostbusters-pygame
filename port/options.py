"""The setup screen: not in the original. It comes first, in the Spectrum's font and colours,
and turns the trainer's cheats (port/trainer.py) on or off before playing.

Keys: up/down (Q/A or the arrows) pick a line, SPACE or Z turns it on or off, 1-4 switch a
line straight away, ENTER plays. A joystick works too: up/down, and fire to switch. The
choice is kept for next time in ~/.ghostbusters.json.
"""
import json
import os

import numpy as np
import pygame
from zxport.screen import Screen
from zxport.text import print_at

import trainer

SAVED = os.path.join(os.path.expanduser("~"), ".ghostbusters.json")
BLACK, BLUE, RED, MAGENTA, GREEN, CYAN, YELLOW, WHITE = range(8)
FIRST_ROW = 4                    # the first cheat's text row
ABOUT_ROW = 16


def attr(ink, paper=BLACK):
    """A bright attribute byte. ink, paper: Spectrum colours 0-7."""
    return 0x40 | paper << 3 | ink


def load_saved():
    """The cheats turned on last time. Returns a set (empty if none were saved)."""
    try:
        with open(SAVED) as f:
            return set(json.load(f).get("trainer", ())) & set(trainer.NAMES)
    except Exception:
        return set()


def save(names):
    """Keep the cheats turned on for next time. names: a set of trainer names."""
    try:
        with open(SAVED, "w") as f:
            json.dump({"trainer": sorted(names)}, f)
    except OSError:
        pass


def wrap(text, width):
    """Split text into lines of at most width characters. Returns a list."""
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    return lines + [line] if line else lines


class OptionsScreen:
    """The setup screen's state, and its picture."""

    def __init__(self, font, ticked=None):
        """font: from zxport.text.load_font. ticked: the cheats on to begin with (None: what
        was saved last time)."""
        self.font = font
        self.ticked = load_saved() if ticked is None else set(ticked) & set(trainer.NAMES)
        self.cursor = 0
        self.held = set()                # the joystick controls held last frame
        self.screen = None
        self.draw()

    def key(self, key):
        """A key press (a pygame key code). Returns True when the game should start."""
        names = trainer.NAMES
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return True
        if pygame.K_1 <= key < pygame.K_1 + len(names):
            self.cursor = key - pygame.K_1
            self.ticked ^= {names[self.cursor]}
        elif key in (pygame.K_UP, pygame.K_q):
            self.cursor = (self.cursor - 1) % len(names)
        elif key in (pygame.K_DOWN, pygame.K_a):
            self.cursor = (self.cursor + 1) % len(names)
        elif key in (pygame.K_SPACE, pygame.K_z):
            self.ticked ^= {names[self.cursor]}
        self.draw()
        return False

    def stick(self, held):
        """The joystick's controls held now (a set of names): acts on presses only."""
        new = held - self.held
        self.held = held
        if "up" in new:
            self.cursor = (self.cursor - 1) % len(trainer.NAMES)
        if "down" in new:
            self.cursor = (self.cursor + 1) % len(trainer.NAMES)
        if "fire" in new:
            self.ticked ^= {trainer.NAMES[self.cursor]}
        if new:
            self.draw()

    def text(self, s, col, row, ink, paper=BLACK):
        """Print s at a character cell, in colour."""
        print_at(self.screen, self.font, s, col, row)
        self.screen.attrs[row, col:col + len(s)] = attr(ink, paper)

    def draw(self):
        """Make the picture (self.screen, a zxport Screen)."""
        self.screen = Screen(attrs=np.full((24, 32), attr(WHITE), np.uint8))
        self.text("            TRAINER             ", 0, 0, WHITE, BLUE)
        self.text("Not in the original: cheats to", 1, 2, CYAN)
        self.text("make the game easier.", 1, 3, CYAN)
        for i, name in enumerate(trainer.NAMES):
            on = name in self.ticked
            paper = BLUE if i == self.cursor else BLACK
            self.text(f" {i + 1} {trainer.LABELS[name]:<20} ", 1, FIRST_ROW + 1 + i, WHITE, paper)
            self.text(" ON " if on else " OFF", 26, FIRST_ROW + 1 + i, GREEN if on else RED, paper)
        self.text("With every cheat OFF this is", 1, 11, YELLOW)
        self.text("the original game.", 1, 12, YELLOW)
        about = wrap(trainer.ABOUT[trainer.NAMES[self.cursor]], 30)
        for k, line in enumerate(about[:5]):
            self.text(line, 1, ABOUT_ROW + k, WHITE)
        self.text("1-4/SPACE: on/off  ENTER: play", 1, 23, MAGENTA)
