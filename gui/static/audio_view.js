// Draws the audio waveform views on the result page.
(() => {
  const v = window.AUDIO_VIEW;
  const css = getComputedStyle(document.documentElement);
  const col = (n) => css.getPropertyValue(n).trim();

  function sharp(c) {
    const r = window.devicePixelRatio || 1, w = c.clientWidth, h = c.height / (c.width / w);
    c.width = w * r; c.height = h * r;
    const x = c.getContext("2d");
    x.scale(r, r);
    return [x, w, h];
  }

  const env = document.getElementById("env");
  const [ex, ew, eh] = sharp(env);
  ex.fillStyle = col("--stego");
  ex.globalAlpha = 0.35;
  v.regions.forEach(([a, b]) => ex.fillRect(Math.min(ew - 4, a * ew), 0, Math.max(4, (b - a) * ew), eh));
  ex.globalAlpha = 1;
  ex.fillStyle = col("--cover");
  v.envelope.forEach(([lo, hi], i) => {
    const x = (i / v.envelope.length) * ew;
    ex.fillRect(x, eh / 2 - hi * eh / 2, Math.max(1, ew / v.envelope.length), Math.max(1, (hi - lo) * eh / 2));
  });

  const z = document.getElementById("zoom");
  const [zx, zw, zh] = sharp(z);
  const all = v.zoom_cover.concat(v.zoom_stego);
  const lo = Math.min(...all), hi = Math.max(...all), pad = (hi - lo) * 0.1 || 0.001;
  const y = (s) => zh - ((s - lo + pad) / (hi - lo + 2 * pad)) * zh;
  const line = (arr, color, width, dash) => {
    zx.strokeStyle = color; zx.lineWidth = width; zx.setLineDash(dash);
    zx.beginPath();
    arr.forEach((s, i) => { const px = (i / (arr.length - 1)) * zw; i ? zx.lineTo(px, y(s)) : zx.moveTo(px, y(s)); });
    zx.stroke();
  };
  line(v.zoom_cover, col("--cover"), 2.5, []);
  line(v.zoom_stego, col("--stego"), 1.5, [4, 3]);
  zx.setLineDash([]);
  zx.fillStyle = col("--stego");
  v.zoom_cover.forEach((s, i) => {
    if (s !== v.zoom_stego[i]) zx.fillRect((i / (v.zoom_cover.length - 1)) * zw - 1.5, zh - 6, 3, 6);
  });
})();
