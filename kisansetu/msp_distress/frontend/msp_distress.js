/**
 * KisanSetu MSP Distress UI — portable frontend.
 *
 * Host page must expose: api(), toast(), esc(), fmt(), $, me, Chart (optional).
 *
 * Mount:
 *   MSPDistress.mountDashboard('mspDistressMount')
 *   MSPDistress.renderFarmerPage()
 *   MSPDistress.renderBuyerPage()
 */
(function (global) {
  const PUNE = { lat: 18.5204, lon: 73.8567 };

  function money(n) {
    return "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
  }

  async function geo() {
    try {
      if (!navigator.geolocation) return PUNE;
      const p = await new Promise((resolve, reject) =>
        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 4000 })
      );
      return { lat: p.coords.latitude, lon: p.coords.longitude };
    } catch {
      return PUNE;
    }
  }

  function bannerHtml(ev) {
    if (!ev) return "";
    if (ev.is_distress) {
      return `<div class="msp-banner alert">
        <div>
          <small>DISTRESS WARNING • Market crash risk</small>
          <h3>${esc(ev.crop)} mandi forecast is below MSP</h3>
          <p>Predicted mandi ${money(ev.P_forecast)}/kg versus official MSP ${money(ev.P_MSP)}/kg.
             Distress selling is blocked below the Dynamic MSP Floor.</p>
        </div>
        <div style="text-align:right">
          <small>F<sub>dynamic</sub></small>
          <span class="msp-floor">${money(ev.F_dynamic)}/kg</span>
        </div>
      </div>`;
    }
    return `<div class="msp-banner ok">
      <div>
        <small>MSP FLOOR HEALTHY</small>
        <h3>${esc(ev.crop)} is trading above the official MSP baseline</h3>
        <p>You can still use reverse bidding, cold storage or government procurement as optional tools.</p>
      </div>
      <div style="text-align:right">
        <small>F<sub>dynamic</sub></small>
        <span class="msp-floor">${money(ev.F_dynamic)}/kg</span>
      </div>
    </div>`;
  }

  function pathwayHtml(ev) {
    const cards = (ev.pathways || []).map((p) => {
      const go =
        p.id === "REVERSE_BID"
          ? "MSPDistress.goto('reverse')"
          : p.id === "COLD_STORAGE"
            ? "MSPDistress.goto('storage')"
            : "MSPDistress.goto('govt')";
      return `<article class="msp-path">
        <b>${esc(p.title)}</b>
        <p>${esc(p.summary)}</p>
        <small>Baseline ${money(p.floor)}/kg</small>
        <button class="primary" onclick="${go}">Open pathway</button>
      </article>`;
    });
    return `<div class="msp-path-grid">${cards.join("")}</div>`;
  }

  function visualizerHtml(ev) {
    const parts = [
      { label: "P_MSP", value: ev.p_msp, cls: "" },
      { label: "Quality adj. (×" + ev.q_m + ")", value: ev.p_msp_quality - ev.p_msp, cls: "gold" },
      { label: "Holding + logistics", value: ev.c_holding, cls: "amber" },
    ];
    const max = Math.max(ev.f_dynamic, 1);
    const rows = parts
      .map(
        (p) => `<div class="msp-bar-row"><span>${esc(p.label)}</span>
        <div class="msp-bar"><span class="${p.cls}" style="width:${Math.max(4, (Math.abs(p.value) / max) * 100)}%"></span></div>
        <b>${money(p.value)}</b></div>`
      )
      .join("");
    return `<div class="msp-viz">
      <div class="section-head"><h2>Dynamic Floor Calculator</h2>
        <span class="tag">${esc(ev.quality_grade)} · ${money(ev.F_dynamic)}/kg</span></div>
      <p style="color:#66756d;margin:0 0 8px">P<sub>MSP</sub> + quality grade + storage/logistics = F<sub>dynamic</sub></p>
      <div class="msp-stack">${rows}
        <div class="msp-bar-row"><span><b>F_dynamic</b></span>
          <div class="msp-bar"><span class="amber" style="width:100%"></span></div>
          <b>${money(ev.f_dynamic)}</b></div>
      </div>
      <canvas id="mspFloorChart" height="110"></canvas>
    </div>`;
  }

  function paintChart(ev) {
    const el = document.getElementById("mspFloorChart");
    if (!el || !global.Chart) return;
    if (global.charts && global.charts.mspFloor) {
      try { global.charts.mspFloor.destroy(); } catch (e) {}
    }
    const chart = new Chart(el, {
      type: "bar",
      data: {
        labels: ["P_MSP", "Quality adj.", "Holding", "F_dynamic"],
        datasets: [{
          data: [ev.p_msp, ev.p_msp_quality, ev.c_holding, ev.f_dynamic],
          backgroundColor: ["#176b3a", "#ca8a04", "#c2410c", "#9f1239"],
        }],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } },
      },
    });
    if (global.charts) global.charts.mspFloor = chart;
  }

  async function evaluateFromForm() {
    const loc = await geo();
    const crop = (document.getElementById("mspCrop") || {}).value || "Onion";
    const grade = (document.getElementById("mspGrade") || {}).value || "B";
    const qty = Number((document.getElementById("mspQty") || {}).value || 1000);
    const days = Number((document.getElementById("mspDays") || {}).value || 0);
    const offer = Number((document.getElementById("mspOffer") || {}).value || 0);
    return api("/api/v1/distress/evaluate", {
      method: "POST",
      body: JSON.stringify({
        crop,
        quantity: qty,
        quality_grade: grade,
        lat: loc.lat,
        lon: loc.lon,
        holding_days: days,
        current_offer_per_kg: offer || null,
      }),
    });
  }

  async function refreshPanel(targetId) {
    const box = document.getElementById(targetId);
    if (!box) return null;
    box.innerHTML = `<div class="empty">Checking mandi vs MSP…</div>`;
    try {
      const ev = await evaluateFromForm();
      global.__mspLast = ev;
      box.innerHTML = bannerHtml(ev) + pathwayHtml(ev) + visualizerHtml(ev);
      paintChart(ev);
      return ev;
    } catch (e) {
      box.innerHTML = `<div class="card error">${esc(e.message)}</div>`;
      return null;
    }
  }

  async function mountDashboard(elId) {
    const host = document.getElementById(elId);
    if (!host) return;
    host.innerHTML = `<div id="mspDashPanel"></div>
      <div class="toolbar"><button class="secondary" onclick="route('mspDistress')">Open MSP Distress desk</button></div>`;
    const loc = await geo();
    try {
      const crops = await api("/api/crops");
      const preferred = ["Onion", "Tomato", "Soybean", "Wheat"];
      const crop = (crops.find((c) => preferred.includes(c.name)) || crops[0] || {}).name || "Onion";
      const ev = await api("/api/v1/distress/evaluate", {
        method: "POST",
        body: JSON.stringify({ crop, quantity: 1000, quality_grade: "B", lat: loc.lat, lon: loc.lon }),
      });
      global.__mspLast = ev;
      document.getElementById("mspDashPanel").innerHTML =
        bannerHtml(ev) +
        (ev.is_distress ? pathwayHtml(ev) : `<p class="soft-note">Dynamic floor ${money(ev.F_dynamic)}/kg · Official MSP ${money(ev.P_MSP)}/kg</p>`);
    } catch (e) {
      document.getElementById("mspDashPanel").innerHTML =
        `<div class="msp-banner ok"><div><small>MSP DESK</small><h3>Distress redressal is online</h3>
         <p>${esc(e.message)}. Open the MSP page to evaluate a crop lot.</p></div></div>`;
    }
  }

  function formHtml(crops) {
    const opts = (crops || []).map((c) => `<option>${esc(c.name)}</option>`).join("");
    return `<div class="msp-form-row">
      <label>Crop<select id="mspCrop" class="control">${opts}</select></label>
      <label>Grade<select id="mspGrade" class="control"><option>B</option><option>A</option><option>C</option></select></label>
      <label>Qty (kg)<input id="mspQty" class="control" type="number" value="1000" min="1"></label>
      <label>Hold days<input id="mspDays" class="control" type="number" value="0" min="0"></label>
    </div>
    <div class="msp-form-row">
      <label>Current offer ₹/kg<input id="mspOffer" class="control" type="number" value="0" min="0" step="0.1"></label>
      <div></div><div></div>
      <button class="primary" onclick="MSPDistress.recompute()">Recompute F_dynamic</button>
    </div>`;
  }

  async function renderFarmerPage() {
    const crops = await api("/api/crops");
    $("content").innerHTML = `
      <div class="hero-reco"><div>
        <small>DISTRESS REDRESSAL</small>
        <h2>Dynamic MSP Floor — stop distress selling</h2>
        <p>If forecasted mandi price falls below official MSP, KisanSetu routes you to reverse bidding, cold storage + 70% DWR loan, or government procurement.</p>
      </div></div>
      ${formHtml(crops)}
      <div id="mspMainPanel"></div>
      <div id="mspWork"></div>`;
    await refreshPanel("mspMainPanel");
    goto("overview");
  }

  async function goto(which) {
    const work = document.getElementById("mspWork");
    if (!work) return;
    if (which === "reverse") return reverseFarmer(work);
    if (which === "storage") return storageFarmer(work);
    if (which === "govt") return govtFarmer(work);
    work.innerHTML = "";
  }

  async function reverseFarmer(work) {
    const ev = global.__mspLast;
    work.innerHTML = `<section class="card"><div class="section-head"><h2>Out-of-district reverse bidding</h2>
      <button class="primary" onclick="MSPDistress.postListing()">List lot at F_dynamic</button></div>
      <p>Minimum starting bid is locked to <b>${money(ev && ev.F_dynamic)}/kg</b>. Buyers see MSP-quality + logistics.</p>
      <div id="mspMyListings" class="msp-list"></div></section>`;
    const rows = await api("/api/v1/marketplace/reverse-bid/listings");
    document.getElementById("mspMyListings").innerHTML =
      rows
        .map(
          (l) => `<div class="msp-item"><div><b>#${l.listing_id} ${esc(l.crop)} · ${esc(l.quality_grade)}</b>
            <small>${num(l.quantity_kg)} kg · floor ${money(l.f_dynamic)}/kg · ${esc(l.origin_district)}</small>
            <small>Bids: ${(l.bids || []).map((b) => money(b.bid_per_kg) + "/kg").join(", ") || "none yet"}</small></div>
            <span class="tag">${esc(l.status)}</span></div>`
        )
        .join("") || `<div class="empty">No distress lots listed yet.</div>`;
  }

  async function postListing() {
    const ev = global.__mspLast;
    if (!ev) return toast("Evaluate a crop first");
    const loc = await geo();
    try {
      const d = await api("/api/v1/marketplace/reverse-bid/distress-list", {
        method: "POST",
        body: JSON.stringify({
          crop: ev.crop,
          quality_grade: ev.quality_grade,
          quantity_kg: ev.quantity_kg,
          lat: loc.lat,
          lon: loc.lon,
          origin_district: (me && me.district) || "",
          origin_state: (me && me.state) || "Maharashtra",
        }),
      });
      toast("Listed. Min bid " + money(d.min_bid_per_kg) + "/kg");
      goto("reverse");
    } catch (e) {
      toast(e.message);
    }
  }

  async function storageFarmer(work) {
    const loc = await geo();
    const fac = await api(`/api/v1/cold-storage/facilities?lat=${loc.lat}&lon=${loc.lon}`);
    const books = await api("/api/v1/cold-storage/bookings");
    work.innerHTML = `<section class="card"><div class="section-head"><h2>Cold storage & e-DWR</h2></div>
      <p>Pick a holding period from the AI recovery hint, then book. F_dynamic updates with storage days.</p>
      <div class="msp-list">${fac
        .map(
          (f) => `<div class="msp-item"><div><b>${esc(f.name)}</b>
          <small>${esc(f.district)} · ${num(f.distance_km)} km · ${money(f.daily_rate_per_kg)}/kg/day</small></div>
          <button class="primary" onclick="MSPDistress.bookStore(${f.facility_id})">Book ${Number((document.getElementById("mspDays") || {}).value || 7) || 7} days</button></div>`
        )
        .join("")}</div>
      <h3>My warehouse receipts</h3>
      <div class="msp-list">${books
        .map(
          (b) => `<div class="msp-item"><div><b>DWR-${String(b.booking_id).padStart(6, "0")}</b>
          <small>${esc(b.crop)} · ${num(b.quantity_kg)} kg · ${b.days_booked} days · floor ${money(b.f_dynamic)}/kg</small>
          <small>Hash ${esc(b.dwr_hash.slice(0, 16))}…</small></div>
          <button class="secondary" onclick="MSPDistress.takeLoan(${b.booking_id})">70% cash advance</button></div>`
        )
        .join("") || `<div class="empty">No deposits yet.</div>`}</div></section>`;
  }

  async function bookStore(facilityId) {
    const ev = global.__mspLast;
    if (!ev) return toast("Evaluate a crop first");
    const loc = await geo();
    const days = Number((document.getElementById("mspDays") || {}).value || 0) || ev.suggested_holding_days || 7;
    try {
      const d = await api("/api/v1/cold-storage/book", {
        method: "POST",
        body: JSON.stringify({
          facility_id: facilityId,
          crop: ev.crop,
          quality_grade: ev.quality_grade,
          quantity_kg: ev.quantity_kg,
          days_booked: days,
          lat: loc.lat,
          lon: loc.lon,
        }),
      });
      toast("e-DWR issued. New F_dynamic " + money(d.F_dynamic) + "/kg");
      global.__mspLast = Object.assign({}, ev, d.breakdown, { F_dynamic: d.F_dynamic, f_dynamic: d.F_dynamic });
      await refreshPanel("mspMainPanel");
      goto("storage");
    } catch (e) {
      toast(e.message);
    }
  }

  async function takeLoan(bookingId) {
    try {
      const d = await api("/api/v1/finance/dwr-loan", {
        method: "POST",
        body: JSON.stringify({ booking_id: bookingId }),
      });
      toast("Mock loan disbursed: " + money(d.advance_amount));
    } catch (e) {
      toast(e.message);
    }
  }

  async function govtFarmer(work) {
    const loc = await geo();
    const ev = global.__mspLast;
    const crop = (ev && ev.crop) || "";
    const centers = await api(`/api/v1/govt/procurement-centers?lat=${loc.lat}&lon=${loc.lon}&crop=${encodeURIComponent(crop)}`);
    work.innerHTML = `<section class="card"><div class="section-head"><h2>Sell to Government Procurement (MSP)</h2></div>
      <p>Nearest FCI / State mandi procurement yards. A pre-filled digital token is generated for registration.</p>
      <div class="msp-list">${centers
        .map(
          (c) => `<div class="msp-item"><div><b>${esc(c.name)}</b>
          <small>${esc(c.agency)} · ${esc(c.district)} · ${num(c.distance_km)} km · ${esc(c.crops)}</small></div>
          <button class="primary" onclick="MSPDistress.makeToken(${c.center_id})">Generate token</button></div>`
        )
        .join("")}</div></section>`;
  }

  async function makeToken(centerId) {
    const ev = global.__mspLast;
    if (!ev) return toast("Evaluate a crop first");
    try {
      const d = await api("/api/v1/govt/procurement-token", {
        method: "POST",
        body: JSON.stringify({
          center_id: centerId,
          crop: ev.crop,
          quality_grade: ev.quality_grade,
          quantity_kg: ev.quantity_kg,
        }),
      });
      toast("Token " + d.token_code);
      const r = await fetch(d.pdf_url, { headers: { Authorization: "Bearer " + (global.token || localStorage.getItem("gram_token") || "") } });
      if (r.ok) {
        const url = URL.createObjectURL(await r.blob());
        window.open(url, "_blank");
      }
    } catch (e) {
      toast(e.message);
    }
  }

  async function renderBuyerPage() {
    const listings = await api("/api/v1/marketplace/reverse-bid/listings");
    $("content").innerHTML = `
      <div class="hero-reco"><div>
        <small>OUT-OF-ZONE LOTS</small>
        <h2>Distress reverse bidding</h2>
        <p>Bids below F_dynamic are rejected. Cost sheet includes quality certificate and logistics.</p>
      </div></div>
      <div class="msp-list">${listings
        .map(
          (l) => `<div class="msp-item"><div>
            <b>${esc(l.crop)} · Grade ${esc(l.quality_grade)}</b>
            <small>${num(l.quantity_kg)} kg from ${esc(l.origin_district || "unknown district")}, ${esc(l.origin_state)}</small>
            <small>Floor ${money(l.f_dynamic)}/kg · MSP-quality ${money(l.p_msp_quality)} + logistics ${money(l.logistics_per_kg)}</small>
            <input id="bid-${l.listing_id}" class="control" type="number" min="${l.f_dynamic}" step="0.1" value="${l.f_dynamic}" style="margin-top:8px;max-width:220px">
          </div>
          <button class="primary" onclick="MSPDistress.placeBid(${l.listing_id},${l.f_dynamic})">Bid ≥ floor</button></div>`
        )
        .join("") || `<div class="empty">No distress lots on the market.</div>`}</div>`;
  }

  async function placeBid(listingId, floor) {
    const el = document.getElementById("bid-" + listingId);
    const bid = Number(el && el.value);
    if (bid < floor) {
      toast("Bid is below F_dynamic and will be blocked");
    }
    try {
      const d = await api(`/api/v1/marketplace/reverse-bid/${listingId}/bid`, {
        method: "POST",
        body: JSON.stringify({
          bid_per_kg: bid,
          buyer_district: (me && me.district) || "",
        }),
      });
      toast("Bid accepted at " + money(d.bid_per_kg) + "/kg");
      renderBuyerPage();
    } catch (e) {
      toast(e.message);
    }
  }

  async function recompute() {
    await refreshPanel("mspMainPanel");
  }

  global.MSPDistress = {
    mountDashboard,
    renderFarmerPage,
    renderBuyerPage,
    recompute,
    goto,
    postListing,
    bookStore,
    takeLoan,
    makeToken,
    placeBid,
  };
})(window);
