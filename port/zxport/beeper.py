"""The Spectrum beeper's sounds, rebuilt as square waves, and WAV clips.

Most games beep through the ROM's BEEP routine ($03B5) with HL = pitch and DE = length in
cycles of the wave:   frequency = 437500 / (HL + 30.125) Hz,   duration = DE / frequency s.
The sample builders need only numpy, so they can be tested without a sound card.
"""
import numpy as np

RATE = 44100
VOLUME = 0.25


def frequency(hl):
    """The ROM BEEP's frequency in Hz for pitch value HL."""
    return 437500.0 / (hl + 30.125)


def beep_seconds(hl, de):
    """How long a ROM BEEP lasts, in seconds (HL pitch, DE cycles)."""
    return de / frequency(hl)


def silence(seconds):
    """A gap, as int16 samples."""
    return np.zeros(max(0, round(RATE * seconds)), dtype=np.int16)


def beep(hl, de, volume=VOLUME):
    """A ROM BEEP as int16 samples: a square wave, HL pitch, DE cycles long."""
    f = frequency(hl)
    n = max(1, round(RATE * de / f))
    phase = (np.arange(n) / RATE * f) % 1.0
    return (np.where(phase < 0.5, 1.0, -1.0) * volume * 32767).astype(np.int16)


def tune(notes, gap=0.0, tail=0.0):
    """Notes one after another, as int16 samples.

    notes: (HL, DE) pairs. gap: seconds of silence after each note (the game's own pause).
    tail: seconds of silence at the end.
    """
    parts = []
    for hl, de in notes:
        parts += [beep(hl, de), silence(gap)]
    parts.append(silence(tail))
    return np.concatenate(parts)


class Sounds:
    """Plays named sounds through pygame's mixer; play() never waits."""

    def __init__(self):
        """Open the mixer (mono at RATE)."""
        import pygame
        self.pygame = pygame
        pygame.mixer.quit()                                  # pygame.init() may have opened a stereo mixer
        pygame.mixer.init(RATE, -16, 1, allowedchanges=0)
        self.sounds = {}
        self.muted = False

    def add(self, name, samples):
        """Add a sound made by the builders above. samples: int16 array."""
        if self.pygame.mixer.get_init()[2] != 1:             # stereo anyway: same samples on both sides
            samples = np.column_stack((samples, samples))
        self.sounds[name] = self.pygame.sndarray.make_sound(samples)

    def add_wav(self, name, path):
        """Add a sound from a WAV file (e.g. speech saved by the game's extract_assets.py)."""
        self.sounds[name] = self.pygame.mixer.Sound(path)

    def seconds(self, name):
        """How long a sound lasts."""
        return self.sounds[name].get_length()

    def play(self, name):
        """Start a sound (unless muted)."""
        if not self.muted:
            self.sounds[name].play()
