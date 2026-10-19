"""Binary-coded decimal as the Z80 does it: each byte holds two digits ($47 is 47).

add and sub are ADD/ADC or SUB/SBC followed by DAA, exact even for bytes that aren't BCD
(a game may count down a binary number with DAA). The other functions turn numbers into
BCD bytes and back.
"""


def add(a, b, carry=0):
    """ADD A,b (ADC with carry) then DAA. a, b: bytes. carry: 0 or 1. Returns (byte, carry)."""
    t = a + b + carry
    half = (a & 0x0F) + (b & 0x0F) + carry > 0x0F
    r, c = t & 0xFF, t > 0xFF
    return (r + _daa_diff(r, c, half)) & 0xFF, int(c or r > 0x99)


def sub(a, b, carry=0):
    """SUB b (SBC with carry) then DAA. a, b: bytes. carry: 0 or 1 (the borrow). Returns (byte, carry)."""
    t = a - b - carry
    half = (a & 0x0F) - (b & 0x0F) - carry < 0
    r, c = t & 0xFF, t < 0
    return (r - _daa_diff(r, c, half)) & 0xFF, int(c or r > 0x99)


def _daa_diff(r, c, half):
    """What DAA adds or takes away: $06 for the low digit, $60 for the high one."""
    return (0x06 if half or (r & 0x0F) > 9 else 0) | (0x60 if c or r > 0x99 else 0)


def to_bcd(n):
    """A number 0-99 as a BCD byte (47 -> $47)."""
    return (n // 10) << 4 | n % 10


def from_bcd(b):
    """A BCD byte as a number ($47 -> 47); a digit over 9 counts as its value ($1A -> 20)."""
    return (b >> 4) * 10 + (b & 0x0F)


def to_bytes(n, count):
    """A number as count BCD bytes, highest first (123456, 3 -> [$12, $34, $56]).
    Digits above the bytes' room are dropped."""
    n %= 100 ** count
    return [to_bcd(n // 100 ** i % 100) for i in reversed(range(count))]


def from_bytes(data):
    """BCD bytes, highest first, as a number ([$12, $34] -> 1234), each as from_bcd reads it."""
    n = 0
    for b in data:
        n = n * 100 + from_bcd(b)
    return n
