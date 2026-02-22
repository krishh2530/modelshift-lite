(() => {
  "use strict";

  // =========================================================
  // ModelShift-Lite Dashboard UI (app.js) — Fixed + Robust
  // =========================================================
  // Fixes included:
  // - Proper fetch timeout + abort for /api/results and /api/history
  // - Analysis page no longer gets stuck on transient fetch errors
  // - Theme button duplicate listener bug fixed
  // - Safer initial page setup (ensures charts render on first load)
  // - Optional API base support (window.MODELSHIFT_API_BASE)
  // - Clearer error text while preserving last known dashboard values

  // -----------------------------
  // Config
  // -----------------------------
  const FETCH_INTERVAL_MS = 4000;
  const FETCH_INTERVAL_BG_MS = 15000; // when tab hidden
  const FETCH_TIMEOUT_MS = 8000;

  // If you ever host frontend separately, set:
  // window.MODELSHIFT_API_BASE = "http://127.0.0.1:8000" (example)
  const API_BASE = String(window.MODELSHIFT_API_BASE || "").replace(/\/+$/, "");
  const apiUrl = (path) => `${API_BASE}${path}`;

  // -----------------------------
  // Helpers
  // -----------------------------
  const isNum = (v) => typeof v === "number" && Number.isFinite(v);
  const el = (id) => document.getElementById(id);

  const safeUpper = (s) => String(s ?? "—").toUpperCase();

  function fmt(n, digits = 2) {
    if (!isNum(n)) return "—";
    return n.toFixed(digits);
  }

  function fmtMaybeInt(n) {
    if (!isNum(n)) return "—";
    const abs = Math.abs(n);
    if (abs >= 100) return n.toFixed(0);
    if (abs >= 10) return n.toFixed(1);
    return n.toFixed(2);
  }

  function nowIsoLocal() {
    const d = new Date();
    const pad = (x) => String(x).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(
      d.getMinutes()
    )}:${pad(d.getSeconds())}`;
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function pickNum(obj, keys) {
    if (!obj || typeof obj !== "object") return null;
    for (const k of keys) {
      if (isNum(obj[k])) return obj[k];
    }
    return null;
  }

  function clampInt(v, lo, hi) {
    v = Number(v);
    if (!Number.isFinite(v)) v = lo;
    return Math.max(lo, Math.min(hi, Math.round(v)));
  }

  // -----------------------------
  // Deep find utilities (schema-robust)
  // -----------------------------
  function deepFind(obj, predicate, maxDepth = 7) {
    const seen = new Set();
    function rec(node, depth) {
      if (!node || depth > maxDepth) return null;
      if (typeof node === "object") {
        if (seen.has(node)) return null;
        seen.add(node);
      }
      if (predicate(node)) return node;

      if (Array.isArray(node)) {
        for (const it of node) {
          const r = rec(it, depth + 1);
          if (r) return r;
        }
        return null;
      }
      if (typeof node === "object") {
        for (const k of Object.keys(node)) {
          const r = rec(node[k], depth + 1);
          if (r) return r;
        }
      }
      return null;
    }
    return rec(obj, 0);
  }

  function deepFindNumberByKeyRegex(obj, keyRegex) {
    let found = null;
    const seen = new Set();

    function rec(node, depth) {
      if (!node || depth > 9 || found !== null) return;
      if (typeof node === "object") {
        if (seen.has(node)) return;
        seen.add(node);
      }
      if (Array.isArray(node)) {
        for (const it of node) rec(it, depth + 1);
        return;
      }
      if (typeof node === "object") {
        for (const [k, v] of Object.entries(node)) {
          if (keyRegex.test(k) && isNum(v)) {
            found = v;
            return;
          }
          rec(v, depth + 1);
          if (found !== null) return;
        }
      }
    }

    rec(obj, 0);
    return found;
  }

  function deepFindArrayByKeyRegex(obj, keyRegex) {
    let found = null;
    const seen = new Set();

    function rec(node, depth) {
      if (!node || depth > 9 || found) return;
      if (typeof node === "object") {
        if (seen.has(node)) return;
        seen.add(node);
      }
      if (Array.isArray(node)) {
        for (const it of node) rec(it, depth + 1);
        return;
      }
      if (typeof node === "object") {
        for (const [k, v] of Object.entries(node)) {
          if (
            keyRegex.test(k) &&
            Array.isArray(v) &&
            v.length >= 2 &&
            v.every((x) => typeof x === "number" && Number.isFinite(x))
          ) {
            found = v;
            return;
          }
          rec(v, depth + 1);
          if (found) return;
        }
      }
    }

    rec(obj, 0);
    return found;
  }

  // -----------------------------
  // DOM refs
  // -----------------------------
  const runIdText = el("runIdText");
  const statusBadge = el("statusBadge");
  const clockText = el("clockText");
  const livePill = el("livePill");

  const latestIdText = el("latestIdText");
  const prevIdText = el("prevIdText");
  const latestGeneratedText = el("latestGeneratedText");
  const prevGeneratedText = el("prevGeneratedText");

  const zoomSlider = el("zoomSlider");
  const zoomMinus = el("zoomMinus");
  const zoomPlus = el("zoomPlus");
  const zoomValue = el("zoomValue");

  const speedSlider = el("speedSlider");
  const speedMinus = el("speedMinus");
  const speedPlus = el("speedPlus");
  const speedValue = el("speedValue");
  const fpsText = el("fpsText");

  const playBtn = el("playBtn");
  const resetBtn = el("resetBtn");

  const syncAxesChk = el("syncAxesChk");
  const loopChk = el("loopChk");
  const themeBtn = el("themeBtn");

  const exportBtn = el("exportBtn");
  const clearHistoryBtn = el("clearHistoryBtn");

  const chartLatest = el("chartLatest");
  const chartPrevious = el("chartPrevious");

  const latestChartNote = el("latestChartNote");
  const prevChartNote = el("prevChartNote");

  const latestCleanHealth = el("latestCleanHealth");
  const latestDriftedHealth = el("latestDriftedHealth");
  const latestPredKs = el("latestPredKs");
  const latestDeltaEntropy = el("latestDeltaEntropy");
  const latestMostDrifted = el("latestMostDrifted");

  const prevCleanHealth = el("prevCleanHealth");
  const prevDriftedHealth = el("prevDriftedHealth");
  const prevPredKs = el("prevPredKs");
  const prevDeltaEntropy = el("prevDeltaEntropy");

  const ledgerBody = el("ledgerBody");
  const analysisJson = el("analysisJson");
  const alertBox = el("alertBox");
  const historyBody = el("historyBody");

  // Optional eval containers (injected if missing)
  let evalLatestBox = el("evalLatestBox");
  let evalPrevBox = el("evalPrevBox");

  const pages = {
    dash: el("page-dash"),
    analysis: el("page-analysis"),
    alerts: el("page-alerts"),
    config: el("page-config"),
    history: el("page-history"),
  };

  // -----------------------------
  // State
  // -----------------------------
  const state = {
    latest: {},
    previous: {},

    latestSeries: { clean: [], drifted: [] },
    prevSeries: { clean: [], drifted: [] },

    latestMeta: {},
    prevMeta: {},

    zoom: Number(zoomSlider?.value ?? 3), // 1..10
    speed: Number(speedSlider?.value ?? 4), // 1..12
    playing: false,
    playhead: 0,
    fps: 0,

    syncAxes: true,
    loop: true,

    lastFetchRunId: null,
    serverHistory: [],

    // render optimization
    dirtyCharts: true,
    dirtyEval: true,
    dirtyHistory: true,
    lastChartKey: "",
  };

  // -----------------------------
  // Navigation
  // -----------------------------
  function setPage(name) {
    const safeName = pages[name] ? name : "dash";
    document.body.setAttribute("data-page", safeName);

    Object.keys(pages).forEach((k) => pages[k]?.classList.toggle("active", k === safeName));
    document.querySelectorAll(".navbtn").forEach((b) => b.classList.toggle("active", b.dataset.page === safeName));

    // Force one render after page switch
    if (safeName === "dash") state.dirtyCharts = true;
  }

  // -----------------------------
  // Clock
  // -----------------------------
  function updateClock() {
    const d = new Date();
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    const ss = String(d.getSeconds()).padStart(2, "0");
    if (clockText) clockText.textContent = `${hh}:${mm}:${ss}`;
  }

  // -----------------------------
  // Extractors
  // -----------------------------
  function extractRunMeta(run) {
    const run_id =
      run?.run_id ??
      run?.id ??
      deepFind(run, (x) => x && typeof x === "object" && typeof x.run_id === "string")?.run_id ??
      "—";

    const status =
      run?.status ??
      run?.state ??
      deepFind(run, (x) => x && typeof x === "object" && typeof x.status === "string")?.status ??
      "—";

    const generated_at =
      run?.generated_at ??
      run?.generated ??
      run?.time ??
      deepFind(run, (x) => x && typeof x === "object" && typeof x.generated_at === "string")?.generated_at ??
      "—";

    return { run_id, status, generated_at };
  }

  function extractMetrics(run) {
    const summary = run?.summary && typeof run.summary === "object" ? run.summary : {};

    const clean_health =
      summary?.clean_health ??
      run?.clean_health ??
      run?.metrics?.clean_health ??
      deepFindNumberByKeyRegex(run, /^clean_health$/i) ??
      deepFindNumberByKeyRegex(run, /clean.*health/i);

    const drifted_health =
      summary?.drifted_health ??
      run?.drifted_health ??
      run?.metrics?.drifted_health ??
      deepFindNumberByKeyRegex(run, /^drifted_health$/i) ??
      deepFindNumberByKeyRegex(run, /drift.*health/i);

    const pred_ks =
      summary?.drifted_pred_ks ??
      run?.pred_ks ??
      run?.metrics?.pred_ks ??
      deepFindNumberByKeyRegex(run, /pred.*ks/i);

    const delta_entropy =
      summary?.drifted_entropy_change ??
      run?.delta_entropy ??
      run?.metrics?.delta_entropy ??
      deepFindNumberByKeyRegex(run, /(delta|d).*entropy/i);

    // Prefer new schema (summary feature + ks)
    let feat = null;
    const fName = summary?.drifted_last_window_feature;
    const fKs = summary?.drifted_last_window_ks;
    if (typeof fName === "string" && isNum(fKs)) {
      feat = { feature: fName, ks: fKs, window_size: run?.window_size };
    } else {
      feat =
        run?.most_drifted_feature ??
        run?.metrics?.most_drifted_feature ??
        deepFind(
          run,
          (x) =>
            x &&
            typeof x === "object" &&
            (typeof x.feature === "string" || typeof x.name === "string") &&
            isNum(x.ks)
        );
    }

    return { clean_health, drifted_health, pred_ks, delta_entropy, feat };
  }

  function extractSeries(run) {
    const clean =
      run?.series?.clean ??
      run?.series?.clean_health ??
      run?.series?.clean_health_series ??
      run?.health_series?.clean ??
      run?.clean_series ??
      run?.clean_health_series ??
      deepFindArrayByKeyRegex(run, /clean.*(series|health)/i);

    const drifted =
      run?.series?.drifted ??
      run?.series?.drift ??
      run?.series?.drifted_health ??
      run?.series?.drifted_health_series ??
      run?.health_series?.drifted ??
      run?.drifted_series ??
      run?.drifted_health_series ??
      deepFindArrayByKeyRegex(run, /(drift|drifted).*(series|health)/i);

    return {
      clean: Array.isArray(clean) ? clean : [],
      drifted: Array.isArray(drifted) ? drifted : [],
    };
  }

  function extractEvaluation(run) {
    const ev = run?.evaluation;
    if (!ev || typeof ev !== "object") return null;

    const clean = ev.clean && typeof ev.clean === "object" ? ev.clean : null;
    const drifted = ev.drifted && typeof ev.drifted === "object" ? ev.drifted : null;
    const baseline = ev.baseline && typeof ev.baseline === "object" ? ev.baseline : null;

    return { baseline, clean, drifted };
  }

  // -----------------------------
  // Status badge
  // -----------------------------
  function setStatusBadge(status) {
    if (!statusBadge) return;

    const s = safeUpper(status);
    statusBadge.textContent = s;
    statusBadge.style.borderColor = "rgba(255,255,255,0.12)";
    statusBadge.style.background = "rgba(0,0,0,0.25)";

    if (s.includes("CRITICAL")) {
      statusBadge.style.borderColor = "rgba(209,31,31,0.55)";
      statusBadge.style.background = "rgba(209,31,31,0.12)";
    } else if (s.includes("WARN")) {
      statusBadge.style.borderColor = "rgba(255,170,0,0.45)";
      statusBadge.style.background = "rgba(255,170,0,0.10)";
    }
  }

  // -----------------------------
  // Ledger
  // -----------------------------
  function fillLedger(latestRun, prevRun) {
    if (!ledgerBody) return;
    ledgerBody.innerHTML = "";

    const rows = [latestRun, prevRun].filter(Boolean);
    for (const r of rows) {
      const meta = extractRunMeta(r);
      const m = extractMetrics(r);

      const tr = document.createElement("tr");

      const td1 = document.createElement("td");
      td1.textContent = meta.generated_at || "—";

      const td2 = document.createElement("td");
      td2.textContent = meta.run_id || "—";

      const td3 = document.createElement("td");
      td3.textContent = meta.status || "—";
      if (safeUpper(meta.status).includes("CRITICAL") || safeUpper(meta.status).includes("WARN")) {
        td3.className = "bad";
      }

      const td4 = document.createElement("td");
      td4.textContent = fmt(m.drifted_health, 2);

      const td5 = document.createElement("td");
      td5.textContent = fmt(m.pred_ks, 4);

      tr.append(td1, td2, td3, td4, td5);
      ledgerBody.appendChild(tr);
    }
  }

  // -----------------------------
  // History
  // -----------------------------
  function renderHistory() {
    if (!historyBody) return;
    historyBody.innerHTML = "";

    const rows = Array.isArray(state.serverHistory) ? state.serverHistory : [];
    for (const r of rows) {
      const tr = document.createElement("tr");

      const tdSaved = document.createElement("td");
      tdSaved.textContent = r.saved_at || "—";

      const tdGen = document.createElement("td");
      tdGen.textContent = r.generated_at || "—";

      const tdRun = document.createElement("td");
      tdRun.textContent = r.run_id || "—";

      const tdStatus = document.createElement("td");
      tdStatus.textContent = r.status || "—";
      if (safeUpper(r.status).includes("CRITICAL") || safeUpper(r.status).includes("WARN")) {
        tdStatus.className = "bad";
      }

      const tdC = document.createElement("td");
      tdC.textContent = isNum(r.clean_health) ? r.clean_health.toFixed(2) : "—";

      const tdD = document.createElement("td");
      tdD.textContent = isNum(r.drifted_health) ? r.drifted_health.toFixed(2) : "—";

      const tdK = document.createElement("td");
      tdK.textContent = isNum(r.drifted_pred_ks) ? r.drifted_pred_ks.toFixed(4) : "—";

      const tdE = document.createElement("td");
      tdE.textContent = isNum(r.drifted_entropy_change) ? r.drifted_entropy_change.toFixed(4) : "—";

      tr.append(tdSaved, tdGen, tdRun, tdStatus, tdC, tdD, tdK, tdE);
      historyBody.appendChild(tr);
    }
  }

  // -----------------------------
  // Evaluation UI (Premium) + CSS injection
  // -----------------------------
  function ensureEvalCss() {
    if (document.getElementById("ms-eval-css")) return;
    const st = document.createElement("style");
    st.id = "ms-eval-css";
    st.textContent = `
      .evalwrap{
        margin-top:12px;
        border:1px solid rgba(255,255,255,0.10);
        background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(0,0,0,0.06));
        padding:12px;
      }
      .evalhead{
        display:flex;
        justify-content:space-between;
        align-items:flex-end;
        gap:10px;
        margin-bottom:10px;
      }
      .evaltitle{
        font-family: ui-monospace, Menlo, Consolas, monospace;
        font-weight:900;
        letter-spacing:1px;
        opacity:0.92;
      }
      .evalnote{
        font-family: ui-monospace, Menlo, Consolas, monospace;
        font-size:12px;
        opacity:0.65;
        text-align:right;
      }
      .evaltablewrap{ overflow:auto; border:1px solid rgba(255,255,255,0.08); }
      table.evaltable{
        width:100%;
        border-collapse:collapse;
        min-width:680px;
      }
      table.evaltable th, table.evaltable td{
        padding:10px 12px;
        border-bottom:1px solid rgba(255,255,255,0.08);
        font-family: ui-monospace, Menlo, Consolas, monospace;
        font-size:12.5px;
        text-align:left;
      }
      table.evaltable th{
        opacity:0.85;
        letter-spacing:0.8px;
      }
      .hint{
        font-family: ui-monospace, Menlo, Consolas, monospace;
        font-size:12px;
        opacity:0.70;
      }
      .bad{ color: rgba(209,31,31,0.95); font-weight:900; }
    `;
    document.head.appendChild(st);
  }

  function ensureEvalBoxes() {
    ensureEvalCss();

    // LATEST
    if (!evalLatestBox) {
      evalLatestBox = document.createElement("div");
      evalLatestBox.id = "evalLatestBox";
      if (latestMostDrifted && latestMostDrifted.parentNode) {
        latestMostDrifted.insertAdjacentElement("afterend", evalLatestBox);
      } else {
        pages.dash?.appendChild(evalLatestBox);
      }
    }

    // PREVIOUS
    if (!evalPrevBox) {
      evalPrevBox = document.createElement("div");
      evalPrevBox.id = "evalPrevBox";
      const prevBlock = prevDeltaEntropy?.closest?.(".block") || chartPrevious?.closest?.(".block") || pages.dash;
      prevBlock?.appendChild(evalPrevBox);
    }
  }

  function extractConfusion(evPart) {
    if (!evPart || typeof evPart !== "object") return null;
    const cm = evPart.confusion_matrix ?? evPart.cm ?? evPart.confusionMatrix ?? null;

    if (Array.isArray(cm) && cm.length === 2 && Array.isArray(cm[0]) && Array.isArray(cm[1])) {
      const tn = cm[0][0],
        fp = cm[0][1],
        fn = cm[1][0],
        tp = cm[1][1];
      if ([tn, fp, fn, tp].every(isNum)) return { tn, fp, fn, tp };
    }

    if (cm && typeof cm === "object") {
      const tn = cm.tn,
        fp = cm.fp,
        fn = cm.fn,
        tp = cm.tp;
      if ([tn, fp, fn, tp].every(isNum)) return { tn, fp, fn, tp };
    }
    return null;
  }

  function evalSectionHtml(title, ev) {
    if (!ev || typeof ev !== "object") {
      return `
        <div class="evalwrap">
          <div class="evalhead">
            <div class="evaltitle">${escapeHtml(title)}</div>
            <div class="evalnote">No evaluation metrics (labels unavailable / invalid)</div>
          </div>
        </div>
      `;
    }

    const clean = ev.clean || null;
    const drifted = ev.drifted || null;

    const rows = [
      ["ACCURACY", ["accuracy", "acc"], 4],
      ["PRECISION", ["precision", "prec"], 4],
      ["RECALL", ["recall", "rec"], 4],
      ["F1 SCORE", ["f1_score", "f1", "f1score"], 4],
      ["ROC AUC", ["roc_auc", "auc", "rocAuc"], 4],
      ["LOG LOSS", ["log_loss", "logloss"], 6],
      ["MSE (BRIER)", ["mse", "brier", "brier_score_loss"], 6],
      ["RMSE", ["rmse"], 6],
      ["R²", ["r2", "r_squared"], 6],
    ];

    const cleanCM = extractConfusion(clean);
    const driftedCM = extractConfusion(drifted);

    const trs = rows
      .map(([label, keys, digs]) => {
        const c = pickNum(clean, keys);
        const d = pickNum(drifted, keys);

        let driftBad = false;
        const higherBetter = ["ACCURACY", "PRECISION", "RECALL", "F1 SCORE", "ROC AUC", "R²"].includes(label);
        if (isNum(c) && isNum(d)) driftBad = higherBetter ? d < c : d > c;

        return `
          <tr>
            <td>${escapeHtml(label)}</td>
            <td>${isNum(c) ? c.toFixed(digs) : "—"}</td>
            <td class="${driftBad ? "bad" : ""}">${isNum(d) ? d.toFixed(digs) : "—"}</td>
          </tr>
        `;
      })
      .join("");

    const cmLine = (() => {
      if (!cleanCM && !driftedCM) return "";
      const c = cleanCM
        ? `CLEAN[tn=${cleanCM.tn}, fp=${cleanCM.fp}, fn=${cleanCM.fn}, tp=${cleanCM.tp}]`
        : "CLEAN[—]";
      const d = driftedCM
        ? `DRIFTED[tn=${driftedCM.tn}, fp=${driftedCM.fp}, fn=${driftedCM.fn}, tp=${driftedCM.tp}]`
        : "DRIFTED[—]";
      return `<div class="hint" style="margin-top:10px;">CONFUSION MATRIX: ${escapeHtml(c)} • ${escapeHtml(d)}</div>`;
    })();

    return `
      <div class="evalwrap">
        <div class="evalhead">
          <div class="evaltitle">${escapeHtml(title)}</div>
          <div class="evalnote">Clean vs Drifted (requires labels)</div>
        </div>

        <div class="evaltablewrap">
          <table class="evaltable">
            <thead>
              <tr>
                <th>METRIC</th>
                <th>CLEAN</th>
                <th>DRIFTED</th>
              </tr>
            </thead>
            <tbody>${trs}</tbody>
          </table>
        </div>

        <div class="hint" style="margin-top:10px;">
          Note: MSE/RMSE are computed on probabilities vs labels (Brier-style).
        </div>
        ${cmLine}
      </div>
    `;
  }

  function renderEvaluation(latestRun, prevRun) {
    ensureEvalBoxes();
    const evL = extractEvaluation(latestRun);
    const evP = extractEvaluation(prevRun);

    if (evalLatestBox) evalLatestBox.innerHTML = evalSectionHtml("EVALUATION METRICS — LATEST RUN", evL);
    if (evalPrevBox) evalPrevBox.innerHTML = evalSectionHtml("EVALUATION METRICS — PREVIOUS RUN", evP);
  }

  // -----------------------------
  // Charts (Canvas)
  // -----------------------------
  const canvasCache = new WeakMap();

  function setupCanvas(canvas) {
    const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    const rect = canvas.getBoundingClientRect();
    const cssW = rect.width;
    const cssH = rect.height;

    const pxW = Math.max(1, Math.floor(cssW * dpr));
    const pxH = Math.max(1, Math.floor(cssH * dpr));

    const cached = canvasCache.get(canvas);
    const same =
      cached &&
      cached.dpr === dpr &&
      cached.pxW === pxW &&
      cached.pxH === pxH &&
      cached.cssW === cssW &&
      cached.cssH === cssH;

    if (!same) {
      canvas.width = pxW;
      canvas.height = pxH;
      canvasCache.set(canvas, { dpr, pxW, pxH, cssW, cssH });
    }

    const ctx = canvas.getContext("2d");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);

    return { ctx, w: cssW, h: cssH };
  }

  function pointsPerSecond() {
    return 3 + state.speed * 5; // 1..12 => 8..63 pts/sec
  }

  function visibleCount(total) {
    const z = Math.max(1, Math.min(10, state.zoom));
    const frac = 1 / z;
    const count = Math.max(12, Math.floor(total * frac));
    return Math.min(total, count);
  }

  function drawChart(canvas, seriesClean, seriesDrifted, opts) {
    const { ctx, w, h } = setupCanvas(canvas);

    const padL = 48,
      padR = 18,
      padT = 14,
      padB = 34;

    const total = Math.max(seriesClean.length, seriesDrifted.length);
    ctx.clearRect(0, 0, w, h);

    if (total < 2) {
      ctx.fillStyle = "rgba(255,255,255,0.75)";
      ctx.font = "12px ui-monospace, Menlo, Consolas, monospace";
      ctx.fillText("No series data found in JSON.", 14, 18);
      return;
    }

    const vis = visibleCount(total);
    const center = Math.max(0, Math.min(total - 1, opts.centerIndex));
    let start = Math.floor(center - vis / 2);
    start = Math.max(0, Math.min(start, total - vis));
    const end = start + vis;

    const getVal = (arr, i) => (i < arr.length ? arr[i] : null);

    let ymin = Infinity,
      ymax = -Infinity;
    for (let i = start; i < end; i++) {
      const a = getVal(seriesClean, i);
      const b = getVal(seriesDrifted, i);
      if (isNum(a)) {
        ymin = Math.min(ymin, a);
        ymax = Math.max(ymax, a);
      }
      if (isNum(b)) {
        ymin = Math.min(ymin, b);
        ymax = Math.max(ymax, b);
      }
    }

    if (!Number.isFinite(ymin) || !Number.isFinite(ymax)) {
      ymin = 0;
      ymax = 1;
    }

    let yr = ymax - ymin;
    if (yr < 1e-9) yr = 1;
    const pad = yr * 0.12;
    ymin -= pad;
    ymax += pad;

    const gx0 = padL,
      gy0 = padT,
      gx1 = w - padR,
      gy1 = h - padB;

    // major grid
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = 1;
    const xTicks = 6,
      yTicks = 5;
    for (let t = 0; t <= xTicks; t++) {
      const x = gx0 + (t / xTicks) * (gx1 - gx0);
      ctx.beginPath();
      ctx.moveTo(x, gy0);
      ctx.lineTo(x, gy1);
      ctx.stroke();
    }
    for (let t = 0; t <= yTicks; t++) {
      const y = gy0 + (t / yTicks) * (gy1 - gy0);
      ctx.beginPath();
      ctx.moveTo(gx0, y);
      ctx.lineTo(gx1, y);
      ctx.stroke();
    }

    // minor dotted grid
    ctx.strokeStyle = "rgba(255,255,255,0.025)";
    ctx.setLineDash([2, 6]);
    const minor = 18;
    for (let x = gx0; x <= gx1; x += minor) {
      ctx.beginPath();
      ctx.moveTo(x, gy0);
      ctx.lineTo(x, gy1);
      ctx.stroke();
    }
    for (let y = gy0; y <= gy1; y += minor) {
      ctx.beginPath();
      ctx.moveTo(gx0, y);
      ctx.lineTo(gx1, y);
      ctx.stroke();
    }
    ctx.setLineDash([]);

    // axis labels
    ctx.fillStyle = "rgba(255,255,255,0.72)";
    ctx.font = "12px ui-monospace, Menlo, Consolas, monospace";
    for (let t = 0; t <= yTicks; t++) {
      const v = ymax - (t / yTicks) * (ymax - ymin);
      const y = gy0 + (t / yTicks) * (gy1 - gy0);
      ctx.fillText(fmtMaybeInt(v), 8, y + 4);
    }
    for (let t = 0; t <= xTicks; t++) {
      const idx = Math.round(start + (t / xTicks) * (vis - 1));
      const x = gx0 + (t / xTicks) * (gx1 - gx0);
      ctx.fillText(String(idx), x - 6, gy1 + 22);
    }

    ctx.save();
    ctx.translate(16, (gy0 + gy1) / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillStyle = "rgba(255,255,255,0.55)";
    ctx.fillText("Health", 0, 0);
    ctx.restore();

    ctx.fillStyle = "rgba(255,255,255,0.55)";
    ctx.fillText("window", (gx0 + gx1) / 2 - 20, h - 8);

    const denom = Math.max(1, vis - 1);
    const xScale = (gx1 - gx0) / denom;

    const xMap = (i) => gx0 + (i - start) * xScale;
    const yMap = (v) => gy0 + (1 - (v - ymin) / (ymax - ymin)) * (gy1 - gy0);

    function drawLine(arr, color) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      let started = false;
      for (let i = start; i < end; i++) {
        const v = getVal(arr, i);
        if (!isNum(v)) {
          started = false;
          continue;
        }
        const x = xMap(i);
        const y = yMap(v);
        if (!started) {
          ctx.moveTo(x, y);
          started = true;
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    }

    drawLine(seriesClean, "rgba(255,255,255,0.88)");
    drawLine(seriesDrifted, "rgba(209,31,31,0.88)");

    // legend
    ctx.fillStyle = "rgba(255,255,255,0.82)";
    ctx.font = "13px ui-monospace, Menlo, Consolas, monospace";
    ctx.fillText("CLEAN", gx1 - 120, gy0 + 20);
    ctx.fillStyle = "rgba(209,31,31,0.90)";
    ctx.fillText("DRIFTED", gx1 - 120, gy0 + 40);
  }

  // -----------------------------
  // Render from API payload
  // -----------------------------
  function updateFromData(payload) {
    state.latest = payload?.latest || {};
    state.previous = payload?.previous || {};

    state.latestMeta = extractRunMeta(state.latest);
    state.prevMeta = extractRunMeta(state.previous);

    if (runIdText) runIdText.textContent = state.latestMeta.run_id || "—";
    if (latestIdText) latestIdText.textContent = state.latestMeta.run_id || "—";
    if (prevIdText) prevIdText.textContent = state.prevMeta.run_id || "—";
    if (latestGeneratedText) latestGeneratedText.textContent = state.latestMeta.generated_at || "—";
    if (prevGeneratedText) prevGeneratedText.textContent = state.prevMeta.generated_at || "—";
    setStatusBadge(state.latestMeta.status || "—");

    const lm = extractMetrics(state.latest);
    const pm = extractMetrics(state.previous);

    if (latestCleanHealth) latestCleanHealth.textContent = fmt(lm.clean_health, 2);
    if (latestDriftedHealth) latestDriftedHealth.textContent = fmt(lm.drifted_health, 2);
    if (latestPredKs) latestPredKs.textContent = fmt(lm.pred_ks, 4);
    if (latestDeltaEntropy) latestDeltaEntropy.textContent = fmt(lm.delta_entropy, 4);

    if (latestMostDrifted) {
      if (lm.feat) {
        const feature = lm.feat.feature || lm.feat.name || "—";
        const ks = isNum(lm.feat.ks) ? lm.feat.ks.toFixed(4) : "—";
        const ws = lm.feat.window_size ?? lm.feat.window ?? lm.feat.n ?? state.latest?.window_size ?? "—";
        latestMostDrifted.textContent = `MOST DRIFTED FEATURE (LAST WINDOW): ${String(feature).toUpperCase()} // KS: ${ks} // WINDOW_SIZE: ${ws}`;
      } else {
        latestMostDrifted.textContent = "MOST DRIFTED FEATURE (LAST WINDOW): —";
      }
    }

    if (prevCleanHealth) prevCleanHealth.textContent = fmt(pm.clean_health, 2);
    if (prevDriftedHealth) prevDriftedHealth.textContent = fmt(pm.drifted_health, 2);
    if (prevPredKs) prevPredKs.textContent = fmt(pm.pred_ks, 4);
    if (prevDeltaEntropy) prevDeltaEntropy.textContent = fmt(pm.delta_entropy, 4);

    state.latestSeries = extractSeries(state.latest);
    state.prevSeries = extractSeries(state.previous);

    const latestStatus = safeUpper(state.latestMeta.status);
    if (latestChartNote) {
      if ((latestStatus.includes("CRITICAL") || latestStatus.includes("WARN")) && isNum(lm.pred_ks)) {
        latestChartNote.textContent = `! DRIFT DETECTED // PRED_KS=${lm.pred_ks.toFixed(4)}`;
      } else if (isNum(lm.pred_ks)) {
        latestChartNote.textContent = `OK // PRED_KS=${lm.pred_ks.toFixed(4)}`;
      } else {
        latestChartNote.textContent = "";
      }
    }

    if (prevChartNote) {
      prevChartNote.textContent = `Prev Run: ${state.prevMeta.run_id || "—"} • Generated: ${state.prevMeta.generated_at || "—"}`;
    }

    // Analysis JSON (proof)
    if (analysisJson) {
      analysisJson.textContent = JSON.stringify({ latest: state.latest, previous: state.previous }, null, 2);
    }

    // Alerts
    if (alertBox) {
      if (latestStatus.includes("CRITICAL")) {
        const feature = lm.feat ? lm.feat.feature || lm.feat.name || "—" : "—";
        const ksFeat = lm.feat && isNum(lm.feat.ks) ? lm.feat.ks.toFixed(4) : "—";
        alertBox.textContent = `CRITICAL: PREDICTION DRIFT HIGH (PRED_KS=${fmt(lm.pred_ks, 4)}). FEATURE=${String(
          feature
        ).toLowerCase()} (KS=${ksFeat}). ΔENTROPY=${fmt(lm.delta_entropy, 4)}. INVESTIGATE IMMEDIATELY.`;
      } else if (latestStatus.includes("WARN")) {
        alertBox.textContent = `WARNING: DRIFT DETECTED (PRED_KS=${fmt(lm.pred_ks, 4)}). Monitor closely.`;
      } else {
        alertBox.textContent = "OK: No critical drift detected.";
      }
    }

    fillLedger(state.latest, state.previous);
    state.dirtyEval = true;
    state.dirtyCharts = true;

    // If run changed, refresh history
    if (state.latestMeta.run_id && state.latestMeta.run_id !== state.lastFetchRunId) {
      state.lastFetchRunId = state.latestMeta.run_id;
      state.playhead = 0;
      fetchHistory();
    }
  }

  // -----------------------------
  // Fetch (abort + timeout)
  // -----------------------------
  let resultsAbort = null;
  let historyAbort = null;

  function abortIfActive(ctrl) {
    try {
      if (ctrl && !ctrl.signal.aborted) ctrl.abort();
    } catch {
      // ignore
    }
  }

  async function fetchJson(url, kind = "results") {
    // Abort previous same-kind request
    if (kind === "results") abortIfActive(resultsAbort);
    if (kind === "history") abortIfActive(historyAbort);

    const controller = new AbortController();
    if (kind === "results") resultsAbort = controller;
    if (kind === "history") historyAbort = controller;

    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

    try {
      const res = await fetch(url, {
        cache: "no-store",
        signal: controller.signal,
        headers: { Accept: "application/json" },
      });

      if (!res.ok) {
        const txt = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status}${txt ? ` - ${txt.slice(0, 200)}` : ""}`);
      }

      return await res.json();
    } finally {
      clearTimeout(timeoutId);
    }
  }

  async function fetchResults() {
    try {
      const data = await fetchJson(apiUrl(`/api/results?t=${Date.now()}`), "results");
      updateFromData(data);

      // If Analysis tab previously showed a fetch error, restore JSON
      if (analysisJson && /failed to fetch|http\s\d+/i.test(analysisJson.textContent || "")) {
        analysisJson.textContent = JSON.stringify({ latest: state.latest, previous: state.previous }, null, 2);
      }
    } catch (e) {
      // Ignore aborts (normal during polling overlap)
      if (e?.name === "AbortError") return;

      // Don't destroy dashboard state if one poll fails
      if (alertBox) {
        alertBox.textContent = "WARNING: /api/results fetch failed. Showing last known values.";
      }

      // Only show error in Analysis if nothing is loaded yet
      const hasData = state.latest && Object.keys(state.latest).length > 0;
      if (analysisJson && !hasData) {
        analysisJson.textContent =
          `Fetch error: ${String(e)}\n\n` +
          `If you opened the HTML directly, run it from the backend server so /api/results is available.\n` +
          `You can also set window.MODELSHIFT_API_BASE if frontend and backend are on different ports.`;
      }
    }
  }

  async function fetchHistory() {
    try {
      const data = await fetchJson(apiUrl(`/api/history?n=50&t=${Date.now()}`), "history");
      state.serverHistory = Array.isArray(data?.runs) ? data.runs : [];
      state.dirtyHistory = true;
    } catch (e) {
      if (e?.name === "AbortError") return;
      state.serverHistory = state.serverHistory || [];
      state.dirtyHistory = true;
    }
  }

  // -----------------------------
  // Animation loop (dirty rendering)
  // -----------------------------
  let lastT = performance.now();
  let fpsAccT = 0;
  let fpsFrames = 0;

  function computeChartKey() {
    const l1 = state.latestSeries.clean.length;
    const l2 = state.latestSeries.drifted.length;
    const p1 = state.prevSeries.clean.length;
    const p2 = state.prevSeries.drifted.length;
    return [
      state.latestMeta.run_id,
      state.prevMeta.run_id,
      l1,
      l2,
      p1,
      p2,
      state.zoom,
      state.speed,
      state.syncAxes ? 1 : 0,
      state.loop ? 1 : 0,
      Math.floor(state.playhead * 10) / 10,
      document.body.getAttribute("data-page"),
    ].join("|");
  }

  function tick(now) {
    const dt = Math.min(0.05, (now - lastT) / 1000);
    lastT = now;

    fpsAccT += dt;
    fpsFrames += 1;
    if (fpsAccT >= 1.0) {
      state.fps = Math.round(fpsFrames / fpsAccT);
      if (fpsText) fpsText.textContent = `${state.fps} FPS`;
      fpsAccT = 0;
      fpsFrames = 0;
    }

    const onDash = document.body.getAttribute("data-page") === "dash";

    if (onDash && state.playing) {
      const total = Math.max(state.latestSeries.clean.length, state.latestSeries.drifted.length);
      if (total >= 2) {
        state.playhead += pointsPerSecond() * dt;
        if (state.playhead >= total - 1) {
          if (state.loop) state.playhead = 0;
          else state.playing = false;
        }
        state.dirtyCharts = true;
      }
    }

    if (state.dirtyHistory) {
      renderHistory();
      state.dirtyHistory = false;
    }

    if (state.dirtyEval) {
      renderEvaluation(state.latest, state.previous);
      state.dirtyEval = false;
    }

    if (onDash && chartLatest && chartPrevious) {
      const key = computeChartKey();
      if (state.dirtyCharts || key !== state.lastChartKey) {
        state.lastChartKey = key;
        state.dirtyCharts = false;

        const latestTotal = Math.max(state.latestSeries.clean.length, state.latestSeries.drifted.length);
        const prevTotal = Math.max(state.prevSeries.clean.length, state.prevSeries.drifted.length);

        const centerLatest = latestTotal ? Math.min(latestTotal - 1, Math.max(0, state.playhead)) : 0;

        let centerPrev = centerLatest;
        if (state.syncAxes && latestTotal >= 2 && prevTotal >= 2) {
          const ratio = centerLatest / (latestTotal - 1);
          centerPrev = ratio * (prevTotal - 1);
        } else {
          centerPrev = Math.min(Math.max(0, prevTotal - 1), Math.max(0, state.playhead));
        }

        drawChart(chartLatest, state.latestSeries.clean, state.latestSeries.drifted, { centerIndex: centerLatest });
        drawChart(chartPrevious, state.prevSeries.clean, state.prevSeries.drifted, { centerIndex: centerPrev });
      }
    }

    if (playBtn) playBtn.textContent = state.playing ? "PAUSE" : "PLAY";
    requestAnimationFrame(tick);
  }

  // -----------------------------
  // Export Report (server preferred, client fallback)
  // -----------------------------
  function downloadBlob(filename, blob) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1500);
  }

  function buildReportHtmlClient() {
    ensureEvalCss();

    const latestMeta = state.latestMeta;
    const prevMeta = state.prevMeta;
    const lm = extractMetrics(state.latest);
    const pm = extractMetrics(state.previous);

    // Try to ensure charts are drawn before export
    if (chartLatest && chartPrevious) {
      try {
        const latestTotal = Math.max(state.latestSeries.clean.length, state.latestSeries.drifted.length);
        const prevTotal = Math.max(state.prevSeries.clean.length, state.prevSeries.drifted.length);
        drawChart(chartLatest, state.latestSeries.clean, state.latestSeries.drifted, {
          centerIndex: latestTotal ? Math.min(latestTotal - 1, Math.max(0, state.playhead)) : 0,
        });
        drawChart(chartPrevious, state.prevSeries.clean, state.prevSeries.drifted, {
          centerIndex: prevTotal ? Math.min(prevTotal - 1, Math.max(0, state.playhead)) : 0,
        });
      } catch {
        // no-op
      }
    }

    const latestImg = chartLatest?.toDataURL("image/png", 1.0) || "";
    const prevImg = chartPrevious?.toDataURL("image/png", 1.0) || "";

    const historyRows = (Array.isArray(state.serverHistory) ? state.serverHistory : [])
      .slice(0, 25)
      .map(
        (r) => `
      <tr>
        <td>${escapeHtml(r.saved_at || "—")}</td>
        <td>${escapeHtml(r.generated_at || "—")}</td>
        <td>${escapeHtml(r.run_id || "—")}</td>
        <td>${escapeHtml(r.status || "—")}</td>
        <td>${isNum(r.clean_health) ? r.clean_health.toFixed(2) : "—"}</td>
        <td>${isNum(r.drifted_health) ? r.drifted_health.toFixed(2) : "—"}</td>
        <td>${isNum(r.drifted_pred_ks) ? r.drifted_pred_ks.toFixed(4) : "—"}</td>
        <td>${isNum(r.drifted_entropy_change) ? r.drifted_entropy_change.toFixed(4) : "—"}</td>
      </tr>
    `
      )
      .join("");

    const mostDriftedLine = escapeHtml(latestMostDrifted?.textContent || "");
    const jsonProof = escapeHtml(JSON.stringify({ latest: state.latest, previous: state.previous }, null, 2));

    const evL = extractEvaluation(state.latest);
    const evP = extractEvaluation(state.previous);

    const evalL = evalSectionHtml("EVALUATION METRICS — LATEST RUN", evL);
    const evalP = evalSectionHtml("EVALUATION METRICS — PREVIOUS RUN", evP);

    return `<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>ModelShift-Lite Report - ${escapeHtml(latestMeta.run_id)}</title>
  <style>
    :root{ --bg:#0b0c0d; --line:rgba(255,255,255,0.10); --text:#e9eef2; --muted:#9aa4ad; --red:#d11f1f; }
    *{box-sizing:border-box}
    body{ margin:0; background:var(--bg); color:var(--text); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; padding:26px; }
    .header{ display:flex; justify-content:space-between; align-items:center; border:1px solid var(--line); background:linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01)); padding:16px 18px; }
    .brand{ font-family: ui-monospace, Menlo, Consolas, monospace; font-weight:900; letter-spacing:2px; display:flex; gap:10px; align-items:center; }
    .tag{ border:1px solid var(--line); padding:6px 10px; font-family: ui-monospace, Menlo, Consolas, monospace; font-weight:900; }
    .grid{ display:grid; grid-template-columns:1fr; gap:14px; margin-top:14px; max-width:1200px; }
    .card{ border:1px solid var(--line); background:rgba(255,255,255,0.02); padding:14px; }
    .title{ font-family: ui-monospace, Menlo, Consolas, monospace; font-weight:900; letter-spacing:1px; opacity:0.92; margin-bottom:10px; }
    .meta{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size:12.5px; line-height:1.4; color:var(--muted); }
    .kpis{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin-top:12px; }
    .kpi{ border:1px solid var(--line); padding:12px; background:rgba(0,0,0,0.18); }
    .kpi .k{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size:12px; letter-spacing:1px; opacity:0.85; }
    .kpi .v{ font-family: ui-monospace, Menlo, Consolas, monospace; font-weight:900; font-size:44px; margin-top:6px; }
    .warn{ box-shadow: inset 0 0 0 1px rgba(209,31,31,0.35); }
    img{ width:100%; border:1px solid var(--line); background:#0a0b0c; }
    table{ width:100%; border-collapse:collapse; min-width:900px; }
    th,td{ border-bottom:1px solid rgba(255,255,255,0.08); padding:10px 12px; font-family: ui-monospace, Menlo, Consolas, monospace; font-size:12.5px; text-align:left; }
    th{ opacity:0.85; }
    .bad{ color:var(--red); font-weight:900; }
    pre{ margin:0; white-space:pre; overflow:auto; max-height:520px; border:1px solid var(--line); padding:12px; background:rgba(0,0,0,0.22); font-family: ui-monospace, Menlo, Consolas, monospace; font-size:12px; line-height:1.35; }
    .foot{ color:var(--muted); font-family: ui-monospace, Menlo, Consolas, monospace; font-size:12px; margin-top:12px; }
    @media (max-width: 1000px){ .kpis{grid-template-columns:repeat(2,minmax(0,1fr));} }

    .evalwrap{
      margin-top:12px;
      border:1px solid rgba(255,255,255,0.10);
      background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(0,0,0,0.06));
      padding:12px;
    }
    .evalhead{ display:flex; justify-content:space-between; align-items:flex-end; gap:10px; margin-bottom:10px; }
    .evaltitle{ font-family: ui-monospace, Menlo, Consolas, monospace; font-weight:900; letter-spacing:1px; opacity:0.92; }
    .evalnote{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size:12px; opacity:0.65; text-align:right; }
    .evaltablewrap{ overflow:auto; border:1px solid rgba(255,255,255,0.08); }
    table.evaltable{ width:100%; border-collapse:collapse; min-width:680px; }
    table.evaltable th, table.evaltable td{ padding:10px 12px; border-bottom:1px solid rgba(255,255,255,0.08); font-family: ui-monospace, Menlo, Consolas, monospace; font-size:12.5px; text-align:left; }
    table.evaltable th{ opacity:0.85; letter-spacing:0.8px; }
    .hint{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size:12px; opacity:0.70; }
  </style>
</head>
<body>
  <div class="header">
    <div class="brand">▸ MODELSHIFT-LITE <span style="opacity:.65;">REPORT</span></div>
    <div class="tag">RUN_ID: ${escapeHtml(latestMeta.run_id)} • ${escapeHtml(nowIsoLocal())}</div>
  </div>

  <div class="grid">
    <div class="card">
      <div class="title">RUN META</div>
      <div class="meta">
        <div><b style="color:var(--text);">STATUS:</b> <span class="${safeUpper(latestMeta.status).includes("CRITICAL") ? "bad" : ""}">${escapeHtml(latestMeta.status)}</span></div>
        <div>Latest Generated: ${escapeHtml(latestMeta.generated_at)} • Previous Generated: ${escapeHtml(prevMeta.generated_at)}</div>
        <div>Latest Run: ${escapeHtml(latestMeta.run_id)} • Previous Run: ${escapeHtml(prevMeta.run_id)}</div>
      </div>
    </div>

    <div class="card">
      <div class="title">LATEST RUN • DASHBOARD SNAPSHOT</div>
      ${latestImg ? `<img src="${latestImg}" alt="Latest chart"/>` : `<div class="meta">Chart image not available</div>`}
      <div class="kpis">
        <div class="kpi"><div class="k">CLEAN HEALTH</div><div class="v">${fmt(lm.clean_health,2)}</div></div>
        <div class="kpi warn"><div class="k">DRIFTED HEALTH</div><div class="v">${fmt(lm.drifted_health,2)}</div></div>
        <div class="kpi"><div class="k">PRED_KS (DRIFT)</div><div class="v">${fmt(lm.pred_ks,4)}</div></div>
        <div class="kpi"><div class="k">Δ ENTROPY</div><div class="v">${fmt(lm.delta_entropy,4)}</div></div>
      </div>
      <div class="meta" style="margin-top:10px;"><b style="color:var(--text);">Most Drifted:</b> ${mostDriftedLine}</div>
      <div style="margin-top:12px;">${evalL}</div>
    </div>

    <div class="card">
      <div class="title">PREVIOUS RUN • SNAPSHOT</div>
      ${prevImg ? `<img src="${prevImg}" alt="Previous chart"/>` : `<div class="meta">Chart image not available</div>`}
      <div class="kpis">
        <div class="kpi"><div class="k">CLEAN HEALTH</div><div class="v">${fmt(pm.clean_health,2)}</div></div>
        <div class="kpi"><div class="k">DRIFTED HEALTH</div><div class="v">${fmt(pm.drifted_health,2)}</div></div>
        <div class="kpi"><div class="k">PRED_KS</div><div class="v">${fmt(pm.pred_ks,4)}</div></div>
        <div class="kpi"><div class="k">Δ ENTROPY</div><div class="v">${fmt(pm.delta_entropy,4)}</div></div>
      </div>
      <div style="margin-top:12px;">${evalP}</div>
    </div>

    <div class="card">
      <div class="title">HISTORY (SAVED RUNS)</div>
      <div style="overflow:auto;">
        <table>
          <thead>
            <tr>
              <th>SAVED_AT</th><th>GENERATED_AT</th><th>RUN_ID</th><th>STATUS</th>
              <th>CLEAN</th><th>DRIFTED</th><th>PRED_KS</th><th>ΔENTROPY</th>
            </tr>
          </thead>
          <tbody>${historyRows || ""}</tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="title">INPUTS (PROOF JSON)</div>
      <pre>${jsonProof}</pre>
      <div class="foot">Generated by ModelShift-Lite UI export.</div>
    </div>
  </div>
</body>
</html>`;
  }

  async function exportReport() {
    const runId = state.latestMeta?.run_id || "UNKNOWN_RUN";

    try {
      const res = await fetch(apiUrl(`/api/report/latest?download=1&t=${Date.now()}`), { cache: "no-store" });
      if (res.ok) {
        const blob = await res.blob();
        downloadBlob(`ModelShift-Lite_Report_${runId}.html`, blob);
        return;
      }
    } catch {
      // fall back to client export
    }

    const html = buildReportHtmlClient();
    downloadBlob(`ModelShift-Lite_Report_${runId}.html`, new Blob([html], { type: "text/html" }));
  }

  // -----------------------------
  // Controls
  // -----------------------------
  function setZoom(v) {
    state.zoom = clampInt(v, 1, 10);
    if (zoomSlider) zoomSlider.value = String(state.zoom);
    if (zoomValue) zoomValue.textContent = String(state.zoom);
    state.dirtyCharts = true;
  }

  function setSpeed(v) {
    state.speed = clampInt(v, 1, 12);
    if (speedSlider) speedSlider.value = String(state.speed);
    if (speedValue) speedValue.textContent = String(state.speed);
  }

  function applyTheme() {
    const theme = localStorage.getItem("ms_theme") || "dark";
    document.documentElement.dataset.theme = theme;
  }

  // -----------------------------
  // Background-aware fetch interval
  // -----------------------------
  let fetchTimer = null;

  function startFetchLoop() {
    stopFetchLoop();
    const ms = document.visibilityState === "hidden" ? FETCH_INTERVAL_BG_MS : FETCH_INTERVAL_MS;
    fetchTimer = setInterval(fetchResults, ms);
  }

  function stopFetchLoop() {
    if (fetchTimer) clearInterval(fetchTimer);
    fetchTimer = null;
  }

  // -----------------------------
  // Init
  // -----------------------------
  function init() {
    // nav clicks
    document.querySelectorAll(".navbtn").forEach((b) => {
      b.addEventListener("click", () => setPage(b.dataset.page));
    });

    // controls
    zoomSlider?.addEventListener("input", () => setZoom(zoomSlider.value));
    zoomMinus?.addEventListener("click", () => setZoom(state.zoom - 1));
    zoomPlus?.addEventListener("click", () => setZoom(state.zoom + 1));

    speedSlider?.addEventListener("input", () => setSpeed(speedSlider.value));
    speedMinus?.addEventListener("click", () => setSpeed(state.speed - 1));
    speedPlus?.addEventListener("click", () => setSpeed(state.speed + 1));

    playBtn?.addEventListener("click", () => {
      state.playing = !state.playing;
      state.dirtyCharts = true;
    });

    resetBtn?.addEventListener("click", () => {
      state.playhead = 0;
      state.playing = false;
      state.dirtyCharts = true;
    });

    syncAxesChk?.addEventListener("change", () => {
      state.syncAxes = !!syncAxesChk.checked;
      state.dirtyCharts = true;
    });

    loopChk?.addEventListener("change", () => {
      state.loop = !!loopChk.checked;
    });

    // theme toggle (FIXED: single listener only)
    themeBtn?.addEventListener("click", () => {
      const current = localStorage.getItem("ms_theme") || "dark";
      const next = current === "dark" ? "light" : "dark";
      localStorage.setItem("ms_theme", next);
      applyTheme();
      state.dirtyCharts = true;
    });

    exportBtn?.addEventListener("click", exportReport);

    // Optional local clear (UI-only) if button exists and backend clear route is not implemented
    clearHistoryBtn?.addEventListener("click", async () => {
      // Try backend clear endpoint if you have one
      try {
        const res = await fetch(apiUrl(`/api/history/clear?t=${Date.now()}`), { method: "POST" });
        if (res.ok) {
          await fetchHistory();
          return;
        }
      } catch {
        // ignore and fallback
      }

      // UI fallback only (does NOT delete server data)
      state.serverHistory = [];
      state.dirtyHistory = true;
      if (alertBox) alertBox.textContent = "INFO: History cleared in UI only (server clear endpoint not available).";
    });

    // initial state
    setZoom(state.zoom);
    setSpeed(state.speed);
    state.syncAxes = !!syncAxesChk?.checked;
    state.loop = !!loopChk?.checked;

    applyTheme();

    // Ensure a valid page is selected on load
    const initialPage =
      document.body.getAttribute("data-page") ||
      document.querySelector(".navbtn.active")?.dataset.page ||
      "dash";
    setPage(initialPage);

    // initial analysis text (until first fetch)
    if (analysisJson && !analysisJson.textContent.trim()) {
      analysisJson.textContent = "Waiting for /api/results ...";
    }

    // clock
    updateClock();
    setInterval(updateClock, 1000);

    // live pill blink
    livePill?.classList.add("blink");

    // resize => redraw charts once
    window.addEventListener("resize", () => {
      state.dirtyCharts = true;
    });

    // tab visibility => slower fetch in background
    document.addEventListener("visibilitychange", startFetchLoop);

    // initial fetches
    fetchResults();
    fetchHistory();

    // fetch loop
    startFetchLoop();

    // animation loop
    requestAnimationFrame(tick);

    // cleanup on unload
    window.addEventListener("beforeunload", () => {
      stopFetchLoop();
      abortIfActive(resultsAbort);
      abortIfActive(historyAbort);
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();