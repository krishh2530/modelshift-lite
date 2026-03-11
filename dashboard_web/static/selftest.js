(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const isNum = (v) => typeof v === "number" && Number.isFinite(v);

  const statusPill = $("statusPill");
  const testSelect = $("testSelect");
  const seedInput = $("seedInput");
  const runBtn = $("runBtn");

  const metaLine = $("metaLine");
  const jsonBox = $("jsonBox");
  const checksBox = $("checksBox");

  const kPredClean = $("kPredClean");
  const kPredDrift = $("kPredDrift");
  const kHealthClean = $("kHealthClean");
  const kHealthDrift = $("kHealthDrift");

  const mixSlider = $("mixSlider");
  const mixVal = $("mixVal");
  const playBtn = $("playBtn");
  const resetBtn = $("resetBtn");

  const histCanvas = $("histCanvas");
  const ksGauge = $("ksGauge");
  const healthGauge = $("healthGauge");
  const featCanvas = $("featCanvas");

  let latest = null;

  // animation state
  const anim = {
    playing: false,
    mix: 0,          // 0..1
    speed: 0.35,     // mix/sec
    lastT: performance.now(),
    kpiStart: null,
    kpiDur: 900,
    kpiFrom: { pc: 0, pd: 0, hc: 0, hd: 0 },
    kpiTo:   { pc: 0, pd: 0, hc: 0, hd: 0 }
  };

  // --- NEW: Mouse tracking for tooltips ---
  const mouse = { x: -1, y: -1, active: false };

  if (histCanvas) {
    histCanvas.addEventListener('mousemove', (e) => {
      const rect = histCanvas.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
      mouse.active = true;
    });
    histCanvas.addEventListener('mouseleave', () => { mouse.active = false; });
  }

  function setPill(mode, text) {
    if (!statusPill) return;
    statusPill.classList.remove("good", "bad", "run");
    if (mode) statusPill.classList.add(mode);
    statusPill.querySelector(".txt").textContent = text;
  }

  function fmt(n, d = 4) {
    if (!isNum(n)) return "—";
    return n.toFixed(d);
  }

  function fmt2(n) {
    if (!isNum(n)) return "—";
    return n.toFixed(2);
  }

  function resizeCanvas(c, cssH) {
    const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    const rect = c.getBoundingClientRect();
    const w = Math.max(1, Math.floor(rect.width * dpr));
    const h = Math.max(1, Math.floor((cssH ?? rect.height) * dpr));
    if (c.width !== w || c.height !== h) {
      c.width = w;
      c.height = h;
    }
    const ctx = c.getContext("2d");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
    return { ctx, w: rect.width, h: cssH ?? rect.height };
  }

  function drawHistogram(data) {
    if (!data || !histCanvas) return;
    const { ctx, w, h } = resizeCanvas(histCanvas, 220);

    const bins = data.bins || [];
    const base = data.baseline || [];
    const clean = data.clean || [];
    const drift = data.drifted || [];
    const n = Math.min(base.length, clean.length, drift.length);

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "rgba(255,255,255,0.06)";
    ctx.fillRect(0, 0, w, h);

    if (n < 2) {
      ctx.fillStyle = "rgba(255,255,255,0.7)";
      ctx.font = "12px ui-monospace, Menlo, Consolas, monospace";
      ctx.fillText("No histogram data", 12, 18);
      return;
    }

    // mix determines how much drifted replaces clean (playable)
    const mix = anim.mix;
    const cur = [];
    for (let i = 0; i < n; i++) {
      cur.push((1 - mix) * clean[i] + mix * drift[i]);
    }

    const maxV = Math.max(...base, ...clean, ...drift, ...cur, 1);
    const padL = 34, padR = 10, padT = 10, padB = 26;
    const gx0 = padL, gx1 = w - padR, gy0 = padT, gy1 = h - padB;

    // grid
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    for (let t = 0; t <= 4; t++) {
      const y = gy0 + (t / 4) * (gy1 - gy0);
      ctx.beginPath(); ctx.moveTo(gx0, y); ctx.lineTo(gx1, y); ctx.stroke();
    }

    // axis labels
    ctx.fillStyle = "rgba(255,255,255,0.70)";
    ctx.font = "11px ui-monospace, Menlo, Consolas, monospace";
    ctx.fillText("count", 6, 16);
    ctx.fillText("p", gx1 - 8, h - 8);

    const bw = (gx1 - gx0) / n;
    const yMap = (v) => gy1 - (v / maxV) * (gy1 - gy0);

    function bars(arr, color, alpha) {
      ctx.fillStyle = color;
      ctx.globalAlpha = alpha;
      for (let i = 0; i < n; i++) {
        const x = gx0 + i * bw + 1;
        const y = yMap(arr[i]);
        ctx.fillRect(x, y, Math.max(1, bw - 2), gy1 - y);
      }
      ctx.globalAlpha = 1;
    }

    // baseline (behind)
    bars(base, "rgba(255,255,255,0.90)", 0.20);
    // clean (blue-ish)
    bars(clean, "rgba(134,168,255,0.95)", 0.18);
    // current animated mix
    bars(cur, "rgba(209,31,31,0.92)", 0.20);

    // animated sweep line
    const sweepX = gx0 + mix * (gx1 - gx0);
    ctx.strokeStyle = "rgba(255,255,255,0.35)";
    ctx.setLineDash([6, 8]);
    ctx.beginPath(); ctx.moveTo(sweepX, gy0); ctx.lineTo(sweepX, gy1); ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = "rgba(255,255,255,0.70)";
    ctx.font = "11px ui-monospace, Menlo, Consolas, monospace";
    ctx.fillText(`mix=${Math.round(mix * 100)}%`, gx0 + 8, gy0 + 14);

    // --- NEW: Interactive Tooltip ---
    if (mouse.active && n > 0) {
      const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
      const cx = mouse.x * dpr;
      const cy = mouse.y * dpr;

      if (cx >= gx0 && cx <= gx1 && cy >= gy0 && cy <= gy1) {
        const i = Math.floor((cx - gx0) / bw);
        if (i >= 0 && i < n) {
          // Highlight the hovered bar
          ctx.fillStyle = "rgba(255,255,255,0.15)";
          ctx.fillRect(gx0 + i * bw, gy0, bw, gy1 - gy0);

          // Draw floating tooltip box
          const ttW = 120, ttH = 55;
          let tx = cx + 15, ty = cy - ttH - 10;
          if (tx + ttW > w) tx = cx - ttW - 15; // Prevent clipping right edge
          if (ty < 0) ty = cy + 15;             // Prevent clipping top edge

          ctx.fillStyle = "rgba(10,14,20,0.95)";
          ctx.fillRect(tx, ty, ttW, ttH);
          ctx.strokeStyle = "rgba(255,255,255,0.2)";
          ctx.strokeRect(tx, ty, ttW, ttH);

          ctx.fillStyle = "rgba(255,255,255,0.9)";
          ctx.font = "11px ui-monospace, Menlo, Consolas, monospace";
          ctx.fillText(`Bin: ${i+1}/${n}`, tx + 8, ty + 16);
          ctx.fillStyle = "rgba(209,31,31,0.95)";
          ctx.fillText(`Current: ${cur[i].toFixed(1)}`, tx + 8, ty + 32);
          ctx.fillStyle = "rgba(255,255,255,0.5)";
          ctx.fillText(`Base:    ${base[i]}`, tx + 8, ty + 46);
        }
      }
    }
  }

  function drawGauge(canvas, value01, label, color) {
    const { ctx, w, h } = resizeCanvas(canvas, 160);
    ctx.clearRect(0, 0, w, h);

    const cx = w / 2, cy = h / 2 + 18;
    const r = Math.min(w, h) * 0.36;

    // base ring
    ctx.lineWidth = 14;
    ctx.strokeStyle = "rgba(255,255,255,0.10)";
    ctx.beginPath();
    ctx.arc(cx, cy, r, Math.PI, 2 * Math.PI);
    ctx.stroke();

    const v = Math.max(0, Math.min(1, value01));
    const end = Math.PI + v * Math.PI;

    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.arc(cx, cy, r, Math.PI, end);
    ctx.stroke();

    // needle
    const nx = cx + Math.cos(end) * (r + 4);
    const ny = cy + Math.sin(end) * (r + 4);
    ctx.strokeStyle = "rgba(255,255,255,0.65)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(nx, ny);
    ctx.stroke();

    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.font = "12px ui-monospace, Menlo, Consolas, monospace";
    ctx.textAlign = "center";
    ctx.fillText(label, cx, 18);
    ctx.font = "26px ui-monospace, Menlo, Consolas, monospace";
    ctx.fillText(`${Math.round(v * 100)}%`, cx, cy + 10);
    ctx.textAlign = "left";
  }

  // --- CHANGED: added 'now' parameter for pulsing animation ---
  function drawFeatures(rows, now) {
    if (!featCanvas) return;
    const { ctx, w, h } = resizeCanvas(featCanvas, 220);
    ctx.clearRect(0, 0, w, h);

    const data = Array.isArray(rows) ? rows.slice(0, 10) : [];
    if (!data.length) {
      ctx.fillStyle = "rgba(255,255,255,0.70)";
      ctx.font = "12px ui-monospace, Menlo, Consolas, monospace";
      ctx.fillText("No feature drift data", 12, 18);
      return;
    }

    const padL = 220, padR = 18, padT = 16, padB = 18;
    const gx0 = padL, gx1 = w - padR, gy0 = padT, gy1 = h - padB;
    const rowH = (gy1 - gy0) / data.length;

    const mx = Math.max(...data.map(r => Number(r.ks_statistic) || 0), 1e-6);
    const mix = anim.mix; // re-use mix to animate bar growth

    ctx.font = "12px ui-monospace, Menlo, Consolas, monospace";

    for (let i = 0; i < data.length; i++) {
      const r = data[i];
      const y = gy0 + i * rowH + 6;
      const ks = Number(r.ks_statistic) || 0;
      const frac = (ks / mx) * (0.25 + 0.75 * mix); // animate
      const barW = frac * (gx1 - gx0);

      // label
      ctx.fillStyle = "rgba(255,255,255,0.80)";
      ctx.fillText(String(r.feature).toUpperCase(), 12, y + 10);

      // bar bg
      ctx.fillStyle = "rgba(255,255,255,0.06)";
      ctx.fillRect(gx0, y, gx1 - gx0, 16);

      // bar fg by severity
      let col = "rgba(80,200,120,0.85)";
      const sev = String(r.severity || "").toUpperCase();
      
      // --- NEW: Pulsing Sine Wave Animation ---
      if (sev.includes("CRITICAL") || sev.includes("HIGH")) {
        const pulse = now ? (0.70 + 0.30 * Math.sin(now / 150)) : 1.0; 
        col = `rgba(209,31,31,${pulse.toFixed(2)})`;
      } else if (sev.includes("MEDIUM")) {
        col = "rgba(255,176,0,0.90)";
      }
      
      ctx.fillStyle = col;
      ctx.fillRect(gx0, y, barW, 16);

      // value
      ctx.fillStyle = "rgba(255,255,255,0.75)";
      ctx.fillText(`KS=${ks.toFixed(4)} • ${sev || "—"}`, gx0 + 8, y + 12);
    }
  }

  function renderChecks(checks) {
    if (!checksBox) return;
    checksBox.innerHTML = "";
    const arr = Array.isArray(checks) ? checks : [];
    for (const c of arr) {
      const pass = !!c.pass;
      const div = document.createElement("div");
      div.className = "check";
      div.innerHTML = `
        <div>
          <div style="font-weight:900;opacity:.92">${String(c.name || "CHECK")}</div>
          <div style="opacity:.72;margin-top:2px">threshold: ${String(c.threshold ?? "—")} • value: ${typeof c.value === "object" ? JSON.stringify(c.value) : String(c.value ?? "—")}</div>
        </div>
        <div class="badge ${pass ? "pass" : "fail"}">${pass ? "PASS" : "FAIL"}</div>
      `;
      checksBox.appendChild(div);
    }
  }

  function startKpiAnimation(summary) {
    anim.kpiStart = performance.now();

    const pc = Number(summary?.pred_ks_clean);
    const pd = Number(summary?.pred_ks_drifted);
    const hc = Number(summary?.health_clean);
    const hd = Number(summary?.health_drifted);

    anim.kpiFrom = { pc: 0, pd: 0, hc: 0, hd: 0 };
    anim.kpiTo = {
      pc: isNum(pc) ? pc : 0,
      pd: isNum(pd) ? pd : 0,
      hc: isNum(hc) ? hc : 0,
      hd: isNum(hd) ? hd : 0
    };
  }

  function setKpis(progress01) {
    const t = Math.max(0, Math.min(1, progress01));
    // easeOutCubic
    const e = 1 - Math.pow(1 - t, 3);

    const v = (a, b) => a + (b - a) * e;
    const pc = v(anim.kpiFrom.pc, anim.kpiTo.pc);
    const pd = v(anim.kpiFrom.pd, anim.kpiTo.pd);
    const hc = v(anim.kpiFrom.hc, anim.kpiTo.hc);
    const hd = v(anim.kpiFrom.hd, anim.kpiTo.hd);

    if (kPredClean) kPredClean.textContent = fmt(pc, 4);
    if (kPredDrift) kPredDrift.textContent = fmt(pd, 4);
    if (kHealthClean) kHealthClean.textContent = fmt2(hc);
    if (kHealthDrift) kHealthDrift.textContent = fmt2(hd);
  }

  async function runTest() {
    const test = String(testSelect?.value || "suite");
    const seed = Number(seedInput?.value || 7);

    setPill("run", "RUNNING…");
    jsonBox.textContent = "Running self-test…";

    try {
      const url = `/api/selftest?test=${encodeURIComponent(test)}&seed=${encodeURIComponent(seed)}&t=${Date.now()}`;
      const res = await fetch(url, { cache: "no-store" });
      const data = await res.json();

      latest = data;

      const ok = !!data.ok;
      setPill(ok ? "good" : "bad", ok ? "PASSED" : "FAILED");

      // meta
      if (metaLine) {
        metaLine.textContent =
          `test=${data.test} • seed=${data.seed} • cases=${data.cases ?? "—"} • elapsed=${data.elapsed_ms ?? "—"}ms • server=${data.server_elapsed_ms ?? "—"}ms`;
      }

      jsonBox.textContent = JSON.stringify(data, null, 2);

      renderChecks(data.checks);

      // prep animation values
      startKpiAnimation(data.summary || {});
      anim.mix = 0;
      mixSlider.value = "0";
      mixVal.textContent = "0%";
      anim.playing = true;
      playBtn.textContent = "PAUSE";

      // draw once immediately
      const case0 = (data.case_results && data.case_results[0]) || null;
      const hist = case0?.viz?.pred_hist || null;
      const feats = case0?.viz?.top_drifted_features || [];

      drawHistogram(hist);
      drawFeatures(feats, performance.now()); // pass current time

    } catch (e) {
      setPill("bad", "ERROR");
      jsonBox.textContent = `Fetch/Run error: ${String(e)}`;
    }
  }

  function tick(now) {
    const dt = Math.min(0.05, (now - anim.lastT) / 1000);
    anim.lastT = now;

    // KPI animation
    if (anim.kpiStart != null) {
      const t = (now - anim.kpiStart) / anim.kpiDur;
      if (t >= 1) {
        setKpis(1);
        anim.kpiStart = null;
      } else {
        setKpis(t);
      }
    }

    // mix animation (playable)
    if (anim.playing) {
      anim.mix += anim.speed * dt;
      if (anim.mix >= 1) anim.mix = 1;
      const pct = Math.round(anim.mix * 100);
      mixSlider.value = String(pct);
      mixVal.textContent = `${pct}%`;
    }

    // redraw visuals if we have data
    if (latest && latest.case_results && latest.case_results[0]) {
      const case0 = latest.case_results[0];
      const hist = case0?.viz?.pred_hist || null;
      const feats = case0?.viz?.top_drifted_features || [];

      drawHistogram(hist);

      // gauges (pred_ks as 0..1, health as 0..100)
      const pd = Number(case0?.metrics?.pred_ks_drifted);
      const hc = Number(case0?.metrics?.health_clean);
      const hd = Number(case0?.metrics?.health_drifted);

      const ks01 = Math.max(0, Math.min(1, (isNum(pd) ? pd : 0)));
      const health01 = Math.max(0, Math.min(1, (isNum(hd) ? hd : 0) / 100));

      drawGauge(ksGauge, ks01, "PRED_KS (DRIFT)", "rgba(209,31,31,0.92)");
      drawGauge(healthGauge, health01, "HEALTH (DRIFT)", "rgba(80,200,120,0.92)");

      drawFeatures(feats, now); // pass 'now' for pulsing
    }

    requestAnimationFrame(tick);
  }

  // Controls
  runBtn?.addEventListener("click", runTest);

  playBtn?.addEventListener("click", () => {
    anim.playing = !anim.playing;
    playBtn.textContent = anim.playing ? "PAUSE" : "PLAY";
  });

  resetBtn?.addEventListener("click", () => {
    anim.playing = false;
    anim.mix = 0;
    mixSlider.value = "0";
    mixVal.textContent = "0%";
    playBtn.textContent = "PLAY";
  });

  mixSlider?.addEventListener("input", () => {
    anim.playing = false;
    playBtn.textContent = "PLAY";
    const pct = Number(mixSlider.value);
    anim.mix = Math.max(0, Math.min(1, pct / 100));
    mixVal.textContent = `${pct}%`;
  });

  window.addEventListener("resize", () => {
    // redraw on resize by just letting tick repaint
  });

  // init
  setPill(null, "READY");
  requestAnimationFrame(tick);
})();