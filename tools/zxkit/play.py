"""Play a game in the simulator: press keys, wait, take screenshots.

This drives the original game through its menus and into play without an emulator, so
the same steps can be repeated exactly (for disassembly maps, assets or comparisons).

    p = Player("work/game.z80")
    p.press("1")              # pick keyboard controls
    p.wait(5)
    p.type("RYAN")
    p.press("ENTER")
    p.screenshot("work/name.png")
    p.save("work/after_name.z80")

Key names: 0-9, a-z, ENTER, SPACE, CS (caps shift), SS (symbol shift).
It uses SkoolKit's trace machinery (its internal Tracer class), with interrupts on.
"""
from skoolkit import CSimulator
from skoolkit.audio import BeeperOptions
from skoolkit.components import get_audio_writer
from skoolkit.kbtracer import KEYS
from skoolkit.simulator import Simulator
from skoolkit import simutils
from skoolkit.simutils import from_snapshot, get_state
from skoolkit.snapshot import Snapshot, write_snapshot
from skoolkit.trace import Tracer

from .screen import SCREEN_SIZE, screen_image
from .sim import TSTATES_PER_SECOND, _quiet

# register name -> index in SkoolKit's register list (IXh/IXl are "X"/"x", IYh/IYl "Y"/"y")
REGS = {"A": simutils.A, "F": simutils.F, "B": simutils.B, "C": simutils.C, "D": simutils.D, "E": simutils.E,
        "H": simutils.H, "L": simutils.L, "X": simutils.IXh, "x": simutils.IXl, "Y": simutils.IYh, "y": simutils.IYl,
        "SP": simutils.SP, "PC": simutils.PC, "IFF": simutils.IFF}
PAIRS = {"BC": "BC", "DE": "DE", "HL": "HL", "IX": "Xx", "IY": "Yy"}

# keyboard half-row port -> index in SkoolKit's 8-entry keyboard list
ROWS = {0xFEFE: 0, 0xFDFE: 1, 0xFBFE: 2, 0xF7FE: 3, 0xEFFE: 4, 0xDFFE: 5, 0xBFFE: 6, 0x7FFE: 7}


class Player:
    """A running game that can be given key presses."""

    def __init__(self, z80):
        """Start from a snapshot.

        z80: snapshot path (e.g. one written by sim.load or sim.run).
        """
        snap = Snapshot.get(z80)
        state = {"iff": snap.iff1, "im": snap.im}
        self.sim = from_snapshot(CSimulator or Simulator, snap, {}, state, {"fast_djnz": False, "fast_ldir": False})
        # port_fe=True: the tracer logs every speaker change, for save_sound
        self.tracer = Tracer(self.sim, snap.border, snap.out7ffd, snap.outfffd, list(snap.ay), snap.outfe, True)
        self.is128k = len(snap.ram(-1)) > 49152
        self.sim.set_tracer(self.tracer)
        self.held = set()        # names of keys held down now
        self.executed = set()    # every address the CPU has run an instruction at

    def _keyboard(self, scr, frame, border, keyboard):
        """Called by SkoolKit once a frame: set the keyboard rows from self.held.

        Returns True to keep running.
        """
        for i in range(8):
            keyboard[i] = 0
        for key in self.held:
            port, bits = KEYS[key]
            keyboard[ROWS[port]] |= bits ^ 0xFF
        return True

    def wait(self, seconds):
        """Run the game.

        seconds: Spectrum time to run for (0 or less does nothing; SkoolKit would run forever).
        """
        if seconds <= 0:
            return
        pc = self.sim.registers[24]
        with _quiet():   # trace prints "Stopped at ..." each time
            self.tracer.run(pc, -1, 0, int(seconds * TSTATES_PER_SECOND), True, self._keyboard, self.executed,
                            None, None, "$", "02X", "04X")

    def run_to(self, addr, max_seconds=5):
        """Run the game (interrupts and keys as in wait) until it reaches an address.

        addr: stop when the CPU is about to run the instruction here.
        max_seconds: give up after this much Spectrum time.
        Returns True if it got there. Handy for stepping a game loop one pass at a time.
        """
        pc = self.sim.registers[24]
        # no frame callback: SkoolKit then keeps tracer.keyboard as it is (with one it starts
        # each run with no keys down until the next frame, so short runs would miss keys)
        self.tracer.keyboard = [0] * 8
        self._keyboard(None, 0, 0, self.tracer.keyboard)
        with _quiet():
            self.tracer.run(pc, addr, 0, int(max_seconds * TSTATES_PER_SECOND), True, None, self.executed,
                            None, None, "$", "02X", "04X")
        return self.sim.registers[24] == addr

    def press(self, key, hold=0.3, after=0.3):
        """Press and release a key.

        key: key name (see module docs).
        hold: seconds to hold it down. after: seconds to run after letting go.
        """
        self.held.add(key)
        self.wait(hold)
        self.held.discard(key)
        self.wait(after)

    def call(self, addr, stop=0xFFF0, max_seconds=20, **regs):
        """Run one of the game's routines, like a CALL from BASIC, with interrupts off.

        addr: the routine's address.
        stop: an address the routine never runs; it is pushed as the return address.
        max_seconds: give up after this much Spectrum time.
        regs: registers to set first, e.g. A=3, DE=0x8000, HL=0x4000, IY=0x5C3A.
        Returns the address it stopped at (stop if the routine returned).
        """
        r = self.sim.registers
        for name, value in regs.items():
            if name in PAIRS:       # high byte, low byte
                hi, lo = PAIRS[name]
                r[REGS[hi]], r[REGS[lo]] = value >> 8, value & 0xFF
            else:
                r[REGS[name]] = value
        sp = 0xFF00
        self.sim.memory[sp:sp + 2] = [stop & 0xFF, stop >> 8]
        r[REGS["SP"]], r[REGS["IFF"]] = sp, 0
        with _quiet():
            self.tracer.run(addr, stop, 0, int(max_seconds * TSTATES_PER_SECOND), False, None, self.executed,
                            None, None, "$", "02X", "04X")
        return r[REGS["PC"]]

    def type(self, text):
        """Type letters, digits and spaces, one key at a time.

        text: what to type (letters are pressed without shift).
        """
        for ch in text:
            self.press("SPACE" if ch == " " else ch.lower())

    def ram(self):
        """Current RAM, $4000-$FFFF (49152 bytes; on a 128K, the banks paged in)."""
        mem = self.sim.memory
        return bytes(mem[0x4000:0x10000])

    def screenshot(self, png, scale=2):
        """Save the current screen.

        png: output path. scale: image size multiplier.
        """
        screen_image(self.ram()[:SCREEN_SIZE], scale).save(png)

    def save(self, z80):
        """Save the current state as a snapshot.

        z80: output path.
        """
        ram, registers, state, machine = get_state(self.sim)
        write_snapshot(z80, ram, registers, state, machine)

    def save_sound(self, wav):
        """Save the beeper sound since the last save_sound (or the start) as a WAV file.

        wav: output path.
        Returns False, writing nothing, if the speaker didn't move.
        """
        delays = self.tracer.get_delays()
        self.tracer.audio_log.clear()
        if not delays:
            return False
        with open(wav, "wb") as f:
            get_audio_writer().write_audio(f, delays, BeeperOptions(100, False, False, 0, self.is128k))
        return True

    def save_map(self, path):
        """Save the addresses run so far as a SkoolKit code map (for sna2ctl -m).

        path: output path. Adds to the file if it exists, so maps from several runs combine.
        """
        old = set()
        try:
            with open(path) as f:
                old = {int(line.strip()[1:], 16) for line in f if line.strip()}
        except FileNotFoundError:
            pass
        with open(path, "w") as f:
            for addr in sorted(old | self.executed):
                f.write(f"${addr:04X}\n")
