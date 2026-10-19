"""The ending's text screen ($A4EB-$A56E, notes/09-zuul.md): the result, the new credit
limit and the account number, typed out a character at a time by $8B92, then the laugh.
Or the bank's game over ($916E, notes/11-game-over.md): its message, then the laugh.
"""
from account import account_number
from building_screen import paint
from text_screen import TextScreen

END_COLOURS = [(20, 8, 11, 1, 0x32), (0, 11, 31, 1, 0x32)]   # $A5DF: the money and the number in red


class Ending(TextScreen):
    """The text screen, in its own back buffer and screen (as the game keeps them)."""

    def __init__(self, city, won, font, text):
        """city: the City, after the scene at Zuul. won: True if two men got in, or
        'foreclosed' for the bank's game over. font: from zxport.text.load_font.
        text: assets/text.json."""
        super().__init__(font)
        self.text = text
        self.last = None                 # what the last step stopped at: 'char' or 'speech'
        self.done = False
        self.gen = self.run(city, won)

    def step(self):
        """Run to the next character typed (or the laugh). Sets last, or done at the end."""
        if self.done:
            return
        try:
            self.last = next(self.gen)
        except StopIteration:
            self.last, self.done = None, True

    def run(self, city, won):
        """$A4EB-$A56B (or $916E-$9174 and on to $A565)."""
        if won == "foreclosed":
            yield from self.message(self.text["foreclosed"])
            yield "speech"
            return
        yield from self.message(self.text["end_won" if won else "end_lost"])
        paint(self.back, END_COLOURS)                                   # $A4FD
        yield from self.message(self.text["end_credit"])
        self.print_money(city.money)                                        # $A514
        yield from self.message(self.text["end_account"])
        for ch in account_number(city.money, city.name):                # $A557
            self.put(ch)
        yield from self.message(self.text["end_write"])
        yield "speech"                                                  # $A565: the laugh
