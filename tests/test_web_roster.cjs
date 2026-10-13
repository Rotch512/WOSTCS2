const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../web/app.js"), "utf8");
const rosterFunctions = source.slice(source.indexOf("function latestRosterStatus("),
  source.indexOf("function playerSummaryByName("));
const context = vm.createContext({
  rosterRows: [],
  statusRank: { Starter: 0, "Stand-in": 1, Benched: 2, Left: 3 },
});
vm.runInContext(rosterFunctions, context);
const run = expression => JSON.parse(JSON.stringify(vm.runInContext(expression, context)));
const row = (player, start, status, extra = {}) => ({
  Player: player, Start: start, Status: status, SteamID: "1", ...extra,
});

// Unsorted history, rejoining, future changes and account changes.
context.rosterRows = [
  row("p", "2020-06-01", "Benched"),
  row("p", "2020-01-01", "Starter"),
  row("p", "2020-03-01", "Left"),
  row("p", "2020-05-01", "Starter"),
  row("p", "2099-01-01", "Starter"),
  row("q", "2020-01-01", "Starter"),
  row("q", "2020-02-01", "Change", { SteamID: "2" }),
  row("q", "2020-03-01", "Change", { SteamID: "3" }),
];
assert.deepEqual(run("currentStarters().map(row => row.player)"), ["q"]);
assert.equal(run('latestRosterStatus("p")'), "Benched");
assert.equal(run('currentRosterRows().find(row => row.player === "q").steam64'), "3");
assert.equal(run('normalizedRosterRows().find(row => row.player === "p" && row.start === "2020-01-01").end'), "2020-03-01");

// Same-day changes use sheet order; an explicit End may close a stint early.
context.rosterRows = [
  row("p", "2020-01-01", "Starter"),
  row("p", "2020-01-01", "Benched"),
  row("q", "2020-01-01", "Starter", { End: "2020-02-01" }),
];
assert.deepEqual(run("currentStarters()"), []);
assert.deepEqual(run("currentRosterRows().map(row => row.player)"), ["p"]);

// Reproduce the actual missing-End fixture from the reported lineup.
context.rosterRows = [
  ...["Add1t", "lazy_ruin", "-叶知秋-", "SingleBoy2147"].map(player => row(player, "2026-5-28", "Starter")),
  row("qiuda", "2026-5-30", "Starter"),
  row("qiuda", "2026-6-2", "Benched"),
  row("qiuda", "2026-6-4", "Left"),
  row("cAh", "2026-6-11", "Starter"),
  row("Ramos4Madrid", "2026-7-17", "Starter"),
  row("cAh", "2026-7-23", "Benched"),
  row("qiuda", "2026-9-14", "Starter"),
  row("cAh", "2026-9-14", "Starter"),
  row("-叶知秋-", "2026-9-15", "Benched"),
  row("Ramos4Madrid", "2026-9-15", "Benched"),
  row("qiuda", "2026-9-24", "Benched"),
  row("-叶知秋-", "2026-9-24", "Starter"),
];
vm.runInContext(`Date = class extends Date {
  constructor(...args) { super(...(args.length ? args : ["2026-10-13T12:00:00Z"])); }
}`, context);
assert.deepEqual(run("currentStarters().map(row => row.player).sort()"),
  ["Add1t", "SingleBoy2147", "cAh", "lazy_ruin", "-叶知秋-"].sort());
console.log("Roster frontend regression checks passed");
