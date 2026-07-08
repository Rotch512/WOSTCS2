let summary = null;
let rosterRows = [];
let selectedPrimarySide = "Both";
const radarSides = { Both: true, CT: true, T: true };

const DATA_PATH = "../output/summary.json";
const PLAYER_SUMMARY_PATH = "../output/player_summary.json";
const PLAYER_MATCHES_PATH = "../output/player_matches.json";
const ROSTER_PATH = "../output/sheets/roster.csv";
const SIDES = ["Both", "CT", "T"];
const COUNT_FIELDS = [
  "rounds", "rounds_won", "kills", "kills_in_round_wins", "deaths", "assists", "damage", "damage_in_round_wins",
  "opening_kills", "opening_kill_round_wins", "opening_deaths", "trade_kills", "traded_deaths", "opening_deaths_traded",
  "flash_assists", "flashes_thrown", "opponent_flashed_time", "utility_damage", "he_damage", "fire_damage", "utility_kills", "multi_kill_rounds", "clutch_wins", "kast_rounds",
  "headshot_kills", "survived_rounds", "rounds_with_kill", "support_rounds", "assisted_kills", "sniper_kills",
  "sniper_multi_kill_rounds", "sniper_opening_kills", "pistol_rounds", "pistol_kills", "pistol_deaths",
  "pistol_assists", "pistol_damage", "pistol_kast_rounds"
];
const playerColumns = ["player", "roster_status", "matches", "rounds", "rating", "firepower", "entrying", "trading", "opening", "utility", "kd", "adr", "kast", "kpr", "dpr"];
const matchColumns = ["date", "map_name", "match_result", "roster_type", "roster_status", "kills", "deaths", "assists", "adr", "kast", "rating"];
const teamMatchColumns = ["date", "map_name", "score_split", "round_win_rate", "match_result", "roster_type", "opening_diff", "clutch_record"];
const statusRank = { "Starter": 0, "Stand-in": 1, "Benched": 2, "Left": 3, "Change": 99 };
const clutchFailureTypes = ["1v1", "2v1", "3v1", "4v1", "5v1", "4v2", "5v2", "5v3"];
let selectedFailureType = "1v1";

function div(num, den) {
  return den ? num / den : 0;
}

function clamp(value, low = 0, high = 100) {
  return Math.max(low, Math.min(high, value));
}

function score(value, average, elite, reverse = false) {
  const raw = reverse
    ? 50 + ((average - value) / Math.max(average - elite, 0.001)) * 50
    : 50 + ((value - average) / Math.max(elite - average, 0.001)) * 50;
  return Math.round(clamp(raw));
}

function grade(value, average, elite, reverse = false) {
  const s = score(value, average, elite, reverse);
  if (s >= 82) return "Elite";
  if (s >= 66) return "Good";
  if (s >= 48) return "Okay";
  if (s >= 32) return "Below avg.";
  return "Poor";
}

function gradeClass(name) {
  return String(name || "").toLowerCase().replace(/[^a-z]+/g, "-").replace(/^-|-$/g, "");
}

function n(value, digits = 0) {
  const num = Number(value);
  if (!Number.isFinite(num)) return digits ? "0." + "0".repeat(digits) : "0";
  return num.toFixed(digits);
}

function unique(values) {
  return [...new Set(values.filter(Boolean))].sort();
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

function fillSelect(id, values, allLabel = "All") {
  const select = document.getElementById(id);
  const current = select.value;
  select.innerHTML = "";
  select.appendChild(new Option(allLabel, ""));
  for (const value of values) select.appendChild(new Option(value, value));
  select.value = values.includes(current) ? current : "";
}

function fillPlayerSelect(values) {
  const select = document.getElementById("playerFilter");
  const current = select.value;
  select.innerHTML = "";
  for (const value of values) select.appendChild(new Option(value, value));
  select.value = values.includes(current) ? current : values[0] || "";
}

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  if (!lines.length) return [];
  const readLine = line => {
    const cells = [];
    let current = "";
    let quoted = false;
    for (let index = 0; index < line.length; index += 1) {
      const char = line[index];
      const next = line[index + 1];
      if (char === '"' && quoted && next === '"') {
        current += char;
        index += 1;
      } else if (char === '"') {
        quoted = !quoted;
      } else if (char === "," && !quoted) {
        cells.push(current);
        current = "";
      } else {
        current += char;
      }
    }
    cells.push(current);
    return cells;
  };
  const headers = readLine(lines[0]);
  return lines.slice(1).map(line => {
    const cells = readLine(line);
    return Object.fromEntries(headers.map((header, index) => [header, cells[index] || ""]));
  });
}

async function loadRoster() {
  try {
    const response = await fetch(ROSTER_PATH, { cache: "no-store" });
    if (!response.ok) return [];
    return parseCsv(await response.text());
  } catch {
    return [];
  }
}

async function loadData() {
  const response = await fetch(DATA_PATH, { cache: "no-store" });
  if (!response.ok) throw new Error(`Unable to load ${DATA_PATH}`);
  const baseSummary = await response.json();
  const [playerSummaryResponse, playerMatchesResponse] = await Promise.all([
    fetch(PLAYER_SUMMARY_PATH, { cache: "no-store" }),
    fetch(PLAYER_MATCHES_PATH, { cache: "no-store" })
  ]);
  if (!playerSummaryResponse.ok) throw new Error(`Unable to load ${PLAYER_SUMMARY_PATH}`);
  if (!playerMatchesResponse.ok) throw new Error(`Unable to load ${PLAYER_MATCHES_PATH}`);
  const playerSummary = await playerSummaryResponse.json();
  const playerMatches = await playerMatchesResponse.json();
  summary = {
    ...baseSummary,
    ...playerSummary,
    player_matches: playerMatches
  };
  rosterRows = await loadRoster();
  hydrateFilters();
  applyUrlParams();
  render();
}

function applyUrlParams() {
  const params = new URLSearchParams(window.location.search);
  const player = params.get("player");
  if (player) {
    const select = document.getElementById("playerFilter");
    if ([...select.options].some(option => option.value === player)) {
      select.value = player;
    }
  }
  if (params.get("view") === "players" || player) {
    setView("playersView");
  } else if (params.get("view") === "team") {
    setView("teamView");
  }
}

function hydrateFilters() {
  const matches = summary.player_matches || [];
  fillPlayerSelect(rosterOrder().filter(player => matches.some(row => row.player === player)));
  fillSelect("quarterFilter", unique(matches.map(row => row.quarter)), "All Quarters");
  fillSelect("mapFilter", unique(matches.map(row => row.map_name)), "All Maps");
  fillSelect("rosterFilter", unique(matches.map(row => row.roster_type)), "All Rosters");
  fillSelect("resultFilter", unique(matches.map(row => row.match_result)), "All Results");
}

function rosterOrder() {
  const seen = new Set();
  const players = [];
  for (const row of rosterRows) {
    const player = row.Player || row.player;
    if (player && !seen.has(player)) {
      seen.add(player);
      players.push(player);
    }
  }
  for (const row of summary?.player_matches || []) {
    if (!seen.has(row.player)) {
      seen.add(row.player);
      players.push(row.player);
    }
  }
  return players;
}

function latestRosterStatus(player) {
  const rows = rosterRows.filter(row => (row.Player || row.player) === player && !/^change$/i.test(row.Status || row.status));
  if (!rows.length) return "";
  return rows[rows.length - 1].Status || rows[rows.length - 1].status || "";
}

function dateValue(value) {
  if (!value || String(value).toLowerCase() === "present") return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function normalizedRosterRows() {
  return rosterRows.map((row, index) => {
    const player = row.Player || row.player || "";
    const start = row.Start || row.start || "";
    const end = row.End || row.end || "";
    const status = row.Status || row.status || "";
    const steam64 = row.SteamID || row.steam64 || row.steam_id || "";
    return {
      index,
      player,
      start,
      end,
      status,
      steam64,
      startDate: dateValue(start),
      endDate: dateValue(end)
    };
  }).filter(row => row.player && row.start && row.status);
}

function isCurrentRosterRow(row) {
  const today = new Date();
  if (row.startDate && row.startDate > today) return false;
  if (row.endDate && row.endDate <= today) return false;
  return !/^(left|change)$/i.test(row.status);
}

function currentRosterRows() {
  return normalizedRosterRows()
    .filter(isCurrentRosterRow)
    .sort((a, b) => (statusRank[a.status] ?? 99) - (statusRank[b.status] ?? 99) || a.player.localeCompare(b.player));
}

function currentStarters() {
  const starters = currentRosterRows().filter(row => /^starter$/i.test(row.status));
  return starters.length ? starters : currentRosterRows().slice(0, 5);
}

function playerSummaryByName() {
  return new Map((summary?.players || []).map(player => [player.player, player]));
}

function filteredMatches(includePlayer = true) {
  const player = document.getElementById("playerFilter").value;
  const quarter = document.getElementById("quarterFilter").value;
  const map = document.getElementById("mapFilter").value;
  const roster = document.getElementById("rosterFilter").value;
  const result = document.getElementById("resultFilter").value;
  const start = document.getElementById("startDate").value;
  const end = document.getElementById("endDate").value;
  return (summary.player_matches || []).filter(row => {
    if (includePlayer && row.player !== player) return false;
    if (quarter && row.quarter !== quarter) return false;
    if (map && row.map_name !== map) return false;
    if (roster && row.roster_type !== roster) return false;
    if (result && row.match_result !== result) return false;
    if (start && row.date < start) return false;
    if (end && row.date > end) return false;
    return true;
  });
}

function emptyCounts() {
  return Object.fromEntries(COUNT_FIELDS.map(field => [field, 0]));
}

function emptyAgg(key = {}) {
  return {
    ...key,
    matches: 0,
    ...emptyCounts(),
    sides: { Both: null, CT: emptyCounts(), T: emptyCounts() }
  };
}

function addCounts(target, source) {
  for (const field of COUNT_FIELDS) target[field] += Number(source?.[field] || 0);
}

function addAgg(acc, row) {
  acc.matches += Number(row.matches || 1);
  addCounts(acc, row);
  for (const side of ["CT", "T"]) addCounts(acc.sides[side], row.sides?.[side] || {});
}

function ratingProxy(row) {
  const rounds = Number(row.rounds || 0);
  if (!rounds) return 0;
  const kpr = div(row.kills, rounds);
  const dpr = div(row.deaths, rounds);
  const adr = div(row.damage, rounds);
  const kast = div(row.kast_rounds, rounds);
  const multi = div(row.multi_kill_rounds, rounds);
  const swing = 0.55 * div(row.opening_kills - row.opening_deaths, rounds) + 0.25 * div(row.clutch_wins, rounds) + 0.20 * div(row.trade_kills, rounds);
  return Math.max(0, 0.18 * div(kpr, 0.68) + 0.18 * div(adr, 75) + 0.16 * div(1 - dpr, 0.34) + 0.16 * div(kast, 0.73) + 0.16 * div(multi, 0.12) + 0.16 * (1 + swing * 3));
}

function compute(row) {
  const rounds = Number(row.rounds || 0);
  const kills = Number(row.kills || 0);
  const deaths = Number(row.deaths || 0);
  const assists = Number(row.assists || 0);
  const openingAttempts = Number(row.opening_kills || 0) + Number(row.opening_deaths || 0);
  row.kd = div(kills, deaths);
  row.kpr = div(kills, rounds);
  row.dpr = div(deaths, rounds);
  row.apr = div(assists, rounds);
  row.adr = div(row.damage, rounds);
  row.kast = 100 * div(row.kast_rounds, rounds);
  row.survival_rate = 100 * div(row.survived_rounds, rounds);
  row.headshot_rate = 100 * div(row.headshot_kills, kills);
  row.opening_duel_diff = Number(row.opening_kills || 0) - Number(row.opening_deaths || 0);
  row.opening_kills_per_round = div(row.opening_kills, rounds);
  row.opening_deaths_per_round = div(row.opening_deaths, rounds);
  row.opening_attempts = 100 * div(openingAttempts, rounds);
  row.opening_success = 100 * div(row.opening_kills, openingAttempts);
  row.win_after_opening_kill = 100 * div(row.opening_kill_round_wins, row.opening_kills);
  row.multi_kill_rate = 100 * div(row.multi_kill_rounds, rounds);
  row.rounds_with_kill_percentage = 100 * div(row.rounds_with_kill, rounds);
  row.kills_per_round_win = div(row.kills_in_round_wins, row.rounds_won);
  row.damage_per_round_win = div(row.damage_in_round_wins, row.rounds_won);
  row.flash_assists_per_round = div(row.flash_assists, rounds);
  row.utility_damage_per_round = div(row.utility_damage, rounds);
  row.utility_kills_per_100_rounds = 100 * div(row.utility_kills, rounds);
  row.trade_kills_per_round = div(row.trade_kills, rounds);
  row.trade_kills_percentage = 100 * div(row.trade_kills, kills);
  row.traded_deaths_per_round = div(row.traded_deaths, rounds);
  row.traded_deaths_percentage = 100 * div(row.traded_deaths, deaths);
  row.opening_deaths_traded_percentage = 100 * div(row.opening_deaths_traded, row.opening_deaths);
  row.saved_by_teammate_per_round = row.traded_deaths_per_round;
  row.saved_teammate_per_round = row.trade_kills_per_round;
  row.assisted_kills_percentage = 100 * div(row.assisted_kills, kills);
  row.support_rounds_percentage = 100 * div(row.support_rounds, rounds);
  row.damage_per_kill = div(row.damage, kills);
  row.attacks_per_round = div(openingAttempts + row.rounds_with_kill, rounds);
  row.sniper_kills_per_round = div(row.sniper_kills, rounds);
  row.sniper_kills_percentage = 100 * div(row.sniper_kills, kills);
  row.rounds_with_sniper_kills_percentage = 100 * div(row.sniper_kills, rounds);
  row.sniper_multi_kill_rounds_rate = div(row.sniper_multi_kill_rounds, rounds);
  row.sniper_opening_kills_per_round = div(row.sniper_opening_kills, rounds);
  row.pistol_rating = ratingProxy({ ...row, rounds: row.pistol_rounds, kills: row.pistol_kills, deaths: row.pistol_deaths, assists: row.pistol_assists, damage: row.pistol_damage, kast_rounds: row.pistol_kast_rounds, multi_kill_rounds: 0, opening_kills: 0, opening_deaths: 0, trade_kills: 0 });
  row.clutch_points_per_round = div(row.clutch_wins, rounds);
  row.last_alive_percentage = rounds !== row.rounds_won ? 100 * div(row.survived_rounds, Math.max(rounds - row.rounds_won, 1)) : 0;
  row.one_on_one_win_percentage = 0;
  row.time_alive_per_round_seconds = 115 * div(row.survived_rounds, rounds) + 35 * div(deaths, rounds);
  row.saves_per_round_loss = rounds !== row.rounds_won ? 100 * div(row.survived_rounds, Math.max(rounds - row.rounds_won, 1)) : 0;
  row.flashes_thrown_per_round = div(row.flashes_thrown, rounds);
  row.time_opponent_flashed_per_round = div(row.opponent_flashed_time, rounds);
  row.round_swing = 100 * (0.55 * div(row.opening_duel_diff, rounds) + 0.25 * div(row.clutch_wins, rounds) + 0.20 * div(row.trade_kills, rounds));
  row.rws = Math.max(0, 10 + row.round_swing / 2.0);
  row.rating = ratingProxy(row);
  row.impact_rating = Math.max(0, 1 + div(row.opening_duel_diff, rounds) * 2.2 + div(row.multi_kill_rounds, rounds) * 1.6 + div(row.trade_kills, rounds) * 0.9);
  row.firepower = Math.round(clamp(0.38 * score(row.kpr, 0.68, 0.95) + 0.30 * score(row.adr, 75, 100) + 0.20 * score(row.multi_kill_rate, 12, 25) + 0.12 * score(row.rounds_with_kill_percentage, 43, 58)));
  row.entrying = Math.round(clamp(0.35 * score(row.traded_deaths_per_round, 0.08, 0.18) + 0.30 * score(row.traded_deaths_percentage, 15, 28) + 0.20 * score(row.saved_by_teammate_per_round, 0.08, 0.18) + 0.15 * score(row.opening_deaths_traded_percentage, 15, 35)));
  row.trading = Math.round(clamp(0.38 * score(row.trade_kills_per_round, 0.10, 0.22) + 0.30 * score(row.trade_kills_percentage, 12, 25) + 0.17 * score(row.saved_teammate_per_round, 0.10, 0.22) + 0.15 * score(row.assisted_kills_percentage, 12, 28)));
  row.opening = Math.round(clamp(0.35 * score(row.opening_kills_per_round, 0.09, 0.18) + 0.25 * score(row.opening_attempts, 18, 32) + 0.25 * score(row.opening_success, 48, 62) + 0.15 * score(row.opening_deaths_per_round, 0.13, 0.07, true)));
  row.clutching = Math.round(clamp(0.45 * score(row.clutch_points_per_round, 0.01, 0.05) + 0.25 * score(row.last_alive_percentage, 6, 14) + 0.30 * score(row.time_alive_per_round_seconds, 60, 80)));
  row.sniping = Math.round(clamp(0.38 * score(row.sniper_kills_per_round, 0.03, 0.28) + 0.24 * score(row.sniper_kills_percentage, 3, 28) + 0.18 * score(row.rounds_with_sniper_kills_percentage, 2, 18) + 0.10 * score(row.sniper_multi_kill_rounds_rate, 0.002, 0.04) + 0.10 * score(row.sniper_opening_kills_per_round, 0.002, 0.055)));
  row.utility = Math.round(clamp(0.45 * score(row.utility_damage_per_round, 3.5, 8.5) + 0.20 * score(row.utility_kills_per_100_rounds, 0.3, 1.2) + 0.20 * score(row.flash_assists_per_round, 0.015, 0.08) + 0.10 * score(row.flashes_thrown_per_round, 0.35, 0.8) + 0.05 * score(row.time_opponent_flashed_per_round, 1.5, 3.5)));
  return row;
}

function withSides(row) {
  const both = compute(row);
  const sides = { Both: both };
  for (const side of ["CT", "T"]) {
    sides[side] = compute({ ...row, ...row.sides[side], player: row.player, matches: row.matches });
  }
  both.sides = sides;
  return both;
}

function aggregate(rows, keyName = "player") {
  const grouped = new Map();
  for (const row of rows) {
    const key = row[keyName];
    if (!grouped.has(key)) grouped.set(key, emptyAgg({ [keyName]: key }));
    addAgg(grouped.get(key), row);
  }
  return [...grouped.values()].map(withSides);
}

function fmtMetric(row, metric, spec = {}) {
  const value = Number(row?.[metric] || 0);
  if (spec.integer) return n(value, 0);
  if (spec.signed) return `${value >= 0 ? "+" : ""}${n(value, spec.digits ?? 2)}${spec.percent ? "%" : ""}`;
  if (spec.percent) return `${n(value, spec.digits ?? 1)}%`;
  if (spec.score) return `${Math.round(value)}/100`;
  if (spec.time) {
    const total = Math.round(value);
    return `${Math.floor(total / 60)}m ${String(total % 60)}s`;
  }
  return n(value, spec.digits ?? 2);
}

function signed(value, digits = 2, suffix = "") {
  const num = Number(value || 0);
  return `${num >= 0 ? "+" : ""}${n(num, digits)}${suffix}`;
}

function ratingClass(value) {
  const num = Number(value || 0);
  if (num >= 1.1) return "good";
  if (num >= 0.95) return "okay";
  return "bad";
}

function renderPlayerCard(player) {
  const status = latestRosterStatus(player?.player || "");
  const ratingGrade = grade(player?.rating || 0, 1.0, 1.25);
  const ctGrade = grade(player?.sides?.CT?.rating || 0, 1.0, 1.25);
  const tGrade = grade(player?.sides?.T?.rating || 0, 1.0, 1.25);
  document.getElementById("playerCard").innerHTML = `
    <div class="player-topline">
      <div class="player-name">${player?.player || "No Data"}</div>
      <span class="status-badge status-${gradeClass(status)}">${status || "Unknown"}</span>
    </div>
    <div class="rating-strip">
      <div><span>Rating 3.0</span><strong class="rating-${ratingClass(player?.rating)}">${n(player?.rating, 2)}</strong><em class="grade-${gradeClass(ratingGrade)}">${ratingGrade}</em></div>
      <div><span>CT Rating</span><strong class="ct">${n(player?.sides?.CT?.rating, 2)}</strong><em class="grade-${gradeClass(ctGrade)}">${ctGrade}</em></div>
      <div><span>T Rating</span><strong class="t">${n(player?.sides?.T?.rating, 2)}</strong><em class="grade-${gradeClass(tGrade)}">${tGrade}</em></div>
    </div>
    <div class="player-sub">Maps <strong>${player?.matches || 0}</strong> · Rounds <strong>${player?.rounds || 0}</strong></div>
    <div class="player-stats">
      <span>K/D <b>${n(player?.kd, 2)}</b></span>
      <span>ADR <b>${n(player?.adr, 1)}</b></span>
      <span>KAST <b>${n(player?.kast, 1)}%</b></span>
      <span>Round swing <b>${signed(player?.round_swing, 2, "%")}</b></span>
      <span>RWS <b>${n(player?.rws, 1)}</b></span>
      <span>Impact <b>${n(player?.impact_rating, 2)}</b></span>
    </div>`;
}

const primarySpecs = [
  { label: "DPR", field: "dpr", digits: 2, min: 0.45, max: 0.95, avg: 0.68, elite: 0.55, reverse: true },
  { label: "KAST", field: "kast", digits: 1, percent: true, min: 55, max: 90, avg: 73, elite: 80 },
  { label: "MULTIKILL", field: "multi_kill_rate", digits: 1, percent: true, min: 3, max: 32, avg: 12, elite: 25 },
  { label: "ADR", field: "adr", digits: 1, min: 45, max: 115, avg: 75, elite: 100 },
  { label: "KPR", field: "kpr", digits: 2, min: 0.4, max: 1.05, avg: 0.68, elite: 0.95 }
];

function markerLeft(value, spec) {
  const ratio = spec.reverse
    ? (spec.max - value) / (spec.max - spec.min)
    : (value - spec.min) / (spec.max - spec.min);
  return clamp(ratio * 100);
}

function renderPrimaryMetrics(player) {
  document.getElementById("sideTabs").innerHTML = SIDES.map(side => `
    <button class="side-tab ${selectedPrimarySide === side ? "active" : ""} ${side.toLowerCase()}" data-side="${side}">${side}</button>
  `).join("");
  for (const button of document.querySelectorAll("#sideTabs .side-tab")) {
    button.addEventListener("click", () => {
      selectedPrimarySide = button.dataset.side;
      render();
    });
  }
  const source = player.sides[selectedPrimarySide] || player;
  document.getElementById("primaryMetrics").innerHTML = primarySpecs.map(spec => {
    const value = Number(source[spec.field] || 0);
    const gradeText = grade(value, spec.avg, spec.elite, spec.reverse);
    return `
      <div class="primary-row">
        <div class="primary-head">
          <strong>${spec.label}</strong>
          <em class="grade-${gradeClass(gradeText)}">${gradeText}</em>
        </div>
        <div class="range-track">
          <i class="range-fill"></i>
          <b style="left:${markerLeft(value, spec)}%"></b>
        </div>
        <div class="primary-value">${fmtMetric(source, spec.field, spec)}</div>
      </div>`;
  }).join("");
}

const analysisGroups = [
  ["Firepower", "firepower", [
    ["Kills per round", "kpr", { digits: 2 }],
    ["Kills per round win", "kills_per_round_win", { digits: 2 }],
    ["Damage per round", "adr", { digits: 1 }],
    ["Damage per round win", "damage_per_round_win", { digits: 1 }],
    ["Rounds with a kill", "rounds_with_kill_percentage", { percent: true, digits: 1 }],
    ["Rating 3.0", "rating", { digits: 2 }],
    ["Rounds with a multi-kill", "multi_kill_rate", { percent: true, digits: 1 }],
    ["Pistol round rating", "pistol_rating", { digits: 2 }]
  ]],
  ["Entrying", "entrying", [
    ["Saved by teammate per round", "saved_by_teammate_per_round", { digits: 2 }],
    ["Traded deaths per round", "traded_deaths_per_round", { digits: 2 }],
    ["Traded deaths percentage", "traded_deaths_percentage", { percent: true, digits: 1 }],
    ["Opening deaths traded percentage", "opening_deaths_traded_percentage", { percent: true, digits: 1 }],
    ["Assists per round", "apr", { digits: 2 }],
    ["Support rounds", "support_rounds_percentage", { percent: true, digits: 1 }]
  ]],
  ["Trading", "trading", [
    ["Saved teammate per round", "saved_teammate_per_round", { digits: 2 }],
    ["Trade kills per round", "trade_kills_per_round", { digits: 2 }],
    ["Trade kills percentage", "trade_kills_percentage", { percent: true, digits: 1 }],
    ["Assisted kills percentage", "assisted_kills_percentage", { percent: true, digits: 1 }],
    ["Damage per kill", "damage_per_kill", { digits: 0 }]
  ]],
  ["Opening", "opening", [
    ["Opening kills per round", "opening_kills_per_round", { digits: 2 }],
    ["Opening deaths per round", "opening_deaths_per_round", { digits: 2 }],
    ["Opening attempts", "opening_attempts", { percent: true, digits: 1 }],
    ["Opening success", "opening_success", { percent: true, digits: 1 }],
    ["Win% after opening kill", "win_after_opening_kill", { percent: true, digits: 1 }],
    ["Attacks per round", "attacks_per_round", { digits: 2 }]
  ]],
  ["Clutching", "clutching", [
    ["Clutch points per round", "clutch_points_per_round", { digits: 2 }],
    ["Last alive percentage", "last_alive_percentage", { percent: true, digits: 1 }],
    ["1on1 win percentage", "one_on_one_win_percentage", { percent: true, digits: 1 }],
    ["Time alive per round", "time_alive_per_round_seconds", { time: true }],
    ["Saves per round loss", "saves_per_round_loss", { percent: true, digits: 1 }]
  ]],
  ["Sniping", "sniping", [
    ["Sniper kills per round", "sniper_kills_per_round", { digits: 2 }],
    ["Sniper kills percentage", "sniper_kills_percentage", { percent: true, digits: 1 }],
    ["Rounds with sniper kills percentage", "rounds_with_sniper_kills_percentage", { percent: true, digits: 1 }],
    ["Sniper multi-kill rounds", "sniper_multi_kill_rounds_rate", { digits: 3 }],
    ["Sniper opening kills per round", "sniper_opening_kills_per_round", { digits: 3 }]
  ]],
  ["Utility", "utility", [
    ["Utility damage per round", "utility_damage_per_round", { digits: 2 }],
    ["Utility kills per 100 rounds", "utility_kills_per_100_rounds", { digits: 2 }],
    ["Flashes thrown per round", "flashes_thrown_per_round", { digits: 2 }],
    ["Flash assists per round", "flash_assists_per_round", { digits: 2 }],
    ["Time opponent flashed per round", "time_opponent_flashed_per_round", { digits: 2 }]
  ]]
];

function renderAnalysisGroups(player) {
  document.getElementById("analysisGroups").innerHTML = analysisGroups.map(([title, scoreField, details]) => `
    <details class="analysis-card ${title === "Firepower" ? "wide" : ""}">
      <summary>
        <strong>${title}</strong>
        ${scoreText(player[scoreField])}
        ${scoreText(player.sides.CT?.[scoreField], "CT ")}
        ${scoreText(player.sides.T?.[scoreField], "T ")}
      </summary>
      ${renderAnalysisDetails(player, title, details)}
    </details>`).join("");
  renderAnalysisRadar(player);
}

function renderAnalysisRadar(player) {
  const radar = document.getElementById("analysisRadar");
  const axes = analysisGroups.map(([title, scoreField]) => ({ title, scoreField }));
  const size = 400;
  const center = size / 2;
  const radius = 132;
  const angleStep = (Math.PI * 2) / axes.length;
  const point = (index, value) => {
    const angle = -Math.PI / 2 + index * angleStep;
    const scaled = Math.max(0, Math.min(100, Number(value || 0))) / 100;
    return [
      center + Math.cos(angle) * radius * scaled,
      center + Math.sin(angle) * radius * scaled
    ];
  };
  const ring = level => axes.map((_, index) => point(index, level)).map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const shape = side => axes.map(({ scoreField }, index) => {
    const source = side === "Both" ? player : player.sides?.[side];
    return point(index, source?.[scoreField]);
  }).map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const labels = axes.map(({ title, scoreField }, index) => {
    const angle = -Math.PI / 2 + index * angleStep;
    const labelRadius = radius + 36;
    const rawX = center + Math.cos(angle) * labelRadius;
    const rawY = center + Math.sin(angle) * labelRadius;
    const anchor = Math.abs(Math.cos(angle)) < 0.2 ? "middle" : Math.cos(angle) > 0 ? "start" : "end";
    const x = anchor === "start" ? Math.min(rawX, size - 86) : anchor === "end" ? Math.max(rawX, 86) : rawX;
    const y = Math.max(18, Math.min(size - 26, rawY));
    const value = n(player?.[scoreField], 0);
    return `
      <text class="radar-label" x="${x.toFixed(1)}" y="${y.toFixed(1)}" text-anchor="${anchor}">${title}</text>
      <text class="radar-value" x="${x.toFixed(1)}" y="${(y + 14).toFixed(1)}" text-anchor="${anchor}">${value}/100</text>`;
  }).join("");
  const axesLines = axes.map((_, index) => {
    const [x, y] = point(index, 100);
    return `<line class="radar-axis" x1="${center}" y1="${center}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}"></line>`;
  }).join("");
  const radarShapes = SIDES.filter(side => radarSides[side]).map(side => `
      <polygon class="radar-shape radar-shape-${side.toLowerCase()}" points="${shape(side)}"></polygon>`).join("");
  radar.innerHTML = `
    <div class="radar-header">
      <div class="radar-legend">
        ${SIDES.map(side => `
          <button class="radar-toggle ${side.toLowerCase()} ${radarSides[side] ? "active" : ""}" data-radar-side="${side}">
            <i></i>${side}
          </button>`).join("")}
      </div>
    </div>
    <svg class="radar-svg" viewBox="0 0 ${size} ${size}" role="img" aria-label="Analysis radar chart">
      <polygon class="radar-grid" points="${ring(20)}"></polygon>
      <polygon class="radar-grid" points="${ring(40)}"></polygon>
      <polygon class="radar-grid" points="${ring(60)}"></polygon>
      <polygon class="radar-grid" points="${ring(80)}"></polygon>
      <polygon class="radar-grid" points="${ring(100)}"></polygon>
      ${axesLines}
      ${radarShapes}
      ${labels}
    </svg>`;
  for (const button of radar.querySelectorAll(".radar-toggle")) {
    button.addEventListener("click", () => {
      const side = button.dataset.radarSide;
      radarSides[side] = !radarSides[side];
      renderAnalysisRadar(player);
    });
  }
}

function renderAnalysisDetails(player, title, details) {
  const chunks = [details];
  return `<div class="analysis-table ${title === "Firepower" ? "two-col" : ""}">
    ${chunks.map(chunk => `
      <div class="analysis-subtable">
        <div class="analysis-line head"><span>Metric</span><b>Both</b><b>CT</b><b>T</b></div>
        ${chunk.map(([labelText, field, spec]) => `
          <div class="analysis-line">
            <span>${labelText}</span>
            <b>${fmtMetric(player.sides.Both, field, spec)}</b>
            <b>${fmtMetric(player.sides.CT, field, spec)}</b>
            <b>${fmtMetric(player.sides.T, field, spec)}</b>
          </div>`).join("")}
      </div>`).join("")}
  </div>`;
}

function scoreClass(value) {
  const num = Number(value || 0);
  if (num >= 82) return "score-elite";
  if (num >= 66) return "score-good";
  if (num >= 48) return "score-okay";
  if (num >= 32) return "score-low";
  return "score-bad";
}

function scoreText(value, prefix = "") {
  const num = Math.round(value || 0);
  const side = prefix.trim();
  if (side === "CT" || side === "T") {
    return `<span class="score-pill side-score ${side.toLowerCase()}"><strong>${side}</strong><b>${num}</b><em>/100</em></span>`;
  }
  return `<span class="score-pill"><b class="${scoreClass(num)}">${num}</b><em>/100</em></span>`;
}

const statItems = [
  ["Total kills", "kills", { integer: true }],
  ["Headshot %", "headshot_rate", { percent: true, digits: 1 }],
  ["Total deaths", "deaths", { integer: true }],
  ["Grenade dmg / Round", "utility_damage_per_round", { digits: 1 }],
  ["Maps played", "matches", { integer: true }],
  ["Rounds played", "rounds", { integer: true }],
  ["Assists / round", "apr", { digits: 2 }],
  ["Saved by teammate / round", "saved_by_teammate_per_round", { digits: 2 }],
  ["Saved teammates / round", "saved_teammate_per_round", { digits: 2 }],
  ["Trade kills", "trade_kills", { integer: true }],
  ["Traded deaths", "traded_deaths", { integer: true }],
  ["Flash assists", "flash_assists", { integer: true }]
];

function renderStatistics(player) {
  document.getElementById("statisticsGrid").innerHTML = statItems.map(([labelText, field, spec = {}]) => `
    <div class="stat-cell"><span>${labelText}</span><strong>${fmtMetric(player, field, spec)}</strong></div>`).join("");
}

function label(col) {
  return {
    player: "Player", matches: "Matches", rounds: "Rounds", rating: "Rating", firepower: "Firepower", entrying: "Entry", trading: "Trade",
    opening: "Opening", utility: "Utility", kd: "K/D", adr: "ADR", kast: "KAST%", kpr: "KPR", dpr: "DPR",
    date: "Date", map_name: "Map", match_result: "Result", roster_type: "Roster", roster_status: "Status",
    kills: "K", deaths: "D", assists: "A", trade_kills: "Trade", score: "Score", round_win_rate: "Round Win%",
    total_score: "Score", ct_score: "CT", t_score: "T", score_split: "Score (CT, T)", opening_diff: "Opening diff", clutch_record: "Clutch W-L"
  }[col] || col;
}

function fmt(col, value) {
  if (["matches", "rounds", "kills", "deaths", "assists", "firepower", "entrying", "trading", "opening", "utility"].includes(col)) return n(value, 0);
  if (["rating", "kd", "kpr", "dpr"].includes(col)) return n(value, 2);
  if (["adr", "kast"].includes(col)) return n(value, 1);
  if (["round_win_rate"].includes(col)) return `${n(value, 1)}%`;
  if (["opening_diff"].includes(col)) return signed(value, 0);
  return value ?? "";
}

function mapKey(mapName) {
  return String(mapName || "").replace(/^de_/, "").toLowerCase();
}

function mapBadge(mapName) {
  const clean = String(mapName || "").replace(/^de_/, "");
  const short = {
    dust2: "D2", inferno: "INF", mirage: "MIR", nuke: "NUK", ancient: "ANC",
    anubis: "ANB", vertigo: "VTG", overpass: "OVP", cache: "CAC", train: "TRN"
  }[clean.toLowerCase()] || clean.slice(0, 3).toUpperCase();
  const key = clean.toLowerCase();
  const icon = ["ancient", "anubis", "cache", "dust2", "inferno", "mirage", "nuke", "train"].includes(key)
    ? `<img class="map-icon-img" src="./assets/maps/${key}.png" alt="${clean}">`
    : `<i class="map-icon map-${key}">${short}</i>`;
  return `<span class="map-cell map-cell-icon-only" title="${clean}">${icon}</span>`;
}

function resultCell(value) {
  const text = String(value || "");
  const cls = /win/i.test(text) ? "result-win" : /loss|lose/i.test(text) ? "result-loss" : "result-neutral";
  return `<span class="result-pill ${cls}">${text}</span>`;
}

function statusCell(value) {
  return `<span class="status-badge status-${gradeClass(value)}">${value || ""}</span>`;
}

function ratingCell(value) {
  return `<span class="rating-value rating-${ratingClass(value)}">${n(value, 2)}</span>`;
}

function percentClass(value) {
  const num = Number(value || 0);
  if (num >= 60) return "metric-good";
  if (num >= 50) return "metric-okay";
  return "metric-bad";
}

function kdClass(value) {
  const num = Number(value || 0);
  if (num >= 1.05) return "metric-good";
  if (num >= 0.95) return "metric-okay";
  return "metric-bad";
}

function renderTable(id, rows, cols) {
  const table = document.getElementById(id);
  table.innerHTML = `<thead><tr>${cols.map(col => `<th>${label(col)}</th>`).join("")}</tr></thead>`;
  const body = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    if (row.match_id) {
      tr.classList.add("clickable-row");
      tr.addEventListener("click", () => {
        window.open(`./match.html?match=${encodeURIComponent(row.match_id)}`, "_blank", "noopener");
      });
    }
    for (const col of cols) {
      const td = document.createElement("td");
      if (col === "map_name") td.innerHTML = mapBadge(row[col]);
      else if (col === "match_result") td.innerHTML = resultCell(row[col]);
      else if (col === "roster_status") td.innerHTML = statusCell(row[col]);
      else if (col === "rating") td.innerHTML = ratingCell(row[col]);
      else if (col === "opening_diff") td.innerHTML = `<span class="${Number(row[col] || 0) >= 0 ? "metric-good" : "metric-bad"}">${fmt(col, row[col])}</span>`;
      else if (col === "ct_score") td.innerHTML = `<span class="ct">${fmt(col, row[col])}</span>`;
      else if (col === "t_score") td.innerHTML = `<span class="t">${fmt(col, row[col])}</span>`;
      else if (col === "score_split") td.innerHTML = row[col];
      else if (col === "round_win_rate") td.innerHTML = row[col];
      else td.textContent = fmt(col, row[col]);
      tr.appendChild(td);
    }
    body.appendChild(tr);
  }
  table.appendChild(body);
}

function teamSideScore(row, side) {
  const sideRow = row?.sides?.[side] || {};
  return Math.round(div(Number(sideRow.rounds_won || 0), 5));
}

function teamSideRounds(row, side) {
  const sideRow = row?.sides?.[side] || {};
  return Math.round(div(Number(sideRow.rounds || 0), 5));
}

function formatTeamScore(row) {
  return `${String(row.our_score ?? 0).padStart(2, "0")}-${String(row.opponent_score ?? 0).padStart(2, "0")}`;
}

function formatSideScore(row, side) {
  const ctWon = teamSideScore(row, "CT");
  const tWon = teamSideScore(row, "T");
  const ctLost = Math.max(0, teamSideRounds(row, "CT") - ctWon);
  const tLost = Math.max(0, teamSideRounds(row, "T") - tWon);
  return side === "CT"
    ? `${String(ctWon).padStart(2, "0")}-${String(ctLost).padStart(2, "0")}`
    : `${String(tWon).padStart(2, "0")}-${String(tLost).padStart(2, "0")}`;
}

function paddedPercent(value) {
  return `${n(value, 1)}%`.padStart(6, " ");
}

function formatScoreSplit(row) {
  return `<span class="score-split mono-stat">${formatTeamScore(row)} <span>(<b class="ct">${formatSideScore(row, "CT")}</b>, <b class="t">${formatSideScore(row, "T")}</b>)</span></span>`;
}

function formatRoundWinRateSplit(row) {
  const total = 100 * div(Number(row.rounds_won || 0), Number(row.rounds || 0));
  const ct = 100 * div(teamSideScore(row, "CT"), teamSideRounds(row, "CT"));
  const t = 100 * div(teamSideScore(row, "T"), teamSideRounds(row, "T"));
  return `<span class="score-split mono-stat">${paddedPercent(total)} <span>(<b class="ct">${paddedPercent(ct)}</b>, <b class="t">${paddedPercent(t)}</b>)</span></span>`;
}

function formatClutchRecord(row) {
  const narrow = `${Number(row.clutch_wins || 0)}-${Number(row.clutch_losses || 0)}`;
  const broad = `${Number(row.clutch_broad_wins || 0)}-${Number(row.clutch_broad_losses || 0)}`;
  return `${narrow} (${broad})`;
}

function recordHtml(wins, draws, losses) {
  return `<span class="record-inline"><b class="record-win">${n(wins, 0)}</b><em>/</em><b class="record-draw">${n(draws, 0)}</b><em>/</em><b class="record-loss">${n(losses, 0)}</b></span>`;
}

function renderTeamMatchesTable(matches) {
  const rows = (matches || []).slice().sort((a, b) => b.date.localeCompare(a.date)).map(row => ({
    ...row,
    score_split: formatScoreSplit(row),
    opening_diff: Number(row.opening_kills || 0) - Number(row.opening_deaths || 0),
    clutch_record: formatClutchRecord(row),
    round_win_rate: formatRoundWinRateSplit(row)
  }));
  renderTable("teamMatchesTable", rows, teamMatchColumns);
}

function failureMatchLabel(row) {
  return `${row.date} · ${row.roster_type}`;
}

function collectClutchFailures(matches, state) {
  return (matches || []).flatMap(match => {
    if (Array.isArray(match.clutch_failures)) {
      return match.clutch_failures
        .filter(item => item.state === state)
        .map(item => ({ ...item, match }));
    }
    const count = Number(match.failure_counts?.clutch?.[state] || 0);
    return count ? [{ state, count, match }] : [];
  })
    .sort((a, b) => b.match.date.localeCompare(a.match.date) || Number(a.round) - Number(b.round));
}

function collectFiveVFourFailures(matches) {
  return (matches || []).flatMap(match => {
    if (Array.isArray(match.advantage_failures)) {
      return match.advantage_failures
        .filter(item => item.state === "5v4")
        .map(item => ({ ...item, match }));
    }
    const count = Number(match.failure_counts?.advantage?.["5v4"] || 0);
    return count ? [{ state: "5v4", count, match }] : [];
  })
    .sort((a, b) => b.match.date.localeCompare(a.match.date) || Number(a.round) - Number(b.round));
}

function renderFailureList(id, rows, emptyText) {
  const target = document.getElementById(id);
  if (!rows.length) {
    target.innerHTML = `<div class="empty-state">${emptyText}</div>`;
    return;
  }
  target.innerHTML = rows.map(item => `
    <div class="failure-row clickable-row" data-match-id="${esc(item.match.match_id)}">
      <div class="failure-main">
        ${mapBadge(item.match.map_name)}
        <strong>${item.match.date}</strong>
        <span class="failure-score mono-stat">${formatTeamScore(item.match)}</span>
        ${resultCell(item.match.match_result)}
        <span class="failure-roster">${item.match.roster_type}</span>
      </div>
      <div class="failure-meta">
        <span>${item.round ? "Round" : "Count"}</span>
        <b>${item.round || item.count || 1}</b>
      </div>
      <div class="failure-state ${String(item.side || "").toLowerCase()}">
        <span>${item.side}</span>
        <b>${item.state}</b>
      </div>
    </div>`).join("");
  for (const row of target.querySelectorAll(".failure-row[data-match-id]")) {
    row.addEventListener("click", () => {
      window.open(`./match.html?match=${encodeURIComponent(row.dataset.matchId)}`, "_blank", "noopener");
    });
  }
}

function renderFailureAnalysis(matches) {
  const filters = document.getElementById("clutchFailureFilters");
  filters.innerHTML = clutchFailureTypes.map(type => {
    const count = collectClutchFailures(matches, type).length;
    return `
      <label class="failure-check ${selectedFailureType === type ? "active" : ""}">
        <input type="checkbox" value="${type}" ${selectedFailureType === type ? "checked" : ""}>
        <span>${type}</span>
        <b>${count}</b>
      </label>`;
  }).join("");
  for (const input of filters.querySelectorAll("input")) {
    input.addEventListener("change", () => {
      selectedFailureType = input.value;
      renderFailureAnalysis(matches);
    });
  }
  renderFailureList("clutchFailureList", collectClutchFailures(matches, selectedFailureType), `No ${selectedFailureType} failures.`);
  renderFailureList("fiveVFourFailures", collectFiveVFourFailures(matches), "No 5v4 failures.");
}

function renderMapsGrid(rows) {
  const grid = document.getElementById("mapsGrid");
  grid.innerHTML = rows.map(row => {
    const key = mapKey(row.map_name);
    const bg = mapBackground(key) || "dust2.jpg";
    return `
      <div class="map-card" style="--map-bg: url('./assets/map-backgrounds/${bg}')">
        <div class="map-art"><span>${row.map_name}</span></div>
        <div class="map-main">
          <div class="map-title">
            <strong>${row.map_name}</strong>
            <span class="map-count">${row.matches} maps</span>
            <span class="map-count">${row.rounds} rounds</span>
          </div>
          <div class="map-primary">
            <span>Rating <b class="rating-${ratingClass(row.rating)}">${n(row.rating, 2)}</b></span>
            <span>Firepower <b class="${scoreClass(row.firepower)}">${n(row.firepower, 0)}</b></span>
          </div>
        </div>
        <div class="map-kpis">
          <span>K/D <b>${n(row.kd, 2)}</b></span>
          <span>ADR <b>${n(row.adr, 1)}</b></span>
          <span>KAST <b>${n(row.kast, 1)}%</b></span>
        </div>
      </div>`;
  }).join("");
}

function mapBackground(key) {
  const available = new Set(["ancient", "anubis", "cache", "dust2", "inferno", "mirage", "nuke", "train"]);
  return available.has(key) ? `${key}.jpg` : "";
}

function renderTeamStarters() {
  const statsByPlayer = playerSummaryByName();
  const starters = currentStarters();
  const target = document.getElementById("teamStarters");
  if (!starters.length) {
    target.innerHTML = `<div class="empty-state">No current roster rows found.</div>`;
    return;
  }
  target.innerHTML = starters.map(row => {
    const stats = statsByPlayer.get(row.player) || {};
    return `
      <div class="starter-card">
        <strong>${esc(row.player)}</strong>
        <span class="starter-rating-metric">Rating <b class="rating-${ratingClass(stats.rating)}">${n(stats.rating, 2)}</b></span>
        <span>Maps <b>${n(stats.matches, 0)}</b></span>
        <span>K/D <b>${n(stats.kd, 2)}</b></span>
        <span>ADR <b>${n(stats.adr, 1)}</b></span>
      </div>`;
  }).join("");
}

function renderRosterTimeline() {
  const rows = normalizedRosterRows();
  const target = document.getElementById("rosterTimeline");
  if (!rows.length) {
    target.innerHTML = `<div class="empty-state">No roster history available.</div>`;
    return;
  }
  const validDates = rows.flatMap(row => [row.startDate, row.endDate || new Date()]).filter(Boolean);
  const minTime = Math.min(...validDates.map(date => date.getTime()));
  const maxTime = Math.max(...validDates.map(date => date.getTime()));
  const span = Math.max(maxTime - minTime, 1);
  const players = unique(rows.map(row => row.player));
  const tickCount = 5;
  const ticks = Array.from({ length: tickCount }, (_, index) => {
    const ratio = tickCount <= 1 ? 0 : index / (tickCount - 1);
    const date = new Date(minTime + span * ratio).toISOString().slice(0, 10);
    return { ratio, date };
  });
  target.innerHTML = `
    <div class="timeline-axis">
      <span></span>
      <div class="timeline-ticks">
        ${ticks.map(tick => `<i style="left:${tick.ratio * 100}%"><b>${tick.date}</b></i>`).join("")}
      </div>
    </div>
    ${players.map(player => {
      const stints = rows.filter(row => row.player === player);
      return `
        <div class="timeline-row">
          <strong>${esc(player)}</strong>
          <div class="timeline-track">
            ${stints.filter(stint => !/^(left|change)$/i.test(stint.status)).map(stint => {
              const start = stint.startDate?.getTime() ?? minTime;
              const end = (stint.endDate || new Date()).getTime();
              const left = clamp(100 * (start - minTime) / span);
              const width = Math.max(2, clamp(100 * (end - start) / span));
              if (end <= start) return "";
              return `<i class="timeline-segment status-line-${gradeClass(stint.status)}" title="${esc(stint.status)} ${esc(stint.start)} - ${esc(stint.end || "Present")}" style="left:${left}%;width:${width}%"></i>`;
            }).join("")}
          </div>
        </div>`;
    }).join("")}
    <div class="timeline-legend">
      <span><i class="status-line-starter"></i>Starter</span>
      <span><i class="status-line-stand-in"></i>Stand-in</span>
      <span><i class="status-line-benched"></i>Benched</span>
    </div>`;
}

function renderRosterHistoryTable() {
  const table = document.getElementById("rosterHistoryTable");
  const rows = normalizedRosterRows().slice().sort((a, b) => b.index - a.index);
  table.innerHTML = `<thead><tr><th>Player</th><th>Status</th><th>Start</th><th>End</th><th>Steam64</th></tr></thead>`;
  const body = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${esc(row.player)}</td>
      <td>${statusCell(row.status)}</td>
      <td>${esc(row.start)}</td>
      <td>${esc(row.end || "Present")}</td>
      <td>${esc(row.steam64)}</td>`;
    body.appendChild(tr);
  }
  table.appendChild(body);
}

function syncRosterPanelHeights() {
  const timeline = document.getElementById("rosterTimeline");
  const history = document.querySelector(".roster-history-scroll");
  if (!timeline || !history) return;
  const timelineHeight = timeline.offsetHeight;
  const timelinePanel = timeline.closest(".panel");
  const historyPanel = history.closest(".panel");
  history.style.maxHeight = `${timelineHeight}px`;
  history.style.minHeight = `${timelineHeight}px`;
  if (timelinePanel && historyPanel) historyPanel.style.minHeight = `${timelinePanel.offsetHeight}px`;
}

function renderTeam() {
  const team = summary?.team || {};
  const overview = team.overview || {};
  document.getElementById("teamOverview").innerHTML = `
    <div class="team-brand">
      <strong>WOST</strong>
      <span>Wake Once Sleep Thrice</span>
    </div>
    <div class="team-showcase">
      <div class="team-showcase-main">
        <span>Maps played</span>
        <strong class="metric-neutral">${n(overview.maps_played, 0)}</strong>
      </div>
      <div class="team-showcase-record">
        <span>Wins / draws / losses</span>
        <b><i class="record-win">${n(overview.wins, 0)}</i><em>/</em><i class="record-draw">${n(overview.draws, 0)}</i><em>/</em><i class="record-loss">${n(overview.losses, 0)}</i></b>
      </div>
    </div>
    <div class="team-kpi-grid">
      <span>Rounds played <b class="metric-neutral">${n(overview.rounds, 0)}</b></span>
      <span>K/D Ratio <b class="${kdClass(overview.kd)}">${n(overview.kd, 2)}</b></span>
      <span>Win rate <b class="${percentClass(overview.win_rate)}">${n(overview.win_rate, 1)}%</b></span>
      <span>Round win rate <b class="${percentClass(overview.round_win_rate)}">${n(overview.round_win_rate, 1)}%</b></span>
    </div>`;
  renderTeamStarters();
  renderRosterTimeline();
  renderRosterHistoryTable();
  syncRosterPanelHeights();
  renderTeamMatchesTable(team.matches);
  renderFailureAnalysis(team.matches || []);
  document.getElementById("teamMaps").innerHTML = (team.maps || []).map(row => `
    <div class="team-map-card" style="--map-bg: url('./assets/map-backgrounds/${mapBackground(mapKey(row.map_name)) || "dust2.jpg"}')">
      <div class="team-map-head">
        <div>${mapBadge(row.map_name)}<span>${esc(row.map_name)}</span></div>
        <strong>${n(row.pick_rate, 1)}% pick</strong>
      </div>
      <div class="map-rate-bars">
        <span><em>Pick</em><i style="width:${clamp(row.pick_rate)}%"></i><b>${n(row.matches, 0)} maps</b></span>
        <span><em>Win</em><i class="win-bar" style="width:${clamp(row.win_rate)}%"></i><b>${n(row.win_rate, 1)}%</b></span>
      </div>
      <div class="team-map-data">
        <span class="team-map-record">Record ${recordHtml(row.wins, row.draws, row.losses)}</span>
        <span>Round win <b>${n(row.round_win_rate, 1)}%</b></span>
        <span>5v4 <b>${n(row.five_v_four_win_rate, 1)}%</b></span>
        <span>4v5 <b>${n(row.four_v_five_win_rate, 1)}%</b></span>
        <span>K/D <b>${n(row.kd, 2)}</b></span>
      </div>
    </div>`).join("");
}

function setView(viewId) {
  for (const button of document.querySelectorAll(".view-tab")) {
    button.classList.toggle("active", button.dataset.view === viewId);
  }
  document.getElementById("playersView").hidden = viewId !== "playersView";
  document.getElementById("teamView").hidden = viewId !== "teamView";
}

function renderTrend(rows) {
  const canvas = document.getElementById("trendCanvas");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const points = rows.slice().sort((a, b) => a.date.localeCompare(b.date));
  const plot = { left: 56, right: 24, top: 46, bottom: 42 };
  const width = canvas.width - plot.left - plot.right;
  const height = canvas.height - plot.top - plot.bottom;
  ctx.strokeStyle = "#263546";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(plot.left, plot.top);
  ctx.lineTo(plot.left, plot.top + height);
  ctx.lineTo(plot.left + width, plot.top + height);
  ctx.stroke();
  const ratings = points.map(row => Number(row.rating || 0));
  const averageRating = ratings.length ? ratings.reduce((sum, value) => sum + value, 0) / ratings.length : 0;
  const minY = Math.max(0, Math.min(0.8, Math.floor((Math.min(...ratings, 1) - 0.1) * 10) / 10));
  const maxY = Math.min(2, Math.max(1.4, Math.ceil((Math.max(...ratings, 1) + 0.1) * 10) / 10));
  ctx.fillStyle = "#8f9eb1";
  ctx.font = "13px sans-serif";
  for (let i = 0; i <= 4; i += 1) {
    const value = minY + (maxY - minY) * (i / 4);
    const y = plot.top + height - (i / 4) * height;
    ctx.fillText(n(value, 2), 12, y + 4);
    ctx.strokeStyle = "#1b2735";
    ctx.beginPath();
    ctx.moveTo(plot.left, y);
    ctx.lineTo(plot.left + width, y);
    ctx.stroke();
  }
  function yFor(value) {
    return plot.top + height - div(Number(value || 0) - minY, maxY - minY) * height;
  }
  function guideLine(value, color) {
    const y = yFor(value);
    if (y < plot.top || y > plot.top + height) return;
    ctx.strokeStyle = color;
    ctx.setLineDash([6, 6]);
    ctx.beginPath();
    ctx.moveTo(plot.left, y);
    ctx.lineTo(plot.left + width, y);
    ctx.stroke();
    ctx.setLineDash([]);
  }
  guideLine(1.0, "#dbe3ee");
  if (averageRating) guideLine(averageRating, "#e9c46a");
  ctx.strokeStyle = "#72a7ff";
  ctx.lineWidth = 3;
  ctx.beginPath();
  points.forEach((row, index) => {
    const x = points.length <= 1 ? plot.left + width / 2 : plot.left + index * (width / (points.length - 1));
    const y = yFor(row.rating);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.fillStyle = "#72a7ff";
  points.forEach((row, index) => {
    const x = points.length <= 1 ? plot.left + width / 2 : plot.left + index * (width / (points.length - 1));
    const y = yFor(row.rating);
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.fillStyle = "#9aa8bd";
  ctx.font = "13px sans-serif";
  ctx.fillText("Rating", 58, 22);
  const legend = [
    ["#72a7ff", "Match rating"],
    ["#e9c46a", `Average ${n(averageRating, 2)}`],
    ["#dbe3ee", "Baseline 1.00"]
  ];
  let lx = plot.left + 92;
  for (const [color, text] of legend) {
    ctx.fillStyle = color;
    ctx.fillRect(lx, 14, 16, 3);
    ctx.fillStyle = "#9aa8bd";
    ctx.fillText(text, lx + 22, 18);
    lx += ctx.measureText(text).width + 54;
  }
  if (points.length) {
    ctx.fillText(points[0].date, plot.left, canvas.height - 14);
    ctx.textAlign = "right";
    ctx.fillText(points[points.length - 1].date, plot.left + width, canvas.height - 14);
    ctx.textAlign = "left";
  }
}

function render() {
  const selectedMatches = filteredMatches(true);
  const allFiltered = filteredMatches(false);
  const order = rosterOrder();
  const players = aggregate(allFiltered).sort((a, b) => {
    const statusDiff = (statusRank[latestRosterStatus(a.player)] ?? 99) - (statusRank[latestRosterStatus(b.player)] ?? 99);
    if (statusDiff) return statusDiff;
    return order.indexOf(a.player) - order.indexOf(b.player);
  });
  for (const player of players) player.roster_status = latestRosterStatus(player.player);
  const selectedPlayer = aggregate(selectedMatches)[0] || players[0] || withSides(emptyAgg({ player: "No Data" }));
  selectedPlayer.roster_status = latestRosterStatus(selectedPlayer.player);
  const maps = aggregate(selectedMatches, "map_name").sort((a, b) => b.matches - a.matches);
  renderPlayerCard(selectedPlayer);
  renderPrimaryMetrics(selectedPlayer);
  renderAnalysisGroups(selectedPlayer);
  renderStatistics(selectedPlayer);
  renderTable("playersTable", players, playerColumns);
  renderMapsGrid(maps);
  renderTable("matchesTable", selectedMatches.slice().sort((a, b) => b.date.localeCompare(a.date)), matchColumns);
  renderTrend(selectedMatches);
  renderTeam();
}

for (const id of ["playerFilter", "quarterFilter", "mapFilter", "rosterFilter", "resultFilter", "startDate", "endDate"]) {
  document.getElementById(id).addEventListener("change", render);
}
for (const button of document.querySelectorAll(".view-tab")) {
  button.addEventListener("click", () => setView(button.dataset.view));
}
window.addEventListener("resize", syncRosterPanelHeights);
loadData().catch(error => console.error(error));
