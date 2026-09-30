"""Flask routes for the GUI."""

import json
import os
import re
import shutil
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
sys.path.insert(0, ROOT)

from flask import Flask, abort, redirect, render_template, request, send_from_directory, url_for  # noqa: E402
from werkzeug.utils import secure_filename  # noqa: E402

from . import attacks, compare, keys, media, messages, samples  # noqa: E402
from . import protect as protect_mod  # noqa: E402
from . import verify as verify_mod  # noqa: E402
from src.crypto_engine import create_payload_dict  # noqa: E402

app = Flask(__name__, instance_path=os.path.join(ROOT, "instance"))
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024

JOBS_DIR = os.path.join(app.instance_path, "jobs")
CHECKS_DIR = os.path.join(app.instance_path, "checks")
EVIDENCE_DIR = os.path.join(ROOT, "evidence")
ID_RE = re.compile(r"^[a-f0-9]{10}$")
SERVABLE = re.compile(r"^(cover|protected|preview-[a-z]+)\.(png|wav)$|^received\.(png|wav|bmp|tif|tiff)$")

PRIVATE_KEY, PUBLIC_KEY = keys.load_pair()


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def _job_dir(base: str, job_id: str) -> str:
    if not ID_RE.match(job_id or ""):
        abort(404)
    path = os.path.join(base, job_id)
    if not os.path.isdir(path):
        abort(404)
    return path


def _receipt(job_dir: str) -> dict:
    with open(os.path.join(job_dir, "receipt.json")) as f:
        return json.load(f)


def _recent_jobs(limit: int = 15) -> list[dict]:
    if not os.path.isdir(JOBS_DIR):
        return []
    jobs = []
    for job_id in os.listdir(JOBS_DIR):
        path = os.path.join(JOBS_DIR, job_id, "receipt.json")
        if ID_RE.match(job_id) and os.path.exists(path):
            with open(path) as f:
                r = json.load(f)
            jobs.append({"id": job_id, **r})
    return sorted(jobs, key=lambda j: j["created"], reverse=True)[:limit]


def _save_upload(file_storage, folder: str, stem: str) -> str:
    name = secure_filename(file_storage.filename or "")
    ext = os.path.splitext(name)[1].lower()
    media.kind_of("x" + ext)  # raises MediaError for unsupported types
    path = os.path.join(folder, stem + ext)
    file_storage.save(path)
    return path


def _base_record_len() -> int:
    """Estimates the signed package size for the capacity meter."""
    payload = create_payload_dict("", __file__, "")
    return 4 + len(json.dumps(payload, sort_keys=True).encode()) + PRIVATE_KEY.key_size // 8


BASE_RECORD = _base_record_len()


@app.context_processor
def globals_for_templates():
    return {"key_id": keys.fingerprint(PUBLIC_KEY)}


@app.route("/")
def home():
    return render_template("home.html", page="home")


# Protect

@app.route("/protect", methods=["GET", "POST"])
def protect():
    form = {"media_id": "", "preset": "short", "text": messages.PRESETS["short"], "nbits": 1, "start": "",
            "mode": "team-image"}
    error = None
    if request.method == "POST":
        form.update({k: request.form.get(k, form[k]) for k in ("media_id", "preset", "text", "mode", "start")})
        job_id = _new_id()
        job_dir = os.path.join(JOBS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        try:
            form["nbits"] = int(request.form.get("nbits", 1))
            try:
                start = int(form["start"])
            except ValueError:
                raise ValueError("Enter a start position (a whole number).") from None
            if form["mode"] in samples.TEAM:
                src = samples.path(form["mode"])
                if not src:
                    raise ValueError("The team's sample file isn't available. Upload or record a file instead.")
            else:
                upload = request.files.get("cover")
                if not upload or not upload.filename:
                    raise ValueError("Choose a photo or audio file, or record some audio first.")
                src = _save_upload(upload, job_dir, "upload")
            protect_mod.protect(src, job_dir, form["media_id"], form["text"], form["nbits"], start, PRIVATE_KEY)
            if src.startswith(job_dir) and os.path.basename(src).startswith("upload"):
                os.remove(src)
            return redirect(url_for("result", job_id=job_id))
        except (ValueError, media.MediaError) as exc:
            shutil.rmtree(job_dir, ignore_errors=True)
            error = str(exc)
    return render_template("protect.html", page="protect", form=form, error=error, presets=messages.PRESETS,
                           base_record=BASE_RECORD, team=samples.info())


@app.route("/team-sample/<mode>")
def team_sample(mode):
    path = samples.path(mode) if mode in samples.TEAM else None
    if not path:
        abort(404)
    return send_from_directory(os.path.dirname(path), os.path.basename(path))


@app.route("/result/<job_id>")
def result(job_id):
    job_dir = _job_dir(JOBS_DIR, job_id)
    receipt = _receipt(job_dir)
    views = (compare.image_views if receipt["kind"] == "image" else compare.audio_views)(job_dir, receipt)
    return render_template("result.html", page="protect", job_id=job_id, r=receipt, v=views)


@app.route("/jobs/<job_id>/<name>")
def job_file(job_id, name):
    if not SERVABLE.match(name):
        abort(404)
    return send_from_directory(_job_dir(JOBS_DIR, job_id), name)


@app.route("/jobs/<job_id>/download/<what>")
def job_download(job_id, what):
    job_dir = _job_dir(JOBS_DIR, job_id)
    receipt = _receipt(job_dir)
    safe_id = secure_filename(receipt["media_id"]) or "protected"
    if what == "bundle":
        path = protect_mod.bundle(job_dir, keys.PUBLIC_PATH)
        return send_from_directory(job_dir, os.path.basename(path), as_attachment=True,
                                   download_name=f"{safe_id}-send-to-B.zip")
    if what == "stego":
        ext = os.path.splitext(receipt["stego_file"])[1]
        return send_from_directory(job_dir, receipt["stego_file"], as_attachment=True,
                                   download_name=f"{safe_id}-protected{ext}")
    abort(404)


@app.route("/keys/public_key.pem")
def public_key():
    return send_from_directory(keys.KEY_DIR, "public_key.pem", as_attachment=True)


@app.route("/keys/new", methods=["POST"])
def new_keys():
    global PRIVATE_KEY, PUBLIC_KEY, BASE_RECORD
    PRIVATE_KEY, PUBLIC_KEY = keys.new_pair()
    BASE_RECORD = _base_record_len()
    return redirect(request.referrer or url_for("home"))


# Verify

@app.route("/verify", methods=["GET", "POST"])
def verify():
    result = error = None
    check_id = None
    chosen = request.values.get("job", "")
    key_source = request.form.get("key_source", "upload")
    if request.method == "POST":
        check_id = _new_id()
        check_dir = os.path.join(CHECKS_DIR, check_id)
        os.makedirs(check_dir, exist_ok=True)
        try:
            upload = request.files.get("stego")
            if upload and upload.filename:
                stego_path = _save_upload(upload, check_dir, "received")
            elif chosen:
                src_dir = _job_dir(JOBS_DIR, chosen)
                stego_name = _receipt(src_dir)["stego_file"]
                stego_path = os.path.join(check_dir, "received" + os.path.splitext(stego_name)[1])
                shutil.copy(os.path.join(src_dir, stego_name), stego_path)
            else:
                raise ValueError("Upload the file you received, or pick one protected on this computer.")

            if key_source == "server":
                pub = PUBLIC_KEY
            else:
                key_file = request.files.get("public_key")
                if not key_file or not key_file.filename:
                    raise ValueError("Upload the sender's public_key.pem (or tick 'use this computer's key').")
                pub = keys.public_from_upload(key_file.read())

            try:
                nbits, start = int(request.form.get("nbits", "")), int(request.form.get("start", ""))
            except ValueError:
                raise ValueError("Enter the LSB count and start position the sender gave you.") from None
            result = verify_mod.verify(stego_path, pub, nbits, start)
            result["key_id"] = keys.fingerprint(pub)
            result["received"] = os.path.basename(stego_path)
            result["kind"] = media.kind_of(stego_path)
        except (ValueError, media.MediaError) as exc:
            error = str(exc)
    return render_template("verify.html", page="verify", result=result, error=error, check_id=check_id,
                           jobs=_recent_jobs(), chosen=chosen, key_source=key_source, steps=verify_mod.STEPS,
                           form=request.form)


@app.route("/checks/<check_id>/<name>")
def check_file(check_id, name):
    if not SERVABLE.match(name):
        abort(404)
    return send_from_directory(_job_dir(CHECKS_DIR, check_id), name)


# Attack tests

@app.route("/attack", methods=["GET", "POST"])
def attack():
    report = error = None
    chosen = request.values.get("job", "")
    jobs = _recent_jobs()
    if request.method == "POST":
        try:
            report = attacks.run_all(_job_dir(JOBS_DIR, chosen), PUBLIC_KEY, EVIDENCE_DIR)
        except (ValueError, media.MediaError) as exc:
            error = str(exc)
    return render_template("attack.html", page="attack", jobs=jobs, chosen=chosen or (jobs[0]["id"] if jobs else ""),
                           report=report, error=error, attack_list=attacks.ATTACKS)


@app.errorhandler(413)
def too_big(_):
    return render_template("home.html", page="home", error="That file is too big (limit 60 MB)."), 413

