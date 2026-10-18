"""Make or check Ghostbusters account numbers (the ending's "new account number").

Usage: python tools/account_number.py NAME MONEY      the number that starts NAME with MONEY dollars
       python tools/account_number.py NAME --check NUMBER   what the game makes of NUMBER for NAME

Type the same name in the game, say yes to "DO YOU HAVE AN ACCOUNT?" and type the number.
Money is kept in whole hundreds, up to $999900. See notes/09-zuul.md.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "port"))
from account import account_number, read_account   # noqa: E402


def main():
    """Command line: NAME (MONEY | --check NUMBER)."""
    ap = argparse.ArgumentParser(description="Make or check Ghostbusters account numbers.")
    ap.add_argument("name")
    ap.add_argument("money", nargs="?", type=int, help="dollars, up to 999900")
    ap.add_argument("--check", help="an account number to check")
    args = ap.parse_args()
    if args.check:
        money = read_account(args.check, args.name)
        print("INVALID ACCOUNT NUMBER" if money is None else f"starts with ${money}")
    elif args.money is not None and 0 <= args.money <= 999900:
        print(account_number(args.money, args.name))
    else:
        ap.error("give MONEY (0-999900) or --check NUMBER")


if __name__ == "__main__":
    main()
