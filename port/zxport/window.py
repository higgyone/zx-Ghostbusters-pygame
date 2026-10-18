"""The pygame window, with a border round the Spectrum's screen, and a pacer that runs the
game's passes at the original's rate whatever the display's frame rate is.
"""
import pygame

from .screen import HEIGHT, WIDTH


class Window:
    """A window showing a Screen, scaled up, inside a border."""

    def __init__(self, title, scale=3, border=16):
        """title: the window's caption. scale: window pixels per Spectrum pixel.
        border: Spectrum pixels of border on each side (the real one is wider)."""
        self.scale, self.border = scale, border
        size = ((WIDTH + 2 * border) * scale, (HEIGHT + 2 * border) * scale)
        self.surface = pygame.display.set_mode(size)
        pygame.display.set_caption(title)

    def show(self, screen, border_colour=(0, 0, 0), flash_swapped=False):
        """Draw a Screen with its border and put it on the display.

        screen: a zxport.screen.Screen. border_colour: (r, g, b).
        flash_swapped: as Screen.to_surface.
        """
        self.surface.fill(border_colour)
        offset = self.border * self.scale
        self.surface.blit(screen.to_surface(self.scale, flash_swapped), (offset, offset))
        pygame.display.flip()

    def show_surface(self, surface, border_colour=(0, 0, 0)):
        """As show, for a port that draws its own 256x192 pygame surface.

        surface: the picture, at Spectrum size. border_colour: (r, g, b).
        """
        self.surface.fill(border_colour)
        offset = self.border * self.scale
        size = (surface.get_width() * self.scale, surface.get_height() * self.scale)
        self.surface.blit(pygame.transform.scale(surface, size), (offset, offset))
        pygame.display.flip()


def quit_asked(events):
    """True if the window was closed or Esc pressed.

    events: from pygame.event.get().
    """
    return any(e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE) for e in events)


class Pacer:
    """Counts how many game passes are due, so a game runs at its own rate (e.g. 25 or 19.5 a
    second) while the display runs at its own."""

    def __init__(self, passes_per_second, display_fps=50):
        """passes_per_second: the original's rate. display_fps: how often to draw."""
        self.rate, self.fps = passes_per_second, display_fps
        self.clock = pygame.time.Clock()
        self.due = 0.0

    def passes(self):
        """Wait for the next display frame.

        Returns how many passes to run now (usually 0 or 1; at most 4, so a long stall isn't
        caught up all at once).
        """
        self.due += self.clock.tick(self.fps) / 1000 * self.rate
        n = min(int(self.due), 4)
        self.due = min(self.due - n, 1.0)
        return n

    def reset(self):
        """Forget the time since the last call (after a pause, so it isn't caught up)."""
        self.clock.tick()
        self.due = 0.0

    @property
    def frames_per_flash(self):
        """Display frames between FLASH swaps (the Spectrum swaps every 0.32 s)."""
        return max(1, round(self.fps * 0.32))
