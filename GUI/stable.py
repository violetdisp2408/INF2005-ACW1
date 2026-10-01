"""The "stable copy" that gets hashed, so a genuine protected file can verify as Authentic.

Hiding the note changes the LSBs it's written into, so a hash of the whole cover can never
match the protected file. Instead, both sides hash a copy of the file with exactly those LSBs
set to 0 (the spec's "selected stable representation"):

- Protect: stable copy of the cover   → create_payload_dict() hashes it → note is signed and hidden
- Verify:  stable copy of the received file (same bits zeroed) → verify_media_integrity() on it

Every other bit of the file is still covered by the hash, and the zeroed bits hold the note
itself, which the signature covers. The team's functions are called unchanged.
"""

import numpy as np

from . import media as M


def note_region(media: M.Media, start: int, nbits: int, package_len: int) -> slice:
    """Values that hold the note (its 32-bit length header + package)."""
    first = start * media.units_per_step
    return slice(first, min(media.unit_count, first + M.units_for(package_len, nbits)))


def stable_copy(path: str, out_path: str, start: int, nbits: int, package_len: int,
                allow_lossy: bool = False) -> str:
    """Saves path with the note's LSBs set to 0, as a PNG or WAV."""
    media = M.load(path, allow_lossy=allow_lossy)
    units = media.units.copy()
    units[note_region(media, start, nbits, package_len)] &= np.uint8((0xFF << nbits) & 0xFF)
    return M.save_units(media, units, out_path)
