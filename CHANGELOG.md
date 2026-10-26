# Changelog

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
