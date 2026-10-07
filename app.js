const $ = (id) => document.getElementById(id);
const state = { items: [], sortKey: "price_per_can", sortDir: 1 };
const money = (n) => (n == null ? "–" : "$" + n.toFixed(2));
const cls = (s) => s.replace(/[^A-Za-z]+/g, "-");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function groupKey(r) {
  const base = r.name.toLowerCase()
    .replace(/\d+(\.\d+)?\s*(x|ml|l|pk|pack)\b/g, " ")
    .replace(/[^a-z ]/g, " ").replace(/\s+/g, " ").trim();
  return `${r.flavour}|${r.pack_count}|${r.size_ml}`;
}

function sizeLabel(r) {
  const ml = r.size_ml ? (r.size_ml >= 1000 ? r.size_ml / 1000 + "L" : r.size_ml + "ml") : "";
  return r.pack_count > 1 ? `${r.pack_count} × ${ml}`.trim() : ml;
}

async function load() {
  try {
    const res = await fetch("data/prices.json?t=" + Date.now());
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    state.items = data.items;
    showStatus(data);
    fillFilters();
    render();
  } catch (e) {
    $("updated").textContent = "Couldn't load prices. Refresh the page, or check back later.";
  }
}

function showStatus(data) {
  if (!data.updated) {
    $("updated").textContent = "No prices yet. The first automatic update hasn't run.";
    return;
  }
  const when = new Date(data.updated);
  $("updated").textContent = "Prices as of " + when.toLocaleString("en-NZ", {
    weekday: "long", day: "numeric", month: "long", hour: "numeric", minute: "2-digit",
  });
  $("chains").innerHTML = Object.entries(data.chains).map(([name, c]) => {
    const stale = c.status === "stale";
    const note = stale ? ` – couldn't update${c.last_success ? ", last good " + esc(c.last_success) : ""}` : "";
    return `<li class="${stale ? "stale" : ""}"><span class="dot ${cls(name)}"></span>${esc(name)}${note}</li>`;
  }).join("");
}

function fillOptions(sel, values, fmt = (v) => v) {
  const keep = sel.value;
  sel.querySelectorAll("option:not(:first-child)").forEach((o) => o.remove());
  values.forEach((v) => sel.add(new Option(fmt(v), v)));
  sel.value = keep;
}

function fillFilters() {
  const uniq = (f) => [...new Set(state.items.map(f))].filter((v) => v !== "" && v != null);
  fillOptions($("chain"), uniq((r) => r.chain).sort());
  fillOptions($("flavour"), uniq((r) => r.flavour).sort());
  fillOptions($("store"), uniq((r) => r.store_name).sort());
}

function filtered() {
  const q = $("q").value.trim().toLowerCase();
  return state.items.filter((r) =>
    (!q || r.name.toLowerCase().includes(q)) &&
    (!$("chain").value || r.chain === $("chain").value) &&
    (!$("flavour").value || r.flavour === $("flavour").value) &&
    (!$("store").value || r.store_name === $("store").value) &&
    (!$("specials").checked || r.on_special) &&
    (!$("hideout").checked || r.available));
}

function sorted(rows) {
  const k = state.sortKey, d = state.sortDir;
  return rows.sort((a, b) => {
    if (a.available !== b.available) return a.available ? -1 : 1;
    const x = a[k], y = b[k];
    if (x == null && y == null) return 0;
    if (x == null) return 1;
    if (y == null) return -1;
    return (typeof x === "string" ? x.localeCompare(y) : x - y) * d;
  });
}

function render() {
  const rows = sorted(filtered());
  // Cheapest available price per can within each product group (across all chains/stores).
  const best = {};
  state.items.filter((r) => r.available && r.price_per_can != null).forEach((r) => {
    const g = groupKey(r);
    if (best[g] == null || r.price_per_can < best[g]) best[g] = r.price_per_can;
  });

  $("rows").innerHTML = rows.map((r) => {
    const isBest = r.available && r.price_per_can != null && r.price_per_can === best[groupKey(r)];
    const special = r.on_special;
    return `<tr class="${r.available ? "" : "out"}">
      <td><div class="prod"><div class="thumb">${r.image ? `<img src="${esc(r.image)}" alt="${esc(r.flavour)} Monster can" loading="lazy" referrerpolicy="no-referrer">` : ""}</div>
        <div><span class="pname" title="${esc(r.name)}">${esc(r.flavour)}</span><span class="psize">${esc(sizeLabel(r))}</span></div></div></td>
      <td><div class="store"><span class="dot ${cls(r.chain)}"></span><div>${esc(r.chain)}<small>${esc(r.store_name)}</small></div></div></td>
      <td class="num"><span class="price ${special ? "special" : ""}">${r.available ? money(r.price) : "Unavailable"}</span>
        ${r.was_price ? `<span class="was">${money(r.was_price)}</span>` : ""}
        ${r.promo_text ? `<span class="promo">${esc(r.promo_text)}</span>` : ""}</td>
      <td class="num ${isBest ? "best" : ""}">${money(r.price_per_can)}${isBest ? '<span class="best-tag">Cheapest</span>' : ""}</td>
      <td class="num">${money(r.price_per_100ml)}</td>
    </tr>`;
  }).join("");

  $("empty").hidden = rows.length > 0;
  $("count").textContent = `${rows.length} product${rows.length === 1 ? "" : "s"} shown`;
  document.querySelectorAll("th").forEach((th) => {
    const b = th.querySelector("button");
    th.removeAttribute("aria-sort");
    if (b && b.dataset.sort === state.sortKey) th.setAttribute("aria-sort", state.sortDir === 1 ? "ascending" : "descending");
  });
}

document.querySelectorAll("th button").forEach((b) => b.addEventListener("click", () => {
  const k = b.dataset.sort;
  state.sortDir = state.sortKey === k ? -state.sortDir : 1;
  state.sortKey = k;
  render();
}));
["q", "chain", "flavour", "store", "specials", "hideout"].forEach((id) =>
  $(id).addEventListener(id === "q" ? "input" : "change", render));

load();

// If a product photo fails to load, drop it and show the placeholder can.
document.addEventListener("error", (e) => {
  if (e.target.tagName === "IMG" && e.target.closest(".thumb")) e.target.remove();
}, true);
