# ACW1 P3-1: Flask GUI

The team's web GUI plus the **Attack Tests** page. Everything that hides, reads, signs or checks is
done by the teammates' own code in `src/`, called unchanged:

| Their file | Who | What the GUI calls |
|---|---|---|
| `src/crypto_engine.py` | crypto | `generate_key_pair`, `save/load_public_key_*`, `create_payload_dict`, `sign_payload`, `unpack_payload_package`, `verify_signature`, `verify_media_integrity`, `compute_file_hash` |
| `src/image_stego.py` | Nathan (image) | `embed_payload_in_image`, `extract_payload_from_image` |
| `src/audio_stego.py` | Patrick (audio) | `embed_payload_in_audio`, `extract_payload_from_audio` |
| `sample.png`, `src/test_member1_2.py` | team | the default sample image, and `generate_sample_wav()` for the default sample audio |

The GUI only adds `app.py`, `requirements.txt` and this `gui/` folder. It never changes `src/` or the
team's `keys/`. It keeps its own keys and files in `instance/`, which the team `.gitignore` already
ignores.

## Run it

```bash
python3 -m pip install -r requirements.txt
python3 app.py                  # open http://127.0.0.1:5000
PORT=5050 python3 app.py        # on a Mac, if port 5000 is taken by AirPlay Receiver
python3 gui/tests/test_gui.py   # GUI tests against the team's real code (~20 s)
```

Needs `src/audio_stego.py`, which is on the `patrick` branch until it's merged into `main`.
Open the app at 127.0.0.1 or localhost: browsers only allow the microphone there (or on HTTPS).

## Pages

- **1. Protect**
  - Cover: the **team's sample image or audio** (the default), your own photo or audio, or a
    **recording made in the browser**.
  - Message: short (a Learning Outcome), long (the Project Overview paragraph) or custom.
  - Settings: the **LSB count** (1–8) and a **start position**. *Pick a random spot* chooses one that fits.
  - Calls `create_payload_dict` → `sign_payload` → `embed_payload_in_image/audio`. If the note
    doesn't fit, the team's own capacity error is shown.
- **Result: what changed**
  - Numbers: how many pixels/samples changed, the biggest change to any value (never more than
    2ⁿ−1 with n LSBs), and PSNR/SNR.
  - Image: original and protected side by side, a map of the changed pixels, and a ×6 close-up.
  - Audio: two players, where the note sits in the clip, and a zoomed waveform.
  - A **bit-by-bit table** of the first values the note was written into: before and after in
    binary, with the replaced LSBs highlighted.
  - A download zip for person B, and the LSB count + start position to tell B separately.
- **2. Verify**
  - B uploads the file and `public_key.pem`, and types the LSB count + start position.
  - The GUI calls the team's functions in order, and the first "no" decides the result:

    | Their function | If it fails |
    |---|---|
    | `extract_payload_from_*` | **Wrong Start Location / Payload Missing** |
    | `unpack_payload_package` | **Cannot Verify** |
    | `verify_signature` | **Signature Invalid** |
    | `verify_media_integrity` | **Tampered** |
    | all pass | **Authentic** |
- **3. Attack Tests**
  - Makes 8 damaged copies of a protected file: edited content, one invisible bit, a bit in the
    signature, wrong key, wrong start, wrong LSB count, scrambled note, and an unprotected file.
  - Runs the same Verify on each, checks the result is the expected one, and saves a table to
    `evidence/` for the report.

## Files in `gui/`

| File | Does |
|---|---|
| `web.py` | The Flask routes (what happens when you open a page or press a button) |
| `protect.py`, `verify.py` | Collect the form input, call the team's functions in order, turn their answers into the spec's verdicts |
| `attacks.py` | The Attack Tests page |
| `compare.py` | The "what changed" views: side-by-side, changed-pixel map, close-up, bit table, PSNR/SNR, waveform |
| `media.py` | Checks upload types. Converts audio uploads/recordings to 16-bit WAV (the audio code reads WAV) |
| `samples.py` | Finds the team's sample image/audio |
| `safe_run.py` | Runs the team's extract function with an 8-second limit (see below) |
| `keys.py` | Keeps one key pair in `instance/keys/` so Protect and Verify use the same key |
| `messages.py` | The short/long message texts from the spec |
| `templates/`, `static/` | The pages' HTML, CSS and JavaScript. `static/recorder.js` records the mic and writes a WAV in the browser |
| `tests/test_gui.py` | The GUI tests |

## What the GUI shows about the team's code today

The GUI reports what their functions return and doesn't work around them:

1. **Genuine files show "Tampered".** `verify_media_integrity` compares the hash of the *protected*
   file with the hash stored in the note, which is the hash of the *original* file. Hiding the note
   changes the file, so they never match. When that function changes, Authentic shows with no GUI change.
2. **A wrong start position makes `extract_payload_from_image` run for about 50 s** (800×600 image,
   measured). It reads a garbage length and keeps going to the end of the image. The GUI stops waiting
   after 8 s and shows "Wrong Start Location / Payload Missing". The audio version stops straight away.
3. **"Wrong Start Location" and "Payload Missing" show as one result.** The payload format has no
   marker to tell "wrong spot" apart from "nothing hidden".
