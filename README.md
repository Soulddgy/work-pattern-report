# work-pattern-report

**English** · [한국어](README_KO.md)

A Claude Code skill that turns your own Claude Code history into a **local HTML report of what you keep asking for**, so you can decide what to automate from counts instead of impressions.

It is a companion to the built-in `/insights` command, not a replacement. `/insights` already explains each session's goal, outcome and friction. This skill adds what it doesn't count:

| | `/insights` | work-pattern-report |
|---|---|---|
| Session goals, outcomes, friction | ✅ | reused from `/insights` |
| How many times, **on how many days**, you asked for the same thing | — | ✅ |
| Which commands Claude actually ran (`git commit`, `npm test`, `gradlew assemble*`…) | tool names only | ✅ command level |
| Automation candidates backed by counts and your own words | narrative | ✅ |
| A buildable design per candidate: trigger, steps (auto vs. needs approval), where it lives, and a copy-paste build prompt | — | ✅ |
| Overlap check with your existing skills and hooks | — | ✅ |
| **Did the repeats go down after you automated?** | — | ✅ compares with the last run |
| Report language | English | Korean and English in one file, with a toggle |

![Sample report (synthetic data)](docs/screenshot-en.png)

*The screenshot uses made-up data from [`examples/make_sample.py`](examples/make_sample.py).*

## Install

```text
/plugin marketplace add Soulddgy/work-pattern-report
/plugin install work-pattern-report@work-pattern-report
```

Or copy `skills/work-pattern-report/` into `~/.claude/skills/`.

Requirements: Claude Code, Python 3.9+ (standard library only). Running `/insights` first is optional but recommended; without it the friction section is replaced by a note.

## Use

Just ask in your own words:

- "What do I spend my Claude time on? Find things I could automate."
- "Weekly retro for 10/19–10/25."
- "Only my-app, October. Focus on things I keep asking for."
- "Compare the last two weeks with the two weeks before. Did the repeats go down?"
- "내가 무슨 작업 많이 하는지 보여줘", "작업 패턴 분석해줘"

The report opens in the language you're talking in and has a 한국어 / English toggle in the top bar. Files go to `~/Documents/work-pattern-report/`:

```
report_<since>_<until>.html   the report (one self-contained file, works offline)
data/<since>_<until>/         extracted prompts, labels, analysis
history.json                  repeat counts per run, for "since last run"
```

## How it works

1. **Extract** (`scripts/extract.py`) — reads `~/.claude/projects/*/*.jsonl` and keeps only messages a person typed. Subagent traffic, system notices and the summary inserted after `/compact` are dropped. It attaches `/insights` facets from `~/.claude/usage-data/`, splits Bash commands into signatures, and estimates active time from 5-minute bins with activity.
2. **Label** — Claude gives each session a task type and attaches a *repeat key* (e.g. `commit & push`) to requests that recur on different days. Key names are reused from the last run so changes can be tracked.
3. **Interpret** — Claude writes automation candidates, each linked to repeat keys, commands and `/insights` friction types, so every claim carries a number. Each candidate also gets a concrete design: what triggers it, the steps (marked *auto* or *needs approval*), what it produces, where it lives, what stays with you, and a prompt you can paste into Claude Code to build it. The repeat counts it targets become the baseline for the next run. Everything Claude writes comes in Korean and English.
4. **Render** (`scripts/render.py`) — one HTML file, no external requests. The layout follows newspaper data desks (The Economist chart style, Swiss grid, Tufte's direct labeling): white page, one signal red, square edges, numbered sections, sticky section navigation, light/dark theme.

## Privacy

Everything stays on your machine. The scripts only read local files and write local files; there is no network access. Your transcripts can contain source code, credentials and internal discussions verbatim, so the skill tells Claude not to upload or publish the report anywhere unless you explicitly ask, and to warn you first.

The `.gitignore` keeps report and data folders out of git in case you run the skill inside this repository.

## Limits

- Task types and repeat keys are Claude's labels, so borderline requests can land in a neighboring bucket.
- Active time counts 5-minute bins with any recorded activity: time away is excluded, long autonomous runs are included. It is not working hours.
- `/insights` analyzes a subset of sessions and may not have caught up with the most recent ones; the report shows its coverage.
- Transcript formats can change between Claude Code versions. If counts look off, please open an issue.

## Development

```bash
python3 examples/make_sample.py      # rebuild the synthetic sample reports in examples/
```

## License

MIT
