"""zxport: the Spectrum basics a pygame port needs at run time, shared between ports.

Modules:
    screen   Spectrum pixels and colours: .scr files, masked sprites, attribute cells, to a pygame surface
    keys     keyboard (and joystick) to the directions and buttons a game reads
    window   the pygame window with its border, and a pacer that runs the game's passes at its own rate
    beeper   the beeper's square-wave sounds (the ROM's BEEP), tunes and WAV clips
    text     printing with an 8x8 font (the ROM font, saved by the game's extract_assets.py)

Only pygame, numpy and pillow are needed (no SkoolKit), so a public copy of a game can
include this folder as it is. Anything a single game does its own way stays in that game.
"""
