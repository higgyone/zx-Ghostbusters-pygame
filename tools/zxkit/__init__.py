"""zxkit: shared tools for porting ZX Spectrum games to Python/pygame.

Modules:
    game_file  read a .tap/.tzx/.z80 (or a .zip of one) and list its tape blocks
    screen     turn Spectrum screen memory (6912 bytes) into an image
    sim        load a tape and run a game in SkoolKit's Z80 simulator
    compare    find where two memory dumps differ
    play       run a game with key presses, screenshots and a code map
"""
