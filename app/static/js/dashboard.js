/* SoilSage dashboard — UI layer.
   GET /api/reading (2s poll), GET/POST /api/location, GET/POST /api/mode. */
(function () {
  "use strict";

  var modeSelect = document.getElementById("modeSelect");
  var modeLocked = window.SOILSAGE_MODE_LOCKED === true;
  var geoBtn = document.getElementById("geoBtn");
  var setCoordsBtn = document.getElementById("setCoordsBtn");
  var latInput = document.getElementById("latInput");
  var lonInput = document.getElementById("lonInput");
  var rainfallSourceEl = document.getElementById("rainfallSource");
  var locationStatusEl = document.getElementById("locationStatus");
  var themeBtn = document.getElementById("themeBtn");
  var alertCard = document.getElementById("alertCard");
  var statusIcon = document.getElementById("statusIcon");
  var rainBadge = document.getElementById("rainBadge");
  var rainfallBadge = document.getElementById("rainfallBadge");

  var ICONS = {
    ok: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 4.5-5.5"/></svg>',
    warn: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5L22 20H2z"/><path d="M12 10v4"/><path d="M12 17.5h.01"/></svg>',
    bad: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg>'
  };

  /* ---------- theme: default to light Mint Canvas, toggle persists ---------- */
  var root = document.documentElement;
  var ICON_MOON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';
  var ICON_SUN = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  function applyTheme(t) {
    root.setAttribute("data-bs-theme", t);
    try { localStorage.setItem("soilsage-theme", t); } catch (_e) {}
    if (themeBtn) {
      themeBtn.setAttribute("aria-pressed", String(t === "dark"));
      themeBtn.innerHTML = t === "dark" ? ICON_SUN : ICON_MOON;
      themeBtn.title = t === "dark" ? "Switch to light mode" : "Switch to dark mode";
      themeBtn.setAttribute("aria-label", themeBtn.title);
    }
  }
  (function initTheme() {
    var saved = null;
    try { saved = localStorage.getItem("soilsage-theme"); } catch (_e) {}
    applyTheme(saved === "dark" || saved === "light" ? saved : "light");
  })();
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      applyTheme(root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark");
      drawChart();
    });
  }

  /* ---------- animated numbers (150-250ms, ease-out) ---------- */
  var displayed = {};
  function animateNumber(id, target, fmt) {
    var el = document.getElementById(id);
    if (!el) return;
    var from = displayed[id];
    if (from === undefined || from === null || !isFinite(from)) { el.textContent = fmt(target); displayed[id] = target; return; }
    if (from === target) return;
    var start = null, dur = 200;
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min(1, (ts - start) / dur);
      var e = 1 - Math.pow(1 - p, 3);
      var v = from + (target - from) * e;
      el.textContent = fmt(v);
      if (p < 1) requestAnimationFrame(step);
      else { displayed[id] = target; }
    }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { el.textContent = fmt(target); displayed[id] = target; return; }
    requestAnimationFrame(step);
  }
  var fmt2 = function (v) { return v.toFixed(2); };
  var fmt1 = function (v) { return v.toFixed(1); };
  var fmtInt = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
  var fmt0 = function (v) { return fmtInt.format(Math.round(v)); };

  function titleCase(s) {
    return String(s).toLowerCase().replace(/(?:^|\s)\S/g, function (c) { return c.toUpperCase(); });
  }

  /* ---------- single source of truth for latest pH ---------- */
  var state = { ph: null };

  /* ---------- pH history chart: HH:MM:SS x, <=5 ticks, optimal band ---------- */
  var history = { t: [], ph: [] };
  var chart = null;
  function chartColors() {
    var dark = root.getAttribute("data-bs-theme") === "dark";
    return {
      line: dark ? "#b7ffb4" : "#262626",
      fill: dark ? "rgba(183,255,180,0.10)" : "rgba(38,38,38,0.08)",
      band: dark ? "rgba(0,255,0,0.16)" : "rgba(0,255,0,0.28)",
      grid: dark ? "rgba(183,255,180,0.14)" : "rgba(38,38,38,0.15)",
      tick: dark ? "#9ec49d" : "#262626"
    };
  }
  function toHMS(ts) {
    var d = new Date(ts);
    function p(n) { return (n < 10 ? "0" : "") + n; }
    return p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
  }
  function bandArrays(n) {
    var top = [], bot = [];
    for (var i = 0; i < n; i++) { top.push(7.5); bot.push(6.0); }
    return { top: top, bot: bot };
  }
  function ensureChart() {
    if (chart) return true;
    var cv = document.getElementById("phChart");
    if (!cv || typeof Chart === "undefined") return false;
    if (cv.clientWidth === 0) return false;
    var c = chartColors();
    Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", -system-ui, sans-serif';
    Chart.defaults.font.size = 11;
    var bands = bandArrays(history.ph.length);
    chart = new Chart(cv, {
      type: "line",
      data: { labels: history.t.slice(), datasets: [
        { data: bands.top, borderWidth: 0, pointRadius: 0, pointHoverRadius: 0, fill: "+1", backgroundColor: c.band, tension: 0 },
        { data: bands.bot, borderWidth: 0, pointRadius: 0, pointHoverRadius: 0, fill: false },
        { data: history.ph.slice(), borderColor: c.line, backgroundColor: c.fill, borderWidth: 2,
          pointRadius: function (ctx) { return ctx.dataIndex === ctx.dataset.data.length - 1 ? 4 : 0; },
          pointHoverRadius: 5, pointBackgroundColor: "#00ff00", pointBorderColor: "#262626", pointBorderWidth: 1.5, tension: 0.2, fill: true }
      ] },
      options: {
        responsive: true, maintainAspectRatio: false,
        animation: { duration: 200, easing: "easeOutQuart" },
        plugins: {
          legend: { display: false },
          tooltip: { enabled: true, mode: "index", intersect: false, backgroundColor: "#262626", titleFont: { size: 11 }, bodyFont: { size: 12 }, padding: 10, cornerRadius: 4, displayColors: false,
            filter: function (item) { return item.datasetIndex === 2; },
            callbacks: { label: function (item) { return "pH " + Number(item.parsed.y).toFixed(2); } } }
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: c.tick, maxTicksLimit: 5, maxRotation: 0, autoSkip: true } },
          y: { suggestedMin: 4, suggestedMax: 9.5, grid: { color: c.grid }, border: { display: false }, ticks: { color: c.tick, stepSize: 1 } }
        }
      }
    });
    return true;
  }
  function drawChart() {
    if (chart) { try { chart.destroy(); } catch (_e) {} chart = null; }
    ensureChart();
  }
  function pushHistory(ph) {
    if (!isFinite(ph)) return;
    history.t.push(toHMS(Date.now())); history.ph.push(ph);
    if (history.t.length > 40) { history.t.shift(); history.ph.shift(); }
    if (!ensureChart()) return;
    var bands = bandArrays(history.ph.length);
    chart.data.labels = history.t.slice();
    chart.data.datasets[0].data = bands.top;
    chart.data.datasets[1].data = bands.bot;
    chart.data.datasets[2].data = history.ph.slice();
    chart.update();
  }
  window.addEventListener("resize", function () {
    if (chart) { try { chart.resize(); } catch (_e) {} }
    else { ensureChart(); }
  });
  window.addEventListener("beforeprint", function () {
    if (chart) { try { chart.resize(); } catch (_e) {} }
  });

  /* ---------- location ---------- */
  function postLocation(latitude, longitude, source) {
    return fetch("/api/location", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ latitude: latitude, longitude: longitude, source: source || "manual" })
    }).then(function (res) { return res.json(); });
  }
  function loadLocation() {
    return fetch("/api/location", { cache: "no-store" }).then(function (res) { return res.json(); }).then(function (data) {
      if (!data.ok || !data.location) return false;
      var loc = data.location;
      if (typeof loc.latitude === "number" && typeof loc.longitude === "number") {
        latInput.value = loc.latitude.toFixed(6);
        lonInput.value = loc.longitude.toFixed(6);
        locationStatusEl.textContent = "Coordinates: " + loc.latitude.toFixed(6) + ", " + loc.longitude.toFixed(6);
        return true;
      }
      return false;
    }).catch(function () { return false; });
  }
  var GEO_ERR = "Couldn't get your location. Enter coordinates manually.";
  function geoSecureMsg() {
    var port = window.location.port || "5000";
    return "Location needs HTTPS or localhost. Open http://127.0.0.1:" + port + " or enter coordinates manually.";
  }
  function geoErrorMsg(err) {
    if (err && err.code === 1) return "Location permission is blocked for this site. Allow it in the browser's site settings, or enter coordinates manually.";
    return "Your device couldn't determine its location. Check that location services are on, or enter coordinates manually.";
  }
  function requestBrowserLocation(autoRequest) {
    return new Promise(function (resolve) {
      if (!navigator.geolocation) { locationStatusEl.textContent = GEO_ERR; resolve(false); return; }
      if (window.isSecureContext === false) { locationStatusEl.textContent = geoSecureMsg(); resolve(false); return; }
      geoBtn.disabled = true;
      locationStatusEl.textContent = autoRequest ? "Requesting browser location (auto)..." : "Requesting browser location...";
      navigator.geolocation.getCurrentPosition(function (pos) {
        var lat = pos.coords.latitude, lon = pos.coords.longitude;
        latInput.value = lat.toFixed(6); lonInput.value = lon.toFixed(6);
        postLocation(lat, lon, autoRequest ? "browser-auto" : "browser").then(function (result) {
          if (!result.ok) throw new Error(result.error || "Failed to set location");
          locationStatusEl.textContent = "Coordinates: " + result.location.latitude.toFixed(6) + ", " + result.location.longitude.toFixed(6);
          resolve(true);
        }).catch(function (e) { locationStatusEl.textContent = e.message; resolve(false); })
        .then(function () { geoBtn.disabled = false; });
      }, function (err) {
        if (window.console && console.warn) console.warn("SoilSage geolocation failed:", err);
        locationStatusEl.textContent = geoErrorMsg(err);
        geoBtn.disabled = false; resolve(false);
      }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
    });
  }

  /* ---------- mode ---------- */
  function setMode(mode) {
    return fetch("/api/mode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: mode })
    }).then(function (res) { return res.json(); });
  }
  function clearReadingUI() {
    state.ph = null;
    ["ph", "n", "p", "k", "temperature", "humidity", "water_temp", "rainfall"].forEach(function (id) {
      var el = document.getElementById(id); if (el) el.textContent = "-";
      setTileStatus(id, null, true);
    });
    document.getElementById("crop").textContent = "-";
    var cs0 = document.getElementById("cropScore");
    if (cs0) cs0.classList.add("d-none");
    document.getElementById("fertilizer").textContent = "-";
    var fc = document.getElementById("fertChips"); if (fc) fc.innerHTML = "";
    var ca = document.getElementById("cropAlts"); if (ca) ca.innerHTML = "";
    var ff = document.getElementById("fitFactors"); if (ff) ff.innerHTML = "";
    var fcmp = document.getElementById("fitComparison"); if (fcmp) fcmp.textContent = "";
    document.getElementById("raw").textContent = "-";
    document.getElementById("action").textContent = "";
    document.getElementById("fertilizerReason").textContent = "";
  }
  function normalizeSerialError(message) {
    var prefix = "ESP32 not detected. Connect the board and verify the serial port.";
    var text = String(message || "").toLowerCase();
    if (text.indexOf("permission denied") !== -1) return "ESP32 found, but access to the serial port was denied. Add your user to the dialout group and reconnect.";
    if (text.indexOf("device reports readiness to read but returned no data") !== -1) return "Serial connection dropped while reading. Reconnect the ESP32 USB cable and wait a few seconds.";
    if (text.indexOf("esp32 not connected") !== -1 || text.indexOf("cannot open") !== -1 || text.indexOf("no such file or directory") !== -1) return prefix;
    return message || "Unable to fetch serial reading";
  }

  var firstLoad = true;
  function setLoading(on) {
    ["crop", "status"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.classList.toggle("ss-skeleton", on);
    });
    var fc = document.getElementById("fertChips");
    if (fc) fc.classList.toggle("ss-skeleton", on);
  }

  /* ---------- "Updated Ns ago" ---------- */
  var lastOkAt = 0;
  setInterval(function () {
    var el = document.getElementById("updated");
    if (!el || !lastOkAt) return;
    var s = Math.max(0, Math.round((Date.now() - lastOkAt) / 1000));
    el.textContent = s < 5 ? "just now" : (s < 60 ? s + "s ago" : Math.floor(s / 60) + "min ago");
  }, 1000);

  function escHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  /* ---------- crop alternatives ---------- */
  function renderAlts(data) {
    var box = document.getElementById("cropAlts");
    if (!box) return { topScore: null };
    var list = data && data.top_crops;
    if (!list || !list.length) { box.innerHTML = ""; return { topScore: null }; }
    var top = { crop: String(list[0].crop), score: Number(list[0].score) };
    if (!isFinite(top.score)) top.score = 1;
    var html = '<span class="ss-alts-note">Runner-up fits</span>';
    for (var i = 1; i < Math.min(list.length, 4); i++) {
      var s = Math.min(Number(list[i].score), top.score);
      html += '<span class="ss-alt"><b>' + escHtml(titleCase(list[i].crop)) + '</b><span>' + Math.round(s * 100) + '%</span></span>';
    }
    box.innerHTML = html;
    return { topScore: top.score, topCrop: top.crop };
  }

  /* ---------- plain-language crop explanation (Pillar 3) ---------- */
  function renderExplanation(data, cropName) {
    var exp = data && data.explanation;
    var titleEl = document.getElementById("explainTitle");
    var summaryEl = document.getElementById("fitSummary");
    var factorsEl = document.getElementById("fitFactors");
    var cmpEl = document.getElementById("fitComparison");
    var badgeEl = document.getElementById("suitabilityBadge");
    var soilNoteEl = document.getElementById("cropSoilNote");

    if (titleEl && cropName) {
      titleEl.textContent = "◉ 03 / Why " + cropName + " fits your soil";
    }
    if (!exp) return;

    if (badgeEl && exp.overall_suitability !== undefined) {
      badgeEl.textContent = exp.overall_suitability + "% soil match";
    }
    if (soilNoteEl && exp.soil_note) {
      soilNoteEl.textContent = exp.soil_note + (exp.water_note ? " · " + exp.water_note + "." : ".");
    }
    if (summaryEl && exp.summary) {
      summaryEl.textContent = exp.summary;
    }

    if (factorsEl && Array.isArray(exp.factors)) {
      var ordered = exp.factors.slice().sort(function (a, b) { return b.fit_pct - a.fit_pct; }).slice(0, 4);
      factorsEl.innerHTML = ordered.map(function (f) {
        var isWarn = (f.status === "low" || f.status === "high");
        var pillText = f.status === "ideal" ? "Ideal match"
          : f.status === "good" ? "Good fit"
          : f.status === "low" ? "Needs boost" : "Watch level";
        return (
          '<div class="ss-fit-item">' +
            '<div class="ss-fit-head">' +
              '<span>◉ ' + escHtml(f.short) + '</span>' +
              '<span class="ss-fit-pill' + (isWarn ? " is-warn" : "") + '">' + pillText + '</span>' +
            '</div>' +
            '<div class="ss-fit-val">' + escHtml(f.value_display) + '</div>' +
            '<div class="ss-fit-ideal">Crop window ' + escHtml(f.ideal_range) + '</div>' +
            '<div class="ss-fit-note">' + escHtml(f.reason) + '</div>' +
          '</div>'
        );
      }).join("");
    }

    if (cmpEl) {
      var cmps = exp.comparisons || [];
      cmpEl.textContent = cmps.length ? "◉ " + cmps[0].reason : "";
    }
  }

  /* ---------- fertilizer chips + one-line summary ---------- */
  var CHIP_ICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6"/><path d="M10 3v5.5L4.5 18a2 2 0 0 0 1.8 3h11.4a2 2 0 0 0 1.8-3L14 8.5V3"/></svg>';
  function renderFertilizer(mix, reason) {
    var box = document.getElementById("fertChips");
    var hidden = document.getElementById("fertilizer");
    if (hidden) { hidden.textContent = mix; hidden.title = mix; }
    if (box) {
      var parts = String(mix).split("+").map(function (p) { return p.trim(); }).filter(Boolean).slice(0, 6);
      box.innerHTML = parts.map(function (p) { return '<span class="ss-chip">' + CHIP_ICON + escHtml(p) + "</span>"; }).join("");
      box.title = mix;
    }
    var bits = [];
    if (/Nitrogen is low/i.test(reason)) bits.push("low nitrogen");
    if (/Phosphorus is low/i.test(reason)) bits.push("low phosphorus");
    if (/Potassium is low/i.test(reason)) bits.push("low potassium");
    if (/lime/i.test(mix)) bits.push("lime for acidity");
    if (/compost/i.test(mix)) bits.push("compost for alkalinity");
    var oneLine = bits.length ? "Formulated to correct " + bits.join(", ") + "." : "Balanced maintenance formulation for the recommended crop.";
    var fertEl = document.getElementById("fertilizerReason");
    if (fertEl) { fertEl.textContent = oneLine; fertEl.title = reason || oneLine; }
    renderFertRate(String(mix));
  }

  var RATE_TABLE = [
    [/urea/i, "Urea ≈55 kg/ha"],
    [/dap/i, "DAP ≈60 kg/ha"],
    [/mop/i, "MOP ≈40 kg/ha"],
    [/ssp/i, "SSP ≈80 kg/ha"],
    [/npk/i, "NPK blend ≈100 kg/ha"],
    [/lime/i, "Lime ≈400 kg/ha"],
    [/compost|organic|mulch/i, "Compost ≈2 t/ha"]
  ];
  function renderFertRate(mix) {
    var el = document.getElementById("fertRate");
    if (!el) return;
    var rates = [];
    RATE_TABLE.forEach(function (row) {
      if (row[0].test(mix)) rates.push(row[1]);
    });
    el.innerHTML = rates.length
      ? "◉ FIELD RATE: " + escHtml(rates.join(" · "))
      : "";
  }

  /* ---------- N/P/K current-vs-target mini bars ---------- */
  var NPK_BAR_COLORS = { low: "#f59e0b", optimal: "#00ff00", high: "#ef4444" };
  function npkStatus(cur, target) {
    if (cur < target * 0.75) return "low";
    if (cur > target * 1.5) return "high";
    return "optimal";
  }
  function renderNpkBars(d) {
    var box = document.getElementById("npkBars");
    if (!box) return;
    var colors = NPK_BAR_COLORS;
    var targetMap = { n: 37, p: 51, k: 32 };
    if (d.explanation && Array.isArray(d.explanation.factors)) {
      d.explanation.factors.forEach(function (f) {
        if (f.feature && isFinite(f.optimal_median)) {
          targetMap[f.feature] = Math.round(f.optimal_median);
        }
      });
    }
    var rows = [
      { k: "N", cur: d.n, target: targetMap.n },
      { k: "P", cur: d.p, target: targetMap.p },
      { k: "K", cur: d.k, target: targetMap.k }
    ];
    box.innerHTML = rows.map(function (r) {
      var scale = Math.max(r.target * 2, r.cur, 1);
      var fill = Math.min(100, (r.cur / scale) * 100).toFixed(1);
      var tick = Math.min(100, (r.target / scale) * 100).toFixed(1);
      var st = npkStatus(r.cur, r.target);
      var word = st === "low" ? "Low" : st === "high" ? "High" : "Optimal";
      return '<div class="ss-npk"><span class="ss-npk-k">' + r.k + " · AIM " + r.target +
        '</span><span class="ss-npkbar" title="Target ' + r.target + ' mg/kg · ' + word + '"><i style="width:' + fill + "%;background:" + colors[st] + '"></i><b style="left:' + tick + '%" title="Target ' + r.target + '"></b></span>' +
        '<span class="ss-npk-v">' + escHtml(fmt0(r.cur)) + " / " + r.target + "</span></div>";
    }).join("");
  }

  /* ---------- rainfall badge ---------- */
  function renderRainfall(meta) {
    var src = meta.source || "default";
    var kind = "default", label = "Default value", sentence = "Set a location to fetch live rainfall.";
    if (src === "open-meteo" && !meta.stale) { kind = "live"; label = "Live"; sentence = "Live 30-day cumulative rainfall for your field coordinates."; }
    else if (src === "open-meteo-cache" || src === "last-known-cache") { kind = "cached"; label = "Cached"; sentence = "Showing cached rainfall. Refreshes automatically."; }
    if (rainBadge) { rainBadge.textContent = label; rainBadge.className = "ss-badge" + (kind === "live" ? " is-live" : kind === "cached" ? " is-cached" : ""); }
    rainfallSourceEl.textContent = sentence;
    var isDefault = (src === "default-constant");
    if (rainfallBadge) rainfallBadge.classList.toggle("d-none", !isDefault);
    return isDefault;
  }

  function setAlert(sev) {
    var statusEl = document.getElementById("status");
    if (alertCard) alertCard.setAttribute("data-sev", sev);
    if (statusIcon) {
      statusIcon.innerHTML = ICONS[sev] || ICONS.bad;
    }
    return statusEl;
  }

  /* ---------- tile range status ---------- */
  var RANGES = {
    ph:          { lo: 4, hi: 9,  optLo: 6.0, optHi: 7.5 },
    n:           { lo: 0, hi: 150, optLo: 28, optHi: 56, target: 37 },
    p:           { lo: 0, hi: 200, optLo: 38, optHi: 77, target: 51 },
    k:           { lo: 0, hi: 200, optLo: 24, optHi: 48, target: 32 },
    temperature: { lo: 0, hi: 45, optLo: 20, optHi: 30 },
    humidity:    { lo: 0, hi: 100, optLo: 40, optHi: 70 },
    water_temp:  { lo: 0, hi: 40, optLo: 20, optHi: 30 },
    rainfall:    { lo: 0, hi: 300, total: true }
  };
  function setTileStatus(id, val, isMissing) {
    var el = document.getElementById(id);
    if (!el) return;
    var tile = el.closest(".ss-tile");
    if (!tile) return;
    var label = tile.querySelector(".ss-tlabel");
    var marker = tile.querySelector(".ss-range i");
    tile.classList.remove("is-low", "is-high", "is-stale");
    if (isMissing || val === null || !isFinite(val)) {
      tile.classList.add("is-stale");
      tile.title = "Sensor disconnected. Displaying placeholder.";
      if (label) label.textContent = "";
      if (marker) marker.style.left = "50%";
      return;
    }
    tile.title = "";
    var r = RANGES[id];
    if (!r) return;
    var pct = Math.min(100, Math.max(0, ((val - r.lo) / (r.hi - r.lo)) * 100));
    if (marker) marker.style.left = pct.toFixed(1) + "%";
    if (r.total) { if (label) label.textContent = "Total"; return; }
    var cls = "", text = "Optimal";
    if (val < r.optLo) { cls = "is-low"; text = "Low"; }
    else if (val > r.optHi) { cls = "is-high"; text = "High"; }
    if (cls) tile.classList.add(cls);
    if (label) label.textContent = text;
  }

  /* ---------- main poll ---------- */
  function updateSensor(id, val, isMissing, fmt) {
    var el = document.getElementById(id);
    if (!el) return;
    if (isMissing) {
      el.textContent = "—";
      displayed[id] = undefined;
      setTileStatus(id, null, true);
    } else {
      animateNumber(id, val, fmt);
      setTileStatus(id, val, false);
    }
  }

  function refresh() {
    return fetch("/api/reading", { cache: "no-store" }).then(function (res) { return res.json(); }).then(function (data) {
      if (firstLoad) { setLoading(false); firstLoad = false; }
      if (!data.ok) {
        if (data.mode && modeSelect) modeSelect.value = data.mode;
        clearReadingUI();
        var msg = data.mode === "serial" ? normalizeSerialError(data.error) : (data.error || "Dashboard error");
        var s0 = setAlert("bad");
        s0.textContent = msg;
        s0.className = "ss-type-20 fw-bold";
        return;
      }
      if (modeSelect) modeSelect.value = data.mode;
      lastOkAt = Date.now();
      currentMode = data.mode;
      updateDevVisibility();

      var phMissing = (data.ph <= 0 || data.ph > 13.5);
      state.ph = phMissing ? null : data.ph;
      updateSensor("ph", data.ph, phMissing, fmt2);
      updateSensor("n", data.n, data.n < 0 || data.n === null, fmt0);
      updateSensor("p", data.p, data.p < 0 || data.p === null, fmt0);
      updateSensor("k", data.k, data.k < 0 || data.k === null, fmt0);
      updateSensor("temperature", data.temperature, data.humidity < 0 || data.temperature < 0, fmt1);
      updateSensor("humidity", data.humidity, data.humidity < 0, fmt1);
      updateSensor("water_temp", data.water_temp, data.water_temp <= -127, fmt1);
      updateSensor("rainfall", data.rainfall, false, fmt1);

      var altInfo = renderAlts(data);
      var cropName = (altInfo.topCrop !== undefined) ? titleCase(altInfo.topCrop) : titleCase(data.prediction);
      var cropEl = document.getElementById("crop");
      cropEl.textContent = cropName;
      cropEl.title = cropName;
      var scoreEl = document.getElementById("cropScore");
      if (scoreEl) {
        if (altInfo.topScore !== null) {
          scoreEl.textContent = Math.round(altInfo.topScore * 100) + "% match";
          scoreEl.classList.remove("d-none");
        } else {
          scoreEl.classList.add("d-none");
        }
      }
      renderFertilizer(data.fertilizer, data.fertilizer_reason || "");
      renderExplanation(data, cropName);

      var rawEl = document.getElementById("raw");
      var rawFull = String(data.raw);
      rawEl.textContent = rawFull.length > 200 ? rawFull.slice(0, 200) + "…" : rawFull;
      rawEl.title = rawFull;

      var meta = data.rainfall_meta || {};
      renderRainfall(meta, data.rainfall);
      if (meta.latitude !== undefined && meta.longitude !== undefined) {
        locationStatusEl.textContent = "Coordinates: " + Number(meta.latitude).toFixed(6) + ", " + Number(meta.longitude).toFixed(6);
      }

      var actionEl = document.getElementById("action");
      if (data.stale) {
        var s1 = setAlert("bad");
        s1.textContent = "ESP32 frozen or disconnected";
        s1.className = "ss-type-20 fw-bold";
        actionEl.textContent = "The sensor stopped sending data. Check the connection, then wait for fresh readings.";
      } else {
        var sev = data.level === "ok" ? "ok" : (data.level === "warn" ? "warn" : "bad");
        var s2 = setAlert(sev);
        s2.textContent = data.status;
        s2.className = "ss-type-20 fw-bold";
        actionEl.textContent = data.action;
      }
      var dup = document.getElementById("actionDup");
      if (dup) dup.textContent = "";
      renderNpkBars(data);
      pushHistory(state.ph === null ? NaN : state.ph);
      placeMarker();
    }).catch(function (err) {
      if (window.console && console.error) console.error("SoilSage refresh failed:", err);
      if (firstLoad) { setLoading(false); firstLoad = false; }
      clearReadingUI();
      var s = setAlert("bad");
      s.textContent = "Dashboard fetch error";
      s.className = "ss-type-20 fw-bold";
    });
  }

  function placeMarker() {
    var marker = document.getElementById("litmusMarker");
    var tag = document.getElementById("phMarkerLabel");
    if (!marker) return;
    var v = state.ph;
    if (v === null || !isFinite(v)) { if (tag) tag.textContent = "pH –"; return; }
    var c = Math.min(9, Math.max(4, v));
    marker.style.left = (((c - 4) / 5) * 100).toFixed(1) + "%";
    if (tag) tag.textContent = "pH " + v.toFixed(1);
  }

  /* ---------- wiring ---------- */
  if (modeSelect) {
    if (modeLocked) { modeSelect.disabled = true; }
    else {
      modeSelect.addEventListener("change", function (event) {
        var desired = event.target.value;
        modeSelect.disabled = true;
        setMode(desired).then(function (d) {
          if (!d.ok) throw new Error(d.error || "Failed to switch mode");
        }).catch(function (e) {
          var s = setAlert("bad");
          s.textContent = e.message; s.className = "ss-type-20 fw-bold";
        }).then(function () { modeSelect.disabled = false; refresh(); });
      });
    }
  }
  var modePill = document.querySelector(".mode-pill");
  document.addEventListener("keydown", function (event) {
    if (event.key === "m" && !modeLocked && modePill) {
      modePill.style.display = modePill.style.display === "none" ? "" : "none";
    }
  });

  var locForm = document.getElementById("locForm");
  function submitCoords() {
    var lat = Number(latInput.value.trim()), lon = Number(lonInput.value.trim());
    if (!isFinite(lat) || !isFinite(lon)) { locationStatusEl.textContent = "Enter valid numeric latitude and longitude."; return; }
    setCoordsBtn.disabled = true;
    postLocation(lat, lon, "manual").then(function (result) {
      if (!result.ok) throw new Error(result.error || "Failed to set location");
      locationStatusEl.textContent = "Coordinates: " + result.location.latitude.toFixed(6) + ", " + result.location.longitude.toFixed(6);
      refresh();
    }).catch(function (e) { locationStatusEl.textContent = e.message; })
    .then(function () { setCoordsBtn.disabled = false; });
  }
  if (locForm) locForm.addEventListener("submit", function (e) { e.preventDefault(); submitCoords(); });
  else setCoordsBtn.addEventListener("click", submitCoords);
  geoBtn.addEventListener("click", function () { requestBrowserLocation(false).then(refresh); });

  /* ---------- preview-data menu ---------- */
  var currentMode = null;
  var devAllowed = (function () {
    try {
      var p = new URLSearchParams(window.location.search);
      return p.get("dev") === "1" || p.get("break") === "1";
    } catch (_e) { return false; }
  })();
  function updateDevVisibility() {
    var menu = document.getElementById("devMenu");
    if (!menu) return;
    var show = devAllowed || currentMode === "sim" || currentMode === null;
    menu.style.display = show ? "" : "none";
    if (!show) menu.removeAttribute("open");
  }
  updateDevVisibility();
  document.addEventListener("click", function (e) {
    var menu = document.getElementById("devMenu");
    if (menu && menu.open && !menu.contains(e.target)) menu.removeAttribute("open");
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      var menu = document.getElementById("devMenu");
      if (menu && menu.open) menu.removeAttribute("open");
    }
  });

  (function () {
    var toggle = document.getElementById("breakToggle");
    if (!toggle) return;
    var menu = document.getElementById("devMenu");
    var mode = "demo", timer = null;
    function setText(id, v) { var el = document.getElementById(id); if (el) el.textContent = v; }
    var FIX = {
      worst: { crop: "CHRISTOPHER ALEXANDER MONTGOMERY III", fertilizerReason: "Formulated to correct low nitrogen, low phosphorus, low potassium, lime for acidity.", status: "ESP32 frozen or disconnected", action: "The sensor stopped sending data. Check the connection, then wait for fresh readings.", ph: "13.99", n: "2000", p: "2000", k: "2000", temperature: "-40.0", humidity: "100.0", water_temp: "-127.0", rainfall: "1000.0", raw: "13.99,2000,2000,2000,-40.0,100.0,-127.0", rainfallSource: "Showing cached rainfall. Refreshes automatically.", locationStatus: "Coordinates: 12.971600, 77.594600" },
      empty: { crop: "-", fertilizerReason: "", status: "", action: "", ph: "-", n: "-", p: "-", k: "-", temperature: "-", humidity: "-", water_temp: "-", rainfall: "-", raw: "-", rainfallSource: "", locationStatus: "Coordinates: not set" },
      one: { crop: "JO", fertilizerReason: "Balanced maintenance formulation for the recommended crop.", status: "Chemical equilibrium maintained", action: "pH is in the balanced range.", ph: "7.0", n: "1", p: "1", k: "1", temperature: "25.0", humidity: "50.0", water_temp: "25.0", rainfall: "1.0", raw: "7.00,1,1,1,25.0,50.0,25.0", rainfallSource: "Live 30-day cumulative rainfall for your field coordinates.", locationStatus: "Coordinates: 0.000000, 0.000000" }
    };
    function setState(next) {
      mode = next;
      toggle.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.break === mode)); });
      if (menu) menu.removeAttribute("open");
      if (timer) { clearInterval(timer); timer = null; }
      if (mode === "demo") return;
      var f = FIX[mode]; if (!f) return;
      var apply = function () {
        Object.keys(f).forEach(function (k) { setText(k, f[k]); });
        var cs = document.getElementById("cropScore");
        if (cs) cs.classList.add("d-none");
      };
      apply(); timer = setInterval(function () { if (mode !== "demo") apply(); }, 2100);
    }
    toggle.addEventListener("click", function (e) { var b = e.target.closest("button[data-break]"); if (b) setState(b.dataset.break); });
  })();

  /* boot */
  setLoading(true);
  refresh();
  loadLocation().then(function (has) { if (!has) return requestBrowserLocation(true); });
  setInterval(refresh, 2000);
})();
