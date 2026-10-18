"""Read game files: .tap, .tzx, .z80, or a .zip holding one of them."""
import os
import zipfile

from skoolkit.tape import parse_tap, parse_tzx

KINDS = (".tap", ".tzx", ".z80")


def read_game(path):
    """Read a game file, looking inside a .zip if needed.

    path: a .tap, .tzx or .z80 file, or a .zip holding one.
    Returns (name, data): the game file's name (inside the zip, if any) and its bytes.
    """
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as zf:
            name = next((n for n in zf.namelist() if n.lower().endswith(KINDS)), None)
            if name is None:
                raise ValueError(f"{path}: no .tap, .tzx or .z80 inside")
            return name, zf.read(name)
    with open(path, "rb") as f:
        return os.path.basename(path), f.read()


def kind(name):
    """File type from a name.

    name: a file name.
    Returns ".tap", ".tzx", ".z80", or None if it is none of them.
    """
    ext = os.path.splitext(name)[1].lower()
    return ext if ext in KINDS else None


def tape_blocks(name, data):
    """The data blocks on a tape, in order.

    name: file name (its extension says .tap or .tzx).
    data: the file's bytes.
    Returns a list of bytes, one per block that carries data: flag byte first, checksum byte last.
    Turbo and custom-loader blocks are included; tones, pauses and text blocks are not.
    """
    tape = parse_tap(data) if kind(name) == ".tap" else parse_tzx(data)
    return [bytes(b.data) for b in tape.blocks if b.data]


def find_games(folder):
    """Every game file under a folder.

    folder: directory to search, including subfolders.
    Returns a sorted list of paths: .tap/.tzx/.z80 files, and .zip files holding one.
    """
    found = []
    for root, _, files in os.walk(folder):
        for f in files:
            path = os.path.join(root, f)
            if kind(f):
                found.append(path)
            elif f.lower().endswith(".zip"):
                with zipfile.ZipFile(path) as zf:
                    if any(kind(n) for n in zf.namelist()):
                        found.append(path)
    return sorted(found)
