"""Runs the team's extract functions in a separate process with a time limit."""

import multiprocessing as mp
import os
import queue

EXTRACT_TIMEOUT = 8.0  # seconds


class ExtractTimeout(Exception):
    pass


def _worker(out, kind, path, nbits, start):
    """Runs the extract function and sends back the result."""
    try:
        if kind == "image":
            from src.image_stego import extract_payload_from_image as extract
        else:
            from src.audio_stego import extract_payload_from_audio as extract
        out.put(("ok", extract(path, nbits, start)))
    except Exception as exc:
        out.put(("error", f"{type(exc).__name__}: {exc}"))


def extract(kind: str, path: str, nbits: int, start: int, timeout: float = EXTRACT_TIMEOUT) -> bytes:
    """Calls the image or audio extract function with a time limit."""
    ctx = mp.get_context(os.environ.get("ACW1_MP_START"))
    out = ctx.Queue()
    proc = ctx.Process(target=_worker, args=(out, kind, path, nbits, start), daemon=True)
    proc.start()
    try:
        status, value = out.get(timeout=timeout)
    except queue.Empty:
        proc.terminate()
        proc.join()
        raise ExtractTimeout(f"no note found within {timeout:g} s")
    proc.join()
    if status == "error":
        raise RuntimeError(value)
    return value
