"""Checks uploads, converts audio to WAV and loads pixel/sample data."""

import math
import os
import shutil
import wave
from dataclasses import dataclass

import numpy as np
import soundfile as sf
from PIL import Image

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
AUDIO_EXTS = {".wav", ".flac", ".ogg", ".mp3", ".aiff", ".aif"}


class MediaError(ValueError):
    """Raised when a file can't be used."""


@dataclass
class Media:
    kind: str            # "image" or "audio"
    path: str
    units: np.ndarray    # one uint8 per pixel channel or WAV byte
    meta: dict           # size and format details

    @property
    def unit_count(self) -> int:
        return int(self.units.size)

    @property
    def units_per_step(self) -> int:
        """Values per start step: 3 for a pixel, 1 for an audio byte."""
        return 3 if self.kind == "image" else 1

    @property
    def step_name(self) -> str:
        return "pixel" if self.kind == "image" else "byte"

    def describe(self) -> str:
        if self.kind == "image":
            return f"{self.meta['width']}×{self.meta['height']} image"
        m = self.meta
        return f"{m['seconds']:.1f} s WAV, {m['channels']} ch, {m['rate']} Hz, {m['sampwidth'] * 8}-bit"


def kind_of(path: str) -> str:
    """Returns "image" or "audio" from the file extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in AUDIO_EXTS:
        return "audio"
    raise MediaError(f"Unsupported file type '{ext or '?'}'. Use an image (PNG, JPEG, ...) or audio (WAV, MP3, ...).")


def prepare_cover(src: str, out_dir: str) -> tuple[str, list[str]]:
    """Copies an image, or converts audio to 16-bit WAV, for the embed functions."""
    if kind_of(src) == "image":
        try:
            Image.open(src).verify()
        except Exception as exc:
            raise MediaError(f"Couldn't open the image: {exc}") from exc
        notes = []
        ext = os.path.splitext(src)[1].lower()
        if ext in {".jpg", ".jpeg", ".webp"}:
            notes.append("The protected copy is saved as PNG: JPEG/WebP compression would erase the hidden bits.")
        out = os.path.join(out_dir, "cover" + ext)
        if os.path.abspath(src) != os.path.abspath(out):
            shutil.copyfile(src, out)
        return out, notes

    try:
        data, rate = sf.read(src, dtype="int16", always_2d=True)
    except Exception as exc:
        raise MediaError(
            "Couldn't read that audio file. WAV, FLAC, OGG and MP3 work; for other formats "
            f"(e.g. m4a) convert to WAV first. ({exc})"
        ) from exc
    if data.shape[0] < rate:
        raise MediaError("The audio is shorter than 1 second. Record or upload something longer.")
    notes = []
    ext = os.path.splitext(src)[1].lower()
    if ext != ".wav":
        notes.append(f"Converted {ext.lstrip('.').upper()} to 16-bit WAV (the audio hiding code reads WAV).")
    elif sf.info(src).subtype != "PCM_16":
        notes.append(f"Converted {sf.info(src).subtype} WAV to 16-bit WAV.")
    out = os.path.join(out_dir, "cover.wav")
    sf.write(out, data, rate, subtype="PCM_16", format="WAV")
    return out, notes


def load(path: str, allow_lossy: bool = False) -> Media:
    """Loads a lossless image or WAV file."""
    kind = kind_of(path)
    if kind == "image":
        try:
            img = Image.open(path)
            fmt = img.format
            img = img.convert("RGB")
        except Exception as exc:
            raise MediaError(f"Couldn't open the image: {exc}") from exc
        if fmt not in ("PNG", "BMP", "TIFF") and not allow_lossy:
            raise MediaError(
                f"This image is {fmt}, which is compressed, so any hidden bits are already gone. "
                "Protected files are always PNG."
            )
        units = np.array(img, dtype=np.uint8).flatten()
        return Media("image", path, units, {"width": img.width, "height": img.height})

    try:
        with wave.open(path, "rb") as w:
            if w.getcomptype() != "NONE":
                raise MediaError("Only uncompressed WAV files can hold hidden data.")
            params = w.getparams()
            frames = w.readframes(w.getnframes())
    except MediaError:
        raise
    except Exception as exc:
        raise MediaError(
            "This isn't a readable WAV file. Protected audio is always WAV. An MP3 or other "
            f"compressed copy would have lost the hidden bits. ({exc})"
        ) from exc
    meta = {
        "channels": params.nchannels,
        "sampwidth": params.sampwidth,
        "rate": params.framerate,
        "frames": params.nframes,
        "seconds": params.nframes / params.framerate if params.framerate else 0,
    }
    return Media("audio", path, np.frombuffer(frames, dtype=np.uint8).copy(), meta)


def units_for(n_bytes: int, nbits: int) -> int:
    """Returns the values needed to hide n_bytes, including the 32-bit length header."""
    return math.ceil((32 + 8 * n_bytes) / nbits)


def max_start(media: Media, n_bytes: int, nbits: int) -> int:
    """Returns the largest start position where n_bytes still fits."""
    free_units = media.unit_count - units_for(n_bytes, nbits)
    return free_units // media.units_per_step
