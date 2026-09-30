// Protect page: cover choice, recording, start position and capacity estimate.
(() => {
  const $ = (s) => document.querySelector(s);
  const cfg = window.ACW1;
  const input = $("#cover");
  let units = null; // size of the chosen cover
  let unitStep = 3; // values per start step

  // cover choice
  const hints = {
    image: "PNG, JPEG, BMP or WebP. The protected copy is always PNG, because JPEG compression would erase the hidden bits.",
    audio: "WAV, FLAC, OGG or MP3. It's converted to plain 16-bit WAV first, because the audio hiding code works on WAV.",
  };
  const isTeam = (mode) => mode === "team-image" || mode === "team-audio";
  const isImage = (mode) => mode === "image" || mode === "team-image";
  function setMode(mode) {
    $("#teamBox").hidden = !isTeam(mode);
    $("#pickBox").hidden = mode === "record" || isTeam(mode);
    $("#recBox").hidden = mode !== "record";
    if (mode === "image" || mode === "audio") {
      input.accept = mode === "image" ? "image/*" : "audio/*,.wav,.flac,.ogg,.mp3";
      $("#pickHint").textContent = hints[mode];
    }
    unitStep = isImage(mode) ? 3 : 1;
    $("#startUnit").textContent = isImage(mode) ? "pixel" : "byte";
    input.value = "";
    $("#previewBox").innerHTML = "";
    $("#recDone").hidden = true;
    units = null;
    if (isTeam(mode) && cfg.team[mode]) {
      const t = cfg.team[mode];
      units = t.units;
      $("#teamImage").hidden = mode !== "team-image";
      $("#teamAudio").hidden = mode !== "team-audio";
      if (mode === "team-image") $("#teamImage").src = cfg.teamUrl[mode];
      else $("#teamAudio").src = cfg.teamUrl[mode];
      $("#teamHint").textContent = mode === "team-image"
        ? `The picture the team's image tests use (${t.name}, ${t.describe}).`
        : `The tone the team's audio tests use (${t.describe}).`;
    }
    update();
  }
  const modeSelect = $("#mode");
  modeSelect.addEventListener("change", () => setMode(modeSelect.value));

  // file preview
  input.addEventListener("change", () => {
    const f = input.files[0];
    const box = $("#previewBox");
    box.innerHTML = "";
    units = null;
    if (!f) return update();
    const url = URL.createObjectURL(f);
    if (f.type.startsWith("image/")) {
      unitStep = 3;
      const img = new Image();
      img.className = "view";
      img.style.marginTop = "10px";
      img.onload = () => { units = img.naturalWidth * img.naturalHeight * 3; update(); };
      img.src = url;
      box.appendChild(img);
    } else {
      unitStep = 1;
      const a = document.createElement("audio");
      a.controls = true;
      a.src = url;
      box.appendChild(a);
      a.addEventListener("loadedmetadata", () => {
        if (/\.wav$/i.test(f.name)) units = Math.max(0, f.size - 44);
        else if (isFinite(a.duration)) units = Math.round(a.duration * 44100 * 2); // estimate
        update();
      });
    }
  });

  // recording
  const lvl = $("#lvl");
  for (let i = 0; i < 48; i++) lvl.appendChild(document.createElement("i"));
  const bars = [...lvl.children];
  let rec = null, timer = null, t0 = 0;
  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  $("#recBtn").addEventListener("click", async () => {
    if (rec) return stopRec();
    $("#recError").hidden = true;
    try {
      rec = new WavRecorder();
      await rec.start((level) => {
        bars.push(bars.shift());
        bars.forEach((b) => lvl.appendChild(b));
        bars[bars.length - 1].style.height = 3 + level * 27 + "px";
      });
    } catch (err) {
      rec = null;
      $("#recError").hidden = false;
      $("#recError").textContent = "Couldn't use the microphone: " + err.message +
        ". Allow microphone access, and open the app at http://127.0.0.1:5000 (browsers block the mic on plain http:// LAN addresses).";
      return;
    }
    t0 = performance.now();
    $("#recBtn").textContent = "Stop";
    $("#recDone").hidden = true;
    timer = setInterval(() => {
      const s = (performance.now() - t0) / 1000;
      $("#recTime").textContent = `${fmt(s)} / 0:30`;
      if (s >= 30) stopRec();
    }, 100);
  });
  function stopRec() {
    clearInterval(timer);
    const out = rec.stop();
    rec = null;
    $("#recBtn").textContent = "Record again";
    bars.forEach((b) => (b.style.height = "3px"));
    if (out.seconds < 2) {
      $("#recError").hidden = false;
      $("#recError").textContent = "That was under 2 seconds. Record a bit longer.";
      return;
    }
    const dt = new DataTransfer();
    dt.items.add(new File([out.blob], "recording.wav", { type: "audio/wav" }));
    input.files = dt.files;
    $("#recAudio").src = URL.createObjectURL(out.blob);
    $("#recInfo").textContent = `${out.seconds.toFixed(1)} s recorded at ${out.sampleRate} Hz. This will be the cover.`;
    $("#recDone").hidden = false;
    unitStep = 1;
    units = out.samples * 2;
    update();
  }

  // message presets
  const preset = $("#preset"), text = $("#text");
  let custom = preset.value === "custom" ? text.value : "";
  preset.addEventListener("change", () => {
    if (preset.value === "custom") { text.value = custom; text.placeholder = "Type your own message"; }
    else text.value = cfg.presets[preset.value];
    update();
  });
  text.addEventListener("input", () => { if (preset.value === "custom") custom = text.value; update(); });

  // package size estimate
  function noteBytes() {
    const enc = new TextEncoder();
    const m = text.value;
    let n = enc.encode(JSON.stringify(m)).length - 2;
    if (/[^\x00-\x7f]/.test(m)) n = JSON.stringify(m).length * 3;
    return cfg.baseRecord + n + enc.encode($("#media_id").value || "MEDIA_001").length;
  }
  const neededUnits = (nbits) => Math.ceil((32 + 8 * noteBytes()) / nbits);
  const maxStart = (nbits) => Math.floor((units - neededUnits(nbits)) / unitStep);

  function update() {
    const nbits = +$("#nbits").value;
    $("#nbitsOut").textContent = nbits;
    const meter = $("#capMeter"), label = $("#capText");
    const start = Math.max(0, +$("#start").value || 0);
    if (units === null) {
      meter.firstElementChild.style.width = "0";
      meter.classList.remove("full");
      label.textContent = input.files.length ? "checked exactly when you press Protect" : "choose a file first";
      return;
    }
    const need = neededUnits(nbits) * nbits;
    const have = Math.max(0, units - start * unitStep) * nbits;
    const fits = need <= have;
    meter.classList.toggle("full", !fits);
    meter.firstElementChild.style.width = Math.min(100, (need / Math.max(1, have)) * 100) + "%";
    label.innerHTML = `note needs about ${need.toLocaleString()} bits; from this start the file holds about ${have.toLocaleString()}: ` +
      (fits ? '<span class="tag ok">fits</span>' : '<span class="tag bad">too big, will be refused</span>');
    $("#startHint").textContent = `Where in the file the note begins (not the top-left corner). With ${nbits} LSB${nbits > 1 ? "s" : ""}, ` +
      `anything from 1 to about ${Math.max(0, maxStart(nbits)).toLocaleString()} fits. B needs this number and the LSB count to read the note, so tell B separately, not in the same email.`;
  }

  $("#randomStart").addEventListener("click", () => {
    if (units === null) { alert("Choose or record a file first."); return; }
    const hi = maxStart(+$("#nbits").value);
    if (hi < 1) { alert("The note doesn't fit in this file at this LSB count."); return; }
    $("#start").value = 1 + Math.floor(Math.random() * hi);
    update();
  });
  ["#nbits", "#start", "#media_id"].forEach((s) => $(s).addEventListener("input", update));

  $("#protectForm").addEventListener("submit", (e) => {
    if (!isTeam(modeSelect.value) && !input.files.length) {
      e.preventDefault();
      alert(modeSelect.value === "record" ? "Record some audio first." : "Choose a file first.");
      return;
    }
    e.target.classList.add("working");
    $("#go").disabled = true;
  });

  setMode(modeSelect.value);
})();
