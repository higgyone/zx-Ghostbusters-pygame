"""Load and run games in SkoolKit's Z80 simulator.

Loading a tape runs the tape's own loader (SkoolKit's tap2sna), exactly as a real Spectrum
would, so custom loaders and protection work too. Running a snapshot uses SkoolKit's trace,
with interrupts on, so the game runs as it does in an emulator (minus sound and keys).
"""
import contextlib
import io
import os

from skoolkit import tap2sna, trace
from skoolkit.snapshot import Snapshot

from .game_file import kind, read_game

TSTATES_PER_SECOND = 3_500_000   # a 48K Spectrum's clock: 3.5 MHz


@contextlib.contextmanager
def _quiet(enabled=True):
    """Hide SkoolKit's progress output while the block runs.

    enabled: False to show it.
    """
    if not enabled:
        yield
        return
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        yield


def load(path, out_z80, quiet=True):
    """Load a game into a snapshot.

    path: a .tap/.tzx (run through its own loader), a .z80 (copied as is), or a .zip of one.
    out_z80: where to write the snapshot of the moment the tape finished loading.
    quiet: hide SkoolKit's progress bar.
    Returns out_z80.
    """
    name, data = read_game(path)
    out_dir = os.path.dirname(os.path.abspath(out_z80))
    os.makedirs(out_dir, exist_ok=True)
    if kind(name) == ".z80":
        with open(out_z80, "wb") as f:
            f.write(data)
        return out_z80
    # tap2sna is given a plain file name in its own folder: on Windows it reads "C:\..." as a URL
    tape = os.path.join(out_dir, "_tape" + kind(name))
    with open(tape, "wb") as f:
        f.write(data)
    here = os.getcwd()
    os.chdir(out_dir)
    try:
        with _quiet(quiet):
            tap2sna.main([os.path.basename(tape), os.path.basename(out_z80)])
    finally:
        os.chdir(here)
        os.remove(tape)
    return out_z80


def run(in_z80, seconds, out_z80=None, out_png=None, quiet=True):
    """Run a snapshot for a while.

    in_z80: snapshot to start from.
    seconds: how long to run, in Spectrum time (not real time).
    out_z80: where to save the state at the end (optional).
    out_png: where to save the screen at the end (optional).
    quiet: hide SkoolKit's output.
    Returns out_z80.
    """
    outs = [p for p in (out_z80, out_png) if p]
    with _quiet(quiet):
        trace.main(["-M", str(int(seconds * TSTATES_PER_SECOND)), in_z80] + outs)
    return out_z80


def ram(z80):
    """The 48K of RAM a snapshot sees ($4000-$FFFF; on a 128K, the banks paged in).

    z80: snapshot path.
    Returns 49152 bytes; index 0 is address $4000.
    """
    return bytes(Snapshot.get(z80).ram())[:49152]


def machine(z80):
    """Which Spectrum a snapshot is for.

    z80: snapshot path.
    Returns "48K" or "128K".
    """
    return "128K" if len(Snapshot.get(z80).ram(-1)) > 49152 else "48K"


def pc(z80):
    """Where a snapshot's program counter is.

    z80: snapshot path.
    Returns the address (int).
    """
    return Snapshot.get(z80).pc

