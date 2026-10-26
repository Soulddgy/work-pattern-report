# Changelog

## 0.3.0 — 2026-10-26

- **Renamed from work-pattern-report to work-to-skills**, since the main output is now the set of skills to build per work area. Install again with the new name: `/plugin marketplace add Soulddgy/work-to-skills` and `/plugin install work-to-skills@work-to-skills`. The old GitHub URL redirects.
- Reports and run history now go to `~/Documents/work-to-skills/`. To keep the "since last run" comparison, move your old `~/Documents/work-pattern-report/` folder there.
- Report title is now "Work to Skills" / "스킬로 만들 업무".

## 0.2.1 — 2026-10-26

- No longer reads `~/.claude/settings.json`. It was only used to check for overlapping hooks, and it can hold API keys, so the directory scanner flagged it. The overlap check now covers skills, CLAUDE.md and scheduled routines.
- Re-encoded the README screenshots. The old compressed bytes happened to match a scanner pattern; the images look the same.

## 0.2.0 — 2026-10-26

- **Work-area skill candidates are now the main output.** The skill groups sessions into work areas, tags the rules you state while correcting the work (corrections, preferences, constraints, reasons for rejecting a result) and proposes a set of skills per area: the flow, the rules in your own words with dates, a proposed skill split by stage, and a build prompt for skill-creator.
- Reads what you already built (project and user skills with their creation dates, CLAUDE.md, per-project memory). Where skills exist it proposes what to add, and counts rules that came back after the skills were created.
- The earlier automation candidates become "Small automations" (commands, hooks, scripts), capped at four.
- Report: foldable sections and blocks (build prompts start open), expand/collapse all, nav controls that stay visible on narrow screens, rules table.
- Sample data now includes work areas.
- README rewritten around skill recommendations; notes on the 30-day transcript retention.

## 0.1.1 — 2026-10-26

- When the /insights analysis is stale (no data, last run more than 7 days before the window end, or under half the window's prompts covered), the skill now stops and asks you to run `/insights` first, then picks up the new data when you say continue. `/insights` can only be run by the user, so the skill asks instead of running it.
- README rewritten: version at the top, what the report shows, and plain-language notes on accuracy, active time, /insights coverage and token use.

## 0.1.0 — 2026-10-26

- First release.
- Counts repeated requests (count, days, sessions) with the user's own words quoted.
- Folds in /insights per-session facets: friction, outcomes, satisfaction.
- Bash command signatures (`git commit`, `gradlew assemble*`, `npm test`, …) with lookup utilities filtered out.
- Estimated active time from 5-minute activity bins.
- Run history: compares repeat keys with the previous run of the same scope.
- Korean and English in one report file with a toggle; everything Claude writes in `analysis.json` is bilingual, ids stay stable for history.
- Automation candidates are buildable: before → after, evidence table, quotes, design (trigger, steps marked auto / needs approval, output, location, what stays manual), success baseline, and a copy-paste build prompt.
- Editorial layout after newspaper data desks: white page, one signal red, square edges, numbered sections, sticky navigation, light/dark theme, offline single file.
- Excludes the summary inserted after `/compact` from prompt counts.
