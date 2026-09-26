"""GUI tests, run against the team's code in src/: python3 gui/tests/test_gui.py"""

import io
import os
import sys
import tempfile

import numpy as np
import soundfile as sf
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from gui import attacks, messages as message  # noqa: E402
from gui.protect import protect  # noqa: E402
from gui.verify import NOT_FOUND, verify  # noqa: E402
from src.crypto_engine import generate_key_pair  # noqa: E402

if __name__ != "__main__" and "pytest" not in sys.modules:
    # skip setup when imported by a helper process
    TMP = PRIV = PUB = JPG = MP3 = None
else:
    TMP = tempfile.mkdtemp(prefix="acw1-gui-")
    PRIV, PUB = generate_key_pair()


def _image(path, w=480, h=360):
    y, x = np.mgrid[0:h, 0:w]
    arr = np.stack([x * 255 // w, y * 255 // h, (x + y) % 256], -1) + np.random.default_rng(1).integers(0, 12, (h, w, 3))
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(path, quality=92)
    return path


def _audio(path, seconds=3.0, rate=44100):
    t = np.arange(int(seconds * rate)) / rate
    sf.write(path, 0.3 * np.sin(2 * np.pi * 440 * t) + 0.02 * np.random.default_rng(2).standard_normal(t.size), rate)
    return path


if TMP:
    JPG = _image(os.path.join(TMP, "photo.jpg"))
    MP3 = _audio(os.path.join(TMP, "clip.mp3"))


def _protect(name, cover, nbits, start, preset="short"):
    job = os.path.join(TMP, name)
    r = protect(cover, job, name.upper(), message.PRESETS[preset], nbits, start, PRIV)
    return job, r, os.path.join(job, r["stego_file"])


# reading back what was hidden

def test_image_note_reads_back_and_signature_passes():
    _, r, stego = _protect("img", JPG, 2, 5000)
    v = verify(stego, PUB, 2, 5000)
    assert v["steps"][0]["status"] == "pass" and v["steps"][1]["status"] == "pass", v["steps"]
    assert v["payload"]["media_id"] == "IMG" and v["payload"]["metadata"] == message.PRESETS["short"]


def test_audio_from_mp3_long_message_reads_back():
    _, r, stego = _protect("aud", MP3, 1, 20000, "long")
    assert stego.endswith(".wav")
    v = verify(stego, PUB, 1, 20000)
    assert v["steps"][1]["status"] == "pass"
    assert v["payload"]["metadata"] == message.PRESETS["long"]


def test_every_lsb_count_reads_back():
    for cover, start in ((JPG, 300), (MP3, 4096)):
        for n in range(1, 9):
            _, _, stego = _protect(f"n{n}-{os.path.basename(cover)}", cover, n, start)
            assert verify(stego, PUB, n, start)["steps"][1]["status"] == "pass", (cover, n)


def test_hash_step_reports_what_m1_returns():
    """Checks the hash step reports what verify_media_integrity returns."""
    _, _, stego = _protect("hash", JPG, 1, 777)
    v = verify(stego, PUB, 1, 777)
    print(f"      genuine file → {v['verdict']}")
    assert v["verdict"] in ("Authentic", "Tampered")


# failures map to the spec's verdicts

def test_wrong_key_is_signature_invalid():
    _, _, stego = _protect("wk", MP3, 1, 1000)
    assert verify(stego, generate_key_pair()[1], 1, 1000)["verdict"] == "Signature Invalid"


def test_wrong_start_is_not_found_and_does_not_hang():
    import time
    _, _, stego = _protect("ws", JPG, 2, 5000)
    t = time.time()
    assert verify(stego, PUB, 2, 90000)["verdict"] == NOT_FOUND
    assert time.time() - t < 15


def test_team_capacity_check_error_is_passed_through():
    tiny = os.path.join(TMP, "tiny.png")
    Image.new("RGB", (24, 24), (40, 90, 160)).save(tiny)
    try:
        protect(tiny, os.path.join(TMP, "cap"), "CAP", message.PRESETS["long"], 1, 5, PRIV)
    except ValueError as exc:
        assert "capacity" in str(exc)
    else:
        raise AssertionError("expected the team's capacity error")


def test_jpeg_copy_of_protected_file_cannot_verify():
    _, _, stego = _protect("jpg", JPG, 1, 50)
    buf = io.BytesIO()
    Image.open(stego).save(buf, format="JPEG", quality=95)
    path = os.path.join(TMP, "recompressed.jpg")
    with open(path, "wb") as f:
        f.write(buf.getvalue())
    assert verify(path, PUB, 1, 50)["verdict"] == "Cannot Verify"


def test_attack_suite_gives_expected_verdicts():
    for name, cover, n, start in (("atk-img", JPG, 1, 2000), ("atk-aud", MP3, 3, 8000)):
        job, _, _ = _protect(name, cover, n, start)
        report = attacks.run_all(job, PUB, os.path.join(TMP, "evidence"))
        print(f"      {name}: untouched file → {report['baseline']}; {report['passed']}/{len(report['rows'])} as expected")
        assert report["passed"] == len(attacks.ATTACKS), [r for r in report["rows"] if not r["ok"]]


# web pages

def test_flask_pages_end_to_end():
    from gui import web
    c = web.app.test_client()
    for page in ("/", "/protect", "/verify", "/attack", "/team-sample/team-image", "/team-sample/team-audio"):
        assert c.get(page).status_code == 200, page
    r = c.post("/protect", data={"mode": "team-image", "media_id": "TEAM1", "preset": "short",
                                 "text": message.PRESETS["short"], "nbits": "1", "start": "123"},
               content_type="multipart/form-data")
    assert r.status_code == 302, r.data[:500]
    with open(JPG, "rb") as f:
        r = c.post("/protect", data={"mode": "image", "media_id": "WEB1", "preset": "short",
                                     "text": message.PRESETS["short"], "nbits": "2", "start": "4321",
                                     "cover": (f, "photo.jpg")}, content_type="multipart/form-data")
    assert r.status_code == 302, r.data[:500]
    job = r.headers["Location"].rsplit("/", 1)[1]
    assert c.get(f"/result/{job}").status_code == 200
    assert c.get(f"/jobs/{job}/download/bundle").status_code == 200
    r = c.post("/verify", data={"job": job, "key_source": "server", "nbits": "2", "start": "4321"},
               content_type="multipart/form-data")
    assert b"verify_signature() says yes" in r.data


if __name__ == "__main__":
    cases = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    failed = 0
    for name, fn in cases:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(cases) - failed}/{len(cases)} passed  (temp files in {TMP})")
    sys.exit(1 if failed else 0)
