# Ghostbusters for pygame

A port of the ZX Spectrum game Ghostbusters (Activision, 1984) to Python and pygame. It plays
the whole game: the controller menu, the title song, your name and account, the car and
equipment shops, the city map, the drives, the buildings, the Marshmallow Man, and Zuul.
The port was checked against the original, run in an emulator with the same keys, screen by
screen.

**This repository holds no part of the original game.** The pictures, sounds, text and font
are read from your own copy of the tape by `tools/extract_assets.py` and saved in `assets/`,
which is never shared.

## What you need
- Python 3.9 or later.
- Your own copy of the original 1984 Activision tape, as a `.tap` or `.tzx` file (or a `.zip`
  of one). The later re-releases (Elite's *The Story So Far*, *They Sold a Million 3*) have
  their code in other places, so they won't work.

## Setup
```
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt     # Linux/macOS: .venv/bin/python
.venv/Scripts/python tools/extract_assets.py "path/to/your/Ghostbusters.tap"
```
The extract takes under a minute. It loads the tape in [SkoolKit](https://skoolkit.ca)'s Z80
simulator, lets the game's own code draw its pictures and play its sounds, and saves them.

## Play
```
.venv/Scripts/python port/ghostbusters.py
```
- Q/A/O/P or the arrow keys move, Z fires. A joystick or gamepad works too.
- In the menus, type as on the Spectrum: backspace or SHIFT rubs out, and ENTER ends a line.
- Esc quits.
- It starts with a setup screen, not in the original, where a trainer's cheats can be turned on
  (infinite money, men, backpack power and traps). With them all off it is the original game.
- `--city` skips the start and goes straight to the city map. `--help` lists what else you can set.

[how-to-play.md](how-to-play.md) explains the game: the cars, the equipment, PK energy, bait,
the Marshmallow Man, and how to get into Zuul.

`tools/account_number.py NAME MONEY` makes the account number the ending gives you, so you
can start a new game with that much money.

## How it is made
- `port/` is the game. `port/zxport/` holds the Spectrum basics (screen, keys, window, sound,
  text) that are shared with other ports.
- `tools/extract_assets.py` reads the assets. `tools/zxkit/` runs the tape in SkoolKit's simulator.

The comments give the address of the original's code that each part copies (`$8B92` and so
on), and some name notes that are kept with the private working copy.

## Licence
The code here is MIT licensed (see LICENSE). Ghostbusters belongs to its owners. This port is
an unofficial fan project, and you need your own copy of the original to play it.
