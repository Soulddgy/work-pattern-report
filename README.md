# work-to-skills

**Version 0.3.1** (2026-10-26) · [Changelog](CHANGELOG.md) · MIT · **English** · [한국어](README_KO.md)

A Claude Code plugin that reads your own Claude Code history and tells you **which areas of your work deserve a skill**.

Use Claude long enough and you keep saying the same things for the same kind of work. Make short videos for a few weeks and you find yourself repeating "don't composite real photos", "feed posts are 4:5", "a zoom with no action is a redo" on different days, until you finally package it into concept, generation, edit and review skills. This plugin **finds that point in your records for you.**

![Sample report (synthetic data)](https://raw.githubusercontent.com/Soulddgy/work-to-skills/assets/screenshot-en.png)

## What's in the report

1. **Work-area skill candidates** (the main output)
   - Areas where you ran the same flow on many days and kept restating the same rules while correcting the work
   - For each one: the flow, the rules you built up (in your own words, with dates), the skills, CLAUDE.md and memory you already have, **rules that came back after those skills existed**, a proposed set of skills, and a **build prompt** you can paste to have Claude create them
   - Where skills already exist, it proposes what to add instead of building new ones
2. **Small automations**: mechanical steps you ask for every time (build and copy, commit and push) as a command, hook or script
3. **Since last run**: whether each repeated request went up or down
4. Task types, repeated requests, `/insights` friction, week by week, commands Claude actually ran, prompts per day and project, longest sessions

The report is one file that works offline. Switch between Korean and English in the top bar; sections and blocks fold and unfold (build prompts start unfolded).

## How it differs from `/insights`

| | `/insights` | work-to-skills |
|---|---|---|
| Session goals, outcomes, friction | ✅ | reused from `/insights` |
| Which areas need which skills | — | ✅ with rules, flow and a build prompt |
| Rules missing from skills you already built | — | ✅ rules restated after each skill's creation date |
| How many times, on how many days, you asked for the same thing | — | ✅ |
| Which commands Claude actually ran | tool names only | ✅ command level |
| Report language | English | Korean / English toggle |

## Install

```text
/plugin marketplace add Soulddgy/work-to-skills
/plugin install work-to-skills@work-to-skills
```

Requirements: Claude Code and Python 3.9+.

The "Where things got stuck" section uses the `/insights` analysis. If it is stale (last run more than a week ago, or covering less than half of the window), the skill stops before building the report and asks you to **run `/insights` first**. `/insights` only runs when you type it, so the skill cannot run it for you. Say "continue" after running it, or "go ahead" to build the report with what is there.

## Use

Ask in your own words:

- "Which parts of my work should I make skills for?"
- "What do I keep telling Claude? Include what my existing skills are missing."
- "Only my-app, October."
- "Compare the last two weeks with the two weeks before. Did the repeats go down?"

Results go to `~/Documents/work-to-skills/`. To preview one first, download and open [`examples/sample-report.en.html`](examples/sample-report.en.html) (made-up data).

## Privacy and what it accesses

Everything is processed on your machine. Transcripts can contain source code and internal discussions verbatim, so the skill never uploads or publishes the report unless you explicitly ask.

| | |
|---|---|
| **Reads** | `~/.claude/projects/*/*.jsonl` (your Claude Code transcripts) and per-project memory (`~/.claude/projects/*/memory/`), `~/.claude/usage-data/` (what `/insights` left), and to see what you already built: `~/.claude/skills/`, plus `.claude/skills/` and `CLAUDE.md` in the folders you work in. It does not read settings or credential files |
| **Writes** | only `~/Documents/work-to-skills/` (the report, its working data and the run history), or a folder you name |
| **Runs** | the two bundled Python scripts (`extract.py`, `render.py`, standard library only), and your system's `open` / `xdg-open` / `start` to show the report |
| **Network** | none. The scripts make no network requests, and the report loads nothing from the internet |
| **Through Claude** | to label your requests, Claude reads batches of your prompts in the session, the same way it reads any file you ask it to |
| **Doesn't** | build the skills for you (it gives you the build prompt), install hooks, MCP servers or packages, change settings, or keep anything outside the folders above |

## Good to know

- **Areas, categories and rules are Claude's judgment.** Claude reads your prompts and decides which area they belong to and what counts as a rule. Read the numbers for **size and order**, not exact values.
- **History is kept for 30 days by default.** Claude Code deletes transcripts older than `cleanupPeriodDays` (30 by default). Raise that setting if you want longer windows later.
- **Active time is not working hours.** Only time with recorded conversation activity counts: time away is left out, and long stretches where Claude worked alone are included.
- **Friction only covers sessions `/insights` analyzed.** The skill asks you to refresh it when it is stale, and the report shows its coverage.
- **It uses a fair number of tokens.** Claude reads and labels your history: a month of one project takes roughly 150k–200k tokens per run. A narrower window or project costs less.
- **Claude Code updates can throw the counts off.** If the transcript format changes, some messages may be missed or miscounted. Please open an issue if numbers look wrong.
