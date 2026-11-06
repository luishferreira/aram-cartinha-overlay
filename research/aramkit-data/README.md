# ARAMKit public Mayhem data snapshot

Collected 2026-10-30. No credentials, account cookies, challenge bypass, or Overwolf used. These are research snapshots, not an overlay implementation.

## Sources and evidence

- Public page: https://aramkit.com/en-US/champions/masteryi
- Main client bundle: https://aramkit.com/_nuxt/D1fanaf7.js
- Champion component: https://aramkit.com/_nuxt/Bp4a6g6M.js
- Config in public HTML declares patch `16.21`, data date `2026-10-30`, `allMatches:31918755`, `highMatches:7979689`.
- Data root: `https://data.aramkit.com/data/16.21-20261030-5f02d4c12c0d/stats/all/`
- Global rank: `augment-rankings.json`
- Complete champion detail: `champion-details/{RiotChampionId}.json`
- Additional conditional builds/items: `champion-details/{RiotChampionId}-single-augments.json`
- Resource root: `https://data.aramkit.com/resources/16.21-32001640c0a4/en-US/resources/`; catalogs `augments.json`, `champions.json`.
- Client also supports `stats/high/`; that dataset was not collected here.
- REA inert JavaScript analysis Evidence: `ev_789751bafe6aa4f97f9f6383f3a1905bd2cca4553e505ba48d21a56dbf90af37`; partial conservative graph, no target execution. Exact URL assembly/schema subsequently corroborated by successful public HTTP responses.

## Coverage

173 champion detail responses, no errors. `manifest.json` preserves URL, collection time, size and SHA256. `normalized.json` has 22,618 champion/augment observations. `combinations.json` has 1,730 two-card records, exactly the published top ten per champion. Catalog contains 235 augments.

`masteryi-single-augments.json` is an example of conditional item/build data (6.8MB); not all champions were fetched for that larger optional resource.

## Schema and interpretation

Normalized observations use `source`, `champion_id` (Riot numeric ID), `augment_id` (numeric game augment ID), English `name`, `rarity` (`silver`, `gold`, `prismatic`), `tier`, `rank`, `win_rate`, `pick_rate`, `sample_count`, plus unmodified `raw` row. Both rate values are proportions, not percentages.

**Champion-specific tiers/ranks:** `augments.all[].tier/rank` are genuinely conditioned on the champion; `augmentTier/augmentRank/augmentWinRate` in the same raw row are separate global references. Example: Yi card2010 is S/rank5/WR0.6061 vs global C/rank178/WR0.4791. Do not substitute global fields into champion comparisons.

Each champion detail also has `augments.stages` keyed 1-4 with stage-specific rows. `availableStages` and `stageAgnostic` encode availability/scope, not observed synergy strength. `blueWinRate` and `redWinRate` are also present. Popularity denominator is not established by the response alone: do not assume it means chosen when offered, or directly equate percentages to OP.GG/Blitz.

`augmentCombinations` entries have `augmentIds` (pair), `rank`, `sampleCount`, `pickRate`, `winRate`; these are a truncated top-ten selection and do not establish causal synergy. Baseline, selection, item, skill, stage and game-duration effects remain potential confounders.

Rank is not strictly descending raw win rate (Yi rank8 WR0.5933 vs rank9 WR0.5998), so sorting formula should not be described as raw win-rate order. Exact server-side tier/rank formula was not recovered.

## Claimed origin and methodology

The public home FAQ says its data comes from matches the site keeps collecting across versions and brackets, is cleaned/recalculated in house rather than copied from third parties, and excludes AFK/passive/abnormally short games. It claims a large frequently updated dataset. These are **provider claims**, not independently audited evidence of collection method, representativeness, distinct match identities, or independence from Blitz/OP.GG. Public client source/HTTP data cannot establish those points.

The champion component computes displayed benefit as `row.winRate - champion.stats.winRate`, and pair benefit similarly against champion baseline. This is a descriptive delta, not an adjusted causal interaction estimate. Component also displays positive item/augment `synergyDelta` values supplied with item metadata. No full statistical formula was recovered.

## Research boundary

Only aggregate public files were downloaded. No personal match records or private databases accessed in this ARAMKit subtask. Public accessibility does not itself document permission for sustained redistribution; reuse/hosting terms remain unverified. This snapshot is suitable for offline comparison and hypothesis generation, not a guarantee that any published metric is accurate.
