"""The account number the ending gives ($A514-$A54F) and the menu reads back ($83FA-$8454).

It is 24 bits written as 8 octal digits: the money's middle BCD byte ($D964), a check byte
made from the money and the player's name, and the money's top BCD byte ($D965).
"""


def stir(a):
    """$88F6, one step: shift a left, the new bottom bit made from some of its other bits.
    a: a byte. Returns the new byte."""
    c = a
    a = ((a << 1) & 0xFF) ^ c
    a = ((a << 1) & 0xFF) ^ c
    a = ((a << 2) & 0xFF) ^ c
    return ((c << 1) | (a >> 7 & 1)) & 0xFF


def name_sum(name):
    """$890A: the 20 bytes of the name (padded with spaces) added up, as a byte."""
    return sum(name.upper().ljust(20)[:20].encode()) & 0xFF


def check_byte(hi, mid, name):
    """The check byte for money bytes hi ($D965) and mid ($D964) and a name. Returns a byte."""
    a = ((hi + mid) & 0xFF) or 1
    for _ in range(name_sum(name) or 256):
        a = stir(a)
    return a


def money_bytes(money):
    """Money in dollars as the two BCD bytes the number holds: (hi, mid), whole hundreds."""
    d = f"{money // 100:04d}"
    return int(d[:2], 16), int(d[2:], 16)


def account_number(money, name):
    """The account number for some money (dollars, up to 999900) and a name. Returns 8 digits."""
    hi, mid = money_bytes(money)
    return f"{mid << 16 | check_byte(hi, mid, name) << 8 | hi:08o}"


def read_account(number, name):
    """What the menu does with a typed number. Returns the money it starts with, or None
    for "INVALID ACCOUNT NUMBER"."""
    n = int(number, 8)
    mid, check, hi = n >> 16 & 0xFF, n >> 8 & 0xFF, n & 0xFF
    if check != check_byte(hi, mid, name):
        return None
    return int(f"{hi:02X}{mid:02X}") * 100
