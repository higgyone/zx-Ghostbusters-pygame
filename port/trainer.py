"""The trainer: cheats the original doesn't have, turned on or off on the setup screen
(port/options.py). With all of them off the game is the original.

The game's code checks `name in trainer.on` where a cheat changes something.
"""
MONEY, MEN, POWER, TRAPS = "infinite_money", "infinite_men", "infinite_power", "infinite_traps"
NAMES = (MONEY, MEN, POWER, TRAPS)
LABELS = {MONEY: "Infinite money", MEN: "Infinite men", POWER: "Infinite power", TRAPS: "Infinite traps"}
ABOUT = {
    MONEY: "Money never goes down: cars, equipment and the Marshmallow Man's damage cost nothing. "
           "You still need the money to buy.",
    MEN: "A man slimed at a building, or squashed at Zuul, is not lost.",
    POWER: "The backpacks never run down, and crossing the streams doesn't empty them.",
    TRAPS: "A caught ghost doesn't fill a trap (or the laser confinement system).",
}

on = set()      # the cheats turned on
