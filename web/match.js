const DATA_PATH = "../output/summary.json";
const DETAIL_BASE_PATH = "../output/match_details";
const SIDES = ["Both", "CT", "T"];
let selectedPlayerSide = "Both";
let currentPlayers = [];
let currentMatch = null;
let currentNames = new Map();

function div(num, den) {
  return den ? num / den : 0;
}

function n(value, digits = 0) {
  const num = Number(value);
  if (!Number.isFinite(num)) return digits ? "0." + "0".repeat(digits) : "0";
  return num.toFixed(digits);
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[char]));
}

function ratingClass(value) {
  const num = Number(value || 0);
  if (num >= 1.1) return "good";
  if (num >= 0.95) return "okay";
  return "bad";
}

function resultCell(value) {
  const text = String(value || "");
  const cls = /win/i.test(text) ? "result-win" : /loss|lose/i.test(text) ? "result-loss" : "result-neutral";
  return `<span class="result-pill ${cls}">${esc(text)}</span>`;
}

function mapKey(mapName) {
  return String(mapName || "").replace(/^de_/, "").toLowerCase();
}

function mapBackground(key) {
  const available = new Set(["ancient", "anubis", "cache", "dust2", "inferno", "mirage", "nuke", "train"]);
  return available.has(key) ? `${key}.jpg` : "";
}

function mapBadge(mapName) {
  const clean = String(mapName || "").replace(/^de_/, "");
  const key = clean.toLowerCase();
  const short = {
    dust2: "D2", inferno: "INF", mirage: "MIR", nuke: "NUK", ancient: "ANC",
    anubis: "ANB", vertigo: "VTG", overpass: "OVP", cache: "CAC", train: "TRN"
  }[key] || clean.slice(0, 3).toUpperCase();
  const icon = ["ancient", "anubis", "cache", "dust2", "inferno", "mirage", "nuke", "train"].includes(key)
    ? `<img class="map-icon-img" src="./assets/maps/${key}.png" alt="${esc(clean)}">`
    : `<i class="map-icon map-${key}">${esc(short)}</i>`;
  return `<span class="map-cell map-cell-icon-only" title="${esc(clean)}">${icon}</span>`;
}

function teamSideScore(row, side) {
  const sideRow = row?.sides?.[side] || {};
  return Math.round(div(Number(sideRow.rounds_won || 0), 5));
}

function teamSideRounds(row, side) {
  const sideRow = row?.sides?.[side] || {};
  return Math.round(div(Number(sideRow.rounds || 0), 5));
}

function formatScore(row) {
  const total = `${String(row.our_score ?? 0).padStart(2, "0")}-${String(row.opponent_score ?? 0).padStart(2, "0")}`;
  const ct = `${String(teamSideScore(row, "CT")).padStart(2, "0")}-${String(Math.max(0, teamSideRounds(row, "CT") - teamSideScore(row, "CT"))).padStart(2, "0")}`;
  const t = `${String(teamSideScore(row, "T")).padStart(2, "0")}-${String(Math.max(0, teamSideRounds(row, "T") - teamSideScore(row, "T"))).padStart(2, "0")}`;
  return `${total} (<span class="ct">${ct}</span>, <span class="t">${t}</span>)`;
}

function playerNameMap(players) {
  return new Map(players.map(row => [String(row.steam64 || ""), row.player]));
}

function namesFor(steam64s, names) {
  const list = (steam64s || []).map(id => names.get(String(id)) || String(id)).filter(Boolean);
  return list.length ? list.join(", ") : "Unknown";
}

function playerLinksFor(steam64s, names) {
  const list = (steam64s || []).map(id => {
    const name = names.get(String(id)) || String(id);
    const href = `./index.html?view=players&player=${encodeURIComponent(name)}`;
    return `<a href="${href}" target="_blank" rel="noreferrer">${esc(name)}</a>`;
  }).filter(Boolean);
  return list.length ? list.join("") : "Unknown";
}

function aliveLinksFor(steam64s, names) {
  const list = (steam64s || []).map(id => {
    const key = String(id);
    const name = names.get(key);
    if (!name) return `<span class="pug-teammate-name">PUG Teammate</span>`;
    const href = `./index.html?view=players&player=${encodeURIComponent(name)}`;
    return `<a href="${href}" target="_blank" rel="noreferrer">${esc(name)}</a>`;
  }).filter(Boolean);
  return list.length ? list.join("") : "Unknown";
}

function renderHero(match) {
  const bg = mapBackground(mapKey(match.map_name)) || "dust2.jpg";
  const key = mapKey(match.map_name);
  document.getElementById("matchHero").style.setProperty("--map-bg", `url('./assets/map-backgrounds/${bg}')`);
  document.getElementById("matchHero").innerHTML = `
    <div>
      <span class="match-kicker">${esc(match.date)} · ${esc(match.roster_type)}</span>
      <h2>${esc(match.map_name)}</h2>
      <div class="match-score mono-stat">${formatScore(match)}</div>
    </div>
    <img class="match-map-icon" src="./assets/maps/${key}.png" alt="">
    <div class="match-actions">
      ${resultCell(match.match_result)}
      ${match.file_url ? `<a class="demo-link" href="${esc(match.file_url)}" target="_blank" rel="noreferrer">Demo download</a>` : ""}
    </div>`;
}

const playerColumns = [
  ["player", "Player"],
  ["rating", "Rating"],
  ["kast", "KAST"],
  ["rws", "RWS"],
  ["kda", "K-D-A"],
  ["clutch", "Clutch"],
  ["opening_kd", "Opening K/D"],
  ["multi_kill_rounds", "Multi-kill"],
  ["flash_bundle", "Flash throws <span class=\"th-note\">(Opp/Team)</span>"],
  ["utility_damage", "Util dmg <span class=\"th-note\">(IB/HE)</span>"],
];

function ratingProxy(row) {
  const rounds = Number(row.rounds || 0);
  if (!rounds) return 0;
  const kpr = div(row.kills, rounds);
  const dpr = div(row.deaths, rounds);
  const adr = div(row.damage, rounds);
  const kast = div(row.kast_rounds, rounds);
  const multi = div(row.multi_kill_rounds, rounds);
  const swing = 0.55 * div(Number(row.opening_kills || 0) - Number(row.opening_deaths || 0), rounds)
    + 0.25 * div(row.clutch_wins, rounds)
    + 0.20 * div(row.trade_kills, rounds);
  return Math.max(0, 0.18 * div(kpr, 0.68) + 0.18 * div(adr, 75) + 0.16 * div(1 - dpr, 0.34) + 0.16 * div(kast, 0.73) + 0.16 * div(multi, 0.12) + 0.16 * (1 + swing * 3));
}

function computePlayer(row) {
  const rounds = Number(row.rounds || 0);
  return {
    ...row,
    rating: ratingProxy(row),
    kast: 100 * div(row.kast_rounds, rounds),
    rws: Math.max(0, 10 + 100 * (0.55 * div(Number(row.opening_kills || 0) - Number(row.opening_deaths || 0), rounds) + 0.25 * div(row.clutch_wins, rounds) + 0.20 * div(row.trade_kills, rounds)) / 2.0)
  };
}

function sidePlayer(row, side) {
  if (side === "Both") return computePlayer(row);
  return computePlayer({
    ...row,
    ...(row.sides?.[side] || {}),
    player: row.player,
    steam64: row.steam64,
    sides: row.sides
  });
}

function renderMatchSideTabs() {
  const tabs = document.getElementById("matchSideTabs");
  tabs.innerHTML = SIDES.map(side => `
    <button class="side-tab ${selectedPlayerSide === side ? "active" : ""} ${side.toLowerCase()}" data-side="${side}">${side}</button>
  `).join("");
  for (const button of tabs.querySelectorAll(".side-tab")) {
    button.addEventListener("click", () => {
      selectedPlayerSide = button.dataset.side;
      renderPlayers(currentPlayers);
    });
  }
}

function playerValue(row, key) {
  if (key === "rating") return `<span class="rating-value rating-${ratingClass(row.rating)}">${n(row.rating, 2)}</span>`;
  if (key === "kast") return `${n(row.kast, 1)}%`;
  if (key === "rws") return n(row.rws, 1);
  if (key === "kda") return `${n(row.kills, 0)}-${n(row.deaths, 0)}-${n(row.assists, 0)}`;
  if (key === "clutch") return `${n(row.clutch_wins, 0)}-${n(row.clutch_losses, 0)} (${n(row.clutch_broad_wins, 0)}-${n(row.clutch_broad_losses, 0)})`;
  if (key === "opening_kd") return `${n(row.opening_kills, 0)}/${n(row.opening_deaths, 0)}`;
  if (key === "flash_bundle") return `${n(row.flashes_thrown, 0)} <span class="muted-cell">(${n(row.opponent_flashed_count, 0)}/${n(row.teammate_flashed_count, 0)})</span>`;
  if (key === "utility_damage") return `${n(row.utility_damage, 0)} <span class="muted-cell">(<b class="util-fire-dmg">${n(row.fire_damage, 0)}</b>/<b class="util-he-dmg">${n(row.he_damage, 0)}</b>)</span>`;
  return n(row[key], 0);
}

function renderPlayers(rows) {
  renderMatchSideTabs();
  const table = document.getElementById("matchPlayersTable");
  table.innerHTML = `<thead><tr>${playerColumns.map(([, label]) => `<th>${label}</th>`).join("")}</tr></thead>`;
  const body = document.createElement("tbody");
  const displayRows = rows
    .slice()
    .sort((a, b) => computePlayer(b).rating - computePlayer(a).rating)
    .map(row => sidePlayer(row, selectedPlayerSide));
  for (const row of displayRows) {
    const tr = document.createElement("tr");
    for (const [key] of playerColumns) {
      const td = document.createElement("td");
      if (key === "player") td.textContent = row.player;
      else td.innerHTML = playerValue(row, key);
      tr.appendChild(td);
    }
    body.appendChild(tr);
  }
  table.appendChild(body);
}

function matchScore(match) {
  return `${String(match.our_score ?? 0).padStart(2, "0")}-${String(match.opponent_score ?? 0).padStart(2, "0")}`;
}

function tag(label, tone) {
  return `<span class="round-tag ${tone}">${esc(label)}</span>`;
}

function buyTypeLabel(row) {
  const own = row.buy?.type || "No Buy Data";
  const opponent = row.opponent_buy?.type || "";
  if (opponent === "Eco") return "Anti-Eco";
  if (opponent === "Force Buy") return "Anti-Force Buy";
  return own;
}

const utilityIcons = [
  ["smoke", "Smoke", "smoke.png"],
  ["flash", "Flash", "flash.png"],
  ["he", "HE", "he.png"],
  ["fire", "Fire", "fire.png"],
];

function utilityCounts(row) {
  const utility = row.buy?.utility || {};
  return utilityIcons.map(([key, label, file]) => {
    const count = Number(utility[key] || 0);
    if (!count) return "";
    return `
      <span class="utility-count utility-${key}" title="${label}">
        <img src="./assets/utility/${file}" alt="${label}">
        <b>x${count}</b>
      </span>`;
  }).join("");
}

function roundCount(match) {
  return Number(match.rounds || 0) || Number(match.our_score || 0) + Number(match.opponent_score || 0);
}

function roundDetailRows(match) {
  const byRound = new Map();
  for (const item of match.round_details || []) {
    const round = Number(item.round || 0);
    if (!round || byRound.has(round)) continue;
    byRound.set(round, item);
  }
  const total = Math.max(roundCount(match), ...byRound.keys(), 0);
  return Array.from({ length: total }, (_, index) => {
    const round = index + 1;
    return { round, ...(byRound.get(round) || {}) };
  });
}

function failureIndexes(match) {
  const fiveVFour = new Set();
  const clutchLost = new Map();
  const clutchWon = new Map();
  for (const item of match.advantage_failures || []) {
    if (item.state === "5v4") fiveVFour.add(Number(item.round));
  }
  for (const item of match.clutch_failures || []) {
    const round = Number(item.round);
    if (!round) continue;
    const states = clutchLost.get(round) || [];
    states.push(item);
    clutchLost.set(round, states);
  }
  for (const item of match.clutch_rounds || []) {
    const round = Number(item.round);
    if (!round || item.won !== true) continue;
    const states = clutchWon.get(round) || [];
    states.push(item);
    clutchWon.set(round, states);
  }
  return { fiveVFour, clutchLost, clutchWon };
}

function uniqueStates(items) {
  return Array.from(new Set((items || []).map(item => String(item.state || "")).filter(Boolean)));
}

function roundTags(row, indexes) {
  const tags = [];
  const round = Number(row.round);
  const won = row.won === true;
  const alive = Number(row.alive_count || 0);
  const start = Number(row.start_count || 0);
  if (indexes.fiveVFour.has(round)) tags.push(tag("5v4 Lost", "danger"));
  for (const state of uniqueStates(indexes.clutchLost.get(round))) {
    tags.push(tag(`${state} Clutch Lost`, "danger"));
  }
  for (const state of uniqueStates(indexes.clutchWon.get(round))) {
    tags.push(tag(`${state} Clutch Won`, "success"));
  }
  if (won && alive === 1) tags.push(tag("Close Win", "warning"));
  if (won && start >= 5 && alive >= start) tags.push(tag("Perfect", "perfect"));
  return tags.join("");
}

function roundHighlights(row, names) {
  const tags = [];
  for (const item of row.highlights || []) {
    const kills = Number(item.kills || 0);
    if (kills >= 4) {
      const name = names.get(String(item.steam64)) || String(item.steam64 || "Unknown");
      tags.push(tag(`${name} ${kills}K`, kills >= 5 ? "ace" : "highlight"));
    }
  }
  return tags.join("");
}

function clutchLostAlive(round, indexes, names) {
  const items = indexes.clutchLost.get(Number(round)) || [];
  const alive = Array.from(new Set(items.flatMap(item => item.alive_steam64s || [])));
  if (!alive.length) return "";
  return `<span class="round-alive">Alive: <b>${aliveLinksFor(alive, names)}</b></span>`;
}

function renderRoundList(match, names) {
  const target = document.getElementById("matchRoundList");
  const rows = roundDetailRows(match);
  const indexes = failureIndexes(match);
  if (!rows.length) {
    target.innerHTML = `<div class="empty-state">No round detail available.</div>`;
    document.getElementById("roundDetailSummary").textContent = "";
    return;
  }
  const fiveVFourCount = indexes.fiveVFour.size;
  const clutchLostCount = Array.from(indexes.clutchLost.values()).reduce((sum, states) => sum + uniqueStates(states).length, 0);
  const clutchWonCount = Array.from(indexes.clutchWon.values()).reduce((sum, states) => sum + uniqueStates(states).length, 0);
  const highlightCount = rows.reduce((sum, row) => sum + (row.highlights || []).filter(item => Number(item.kills || 0) >= 4).length, 0);
  document.getElementById("roundDetailSummary").textContent = `${rows.length} rounds · ${fiveVFourCount} 5v4 lost · ${clutchLostCount} clutch lost · ${clutchWonCount} clutch won · ${highlightCount} highlights`;
  target.innerHTML = rows.map(row => {
    const won = row.won === true;
    const lost = row.won === false;
    const status = won ? "Win" : lost ? "Lose" : "Unknown";
    const side = String(row.side || "").toLowerCase();
    const clutchAlive = clutchLostAlive(row.round, indexes, names);
    const tagHtml = roundTags(row, indexes);
    const highlightTags = roundHighlights(row, names);
    const hasTags = Boolean(tagHtml || highlightTags);
    return `
      <div class="round-row ${won ? "round-win" : lost ? "round-loss" : "round-unknown"} ${clutchAlive ? "has-alive" : ""} ${hasTags ? "has-tags" : "no-tags"}">
        <div class="round-no ${side}">
          <span>Round</span>
          <b>${Number(row.round || 0)}</b>
        </div>
        <div class="round-result">
          <b>${status}</b>
        </div>
        <div class="round-buy-cell">
          <b>${esc(buyTypeLabel(row))}</b>
        </div>
        <div class="round-utility-cell">
          <div class="round-utility">${utilityCounts(row) || `<em>None</em>`}</div>
        </div>
        <div class="round-tags">
          ${tagHtml}
          ${highlightTags}
        </div>
        <div class="round-alive-slot">${clutchAlive}</div>
      </div>`;
  }).join("");
}

async function load() {
  const matchId = new URLSearchParams(window.location.search).get("match");
  const response = await fetch(DATA_PATH, { cache: "no-store" });
  const summary = await response.json();
  const indexMatch = (summary.team?.matches || []).find(row => row.match_id === matchId);
  if (!indexMatch) throw new Error(`Match not found: ${matchId}`);
  const detailResponse = await fetch(`${DETAIL_BASE_PATH}/${encodeURIComponent(matchId)}.json`, { cache: "no-store" });
  if (!detailResponse.ok) throw new Error(`Match detail not found: ${matchId}`);
  const detail = await detailResponse.json();
  const match = detail.match || indexMatch;
  if (!match) throw new Error(`Match not found: ${matchId}`);
  const players = detail.players || (summary.player_matches || []).filter(row => row.match_id === matchId);
  const names = playerNameMap(players);
  currentMatch = match;
  currentPlayers = players;
  currentNames = names;
  renderHero(match);
  renderPlayers(players);
  renderRoundList(match, names);
}

load().catch(error => {
  document.querySelector("main").innerHTML = `<section class="panel"><h2>${esc(error.message)}</h2></section>`;
});
