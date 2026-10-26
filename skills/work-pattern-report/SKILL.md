---
name: work-pattern-report
description: A companion to Claude Code's built-in /insights. Reads your local Claude Code transcripts (~/.claude/projects) and the per-session analysis /insights leaves in ~/.claude/usage-data, counts how often you asked for the same thing and on how many days, which commands Claude actually ran, and where sessions got stuck, then turns those counts into automation candidates in a local HTML report (Korean or English). On later runs it shows whether those repeats went down. Use it for "what do I spend my Claude time on", "find repetitive work I could automate", "work pattern report", "weekly/monthly retro", "did that skill actually reduce my repeats", "insights in Korean", "내가 무슨 작업 많이 하는지", "작업 패턴 분석", "반복 작업 찾아줘", "자동화할 만한 거", "주간 회고", "지난번보다 줄었나". When someone asks for automation ideas, count their records with this skill instead of answering from memory. Not for git commit statistics or GitHub contribution stats of a single repository.
---

# Work Pattern Report (an /insights companion)

`/insights` summarizes each session's goal, outcome and friction well, but it does not count **how many times, on how many days, you asked for the same thing**, or **which commands Claude actually ran**. This skill counts both, folds in the /insights analysis, and renders one local HTML page.

The point is to decide what to automate from **counts**, not impressions, and to check on the next run whether an automation actually reduced the repeats. Every claim in the report must be backed by a number counted from the records.

**Do not redo what /insights already does.** Session goals, outcomes and friction come straight from its facets. CLAUDE.md suggestions are its job too. This skill focuses on repeats, commands, change over time, and the automation candidates those support.

## Language

The report file holds both a Korean and an English version with a toggle in the navigation bar, and opens in the language the user is talking to you in. Set `"lang": "ko"` or `"lang": "en"` in `analysis.json` for that first language.

The fixed text (menus, headings, column names) is built in. Everything you write has to come in both languages, or the other version shows the wrong language. So write every display text in `analysis.json` as `{"ko": "...", "en": "..."}`: category labels and descriptions, repeat-key labels and descriptions, friction titles, descriptions and examples, every candidate field, and every observation. Task types and repeat keys in the label files are **ids**; keep them in the user's language (they are what the run history matches on) and put the translations in `label`. Quotes of what the user said, session titles and commands are shown as they are, in either version.

## Privacy

Transcripts can contain source code, credentials, internal emails and security findings verbatim. Keep the report and intermediate files **on the user's machine**. Do not publish, upload or send them anywhere (artifact hosts, note apps, chat tools, APIs) unless the user asks for that specific report to go to a specific place, and even then point out the risk first.

## Defaults

| Item | Default | How the user changes it |
|---|---|---|
| Window | last 30 days including today | "this week", "October only", "everything" |
| Scope | all projects | "only my-app", "skip the blog" |
| Report | `~/Documents/work-pattern-report/report_<since>_<until>.html` | any path they name |
| Work folder | `~/Documents/work-pattern-report/data/<since>_<until>/` | — |
| Run history | `~/Documents/work-pattern-report/history.json` | — |

"Everything" is `--since 2020-01-01`. A project filter is `--project` with part of the project directory name (for example `my-app`). For "skip X", extract everything, ignore X while labeling and interpreting, and say so in the observations.

## Steps

### 1. Extract

```bash
python3 <skill-dir>/scripts/extract.py --out <work folder> [--days 30 | --since YYYY-MM-DD --until YYYY-MM-DD] [--project NAME]
```

`<skill-dir>` is the folder this SKILL.md is in. Python 3.9+ standard library only.

Check three things in the last line of JSON:
- `prompts` is 0: re-check the window and tell the user.
- `insights.sessions_with_facets` is 0, or `insights.latest_report_date` is more than 7 days older than the window end: tell the user in one line that running `/insights` first adds friction analysis. /insights is a built-in command only the user can type, so you cannot run it for them. Don't wait; carry on, and the report shows a note in that section instead.
- `compact_summaries_skipped` counts the summaries the system inserts after `/compact`. Excluding them is expected.

Outputs:
- `sessions.json` — per session: title, prompt count, estimated active time, top tools/commands/skills; with /insights data, `facets` (goal, outcome, friction counts and detail, summary) and `meta` (commits and so on)
- `insights.json` — /insights friction, outcome and satisfaction totals for the window, and its coverage
- `tools.json` — Bash command signatures (`git commit`, `npm test`, `gradlew assemble*`, …), skills, MCP servers
- `stats.json` — prompts per day/week/project, active time, the previous same-length window
- `batches/batch-NN.txt` — prompts to label, grouped by session; each session header has its title and, when /insights analyzed it, an `# insights goal:` line

### 2. Choose task types

Skim the titles and `facets.underlying_goal` / `brief_summary` in `sessions.json` and pick **7–12 task types**. Because /insights already summarized each session's goal, you can usually settle the types before reading every batch.

Name types at the level of "what was the person trying to get done", in their own working vocabulary.
- Good: `device / emulator testing`, `build & release`, `PR, review, merge`, `matching the design spec`, `video generation`, `compliance docs`
- Bad: `Bash work`, `questions`, `misc requests`, `session context`

If one type exceeds 30%, see whether it splits. Give each type a one-line description.

### 3. Label — session default + repeat keys

**First, if the run history exists, read the `repeats` key names of the last entry with the same scope.** Reuse those names for the same work; otherwise the comparison splits one habit into "gone" and "new".

Write `<work folder>/labels/batch-NN.tsv` for each batch, tab-separated:

```
S012	PR, review, merge
p0130	build & release	build debug artifact → Downloads
p0131		ask for a review comment
```

- `S###` lines set the session's default type. Write exactly one for every session; most prompts need nothing more.
- Write a `p####` line only when the prompt is clearly a different type from the session default (second column), or when it gets a repeat key (third column). Do not write a line for every prompt; it costs tokens and changes nothing.

**Repeat keys are the core of this report.** When a request with the same intent comes back on another day or in another session, give it the same key.
- Name them as short "action → result" phrases, e.g. `build debug artifact → Downloads`, `commit & push`, `update the notes app`, `ask for a review comment`, `install on test device`, `log in with the test account`.
- Attach them to prompts that **ask for** the work, not to prompts that discuss it. One exception: when the user re-asks or checks on something Claude should already have done ("did you update the notes?", "you log in, don't ask me"), that prompt gets a key too. It is the strongest signal that the work is not automated yet.
- Don't key one-off work. If a second occurrence shows up later, go back and key the first.
- Keep key names stable across batches.

With six batches or fewer, label them yourself in order. With more, if you split them across subagents, pass the task types and the current key list (including the history's keys) to each, and unify the key names once when they return.

### 4. Interpret — `analysis.json`

Run the renderer once without `--history` (so nothing is recorded) to see counts and days per key, then write:

```json
{
  "lang": "ko",
  "categories": [{"name": "빌드·배포", "label": {"ko": "빌드·배포", "en": "build & release"},
                  "desc": {"ko": "빌드, 설치, 릴리즈 준비", "en": "building artifacts, installing, release prep"}}],
  "repeats": [{"key": "debug 빌드 → Downloads", "label": {"ko": "debug 빌드 → Downloads", "en": "debug build → Downloads"},
               "desc": {"ko": "빌드 후 ~/Downloads 복사, 이전 파일 정리", "en": "build, copy to ~/Downloads, delete the old one"}}],
  "frictions": [{"type": "wrong_approach",
                 "title": {"ko": "방향을 정하기 전에 만들기 시작함", "en": "Started building before the goal was clear"},
                 "desc": {"ko": "게시물 역할을 정하기 전에 시안부터 만들어 라운드가 늘었다",
                          "en": "Drafts were made before the post's role was agreed, which added rounds"},
                 "examples": [{"ko": "SNS 게시물: 기존 공지와 중복, 결국 '기획부터 다시'",
                               "en": "Social post: duplicated an earlier announcement, ended in 'start the plan over'"}]}],
  "candidates": [{
    "title": {"ko": "빌드·설치 한 번에", "en": "One command to build and install"},
    "problem": {"ko": "빌드, 복사, 이전 파일 정리, 설치를 매번 따로 시킨다",
                "en": "Build, copy, clean-up and install are asked for separately every time"},
    "approach": {"ko": "/ship-build 스킬: 툴체인 설정, 빌드, 날짜 붙여 복사, 이전 파일 정리, 기기 설치",
                 "en": "a /ship-build skill: set the toolchain, build, copy with a date suffix, prune old copies, install"},
    "type": {"ko": "스킬", "en": "skill"}, "effort": "S",
    "repeat_keys": ["debug 빌드 → Downloads", "테스트 기기에 설치"],
    "commands": ["gradlew assemble*", "adb install"],
    "friction_types": [],
    "trigger": {"ko": "직접 부르는 명령 /ship-build", "en": "a command you run: /ship-build"},
    "steps": [
      {"text": {"ko": "JAVA_HOME 설정 후 gradlew assembleDebug", "en": "set JAVA_HOME, run gradlew assembleDebug"}},
      {"text": {"ko": "APK를 날짜 붙여 ~/Downloads 로 복사, 이전 것 삭제", "en": "copy the APK to ~/Downloads with a date suffix, delete the old one"}},
      {"text": {"ko": "연결된 기기 확인 후 adb install", "en": "check the connected device, adb install"}, "manual": true}
    ],
    "output": {"ko": "~/Downloads 의 APK 한 개와 설치 결과 한 줄", "en": "one APK in ~/Downloads and a one-line install result"},
    "where": "~/.claude/skills/ship-build/SKILL.md",
    "keep_manual": {"ko": "어느 기기에 설치할지 고르기, release 빌드", "en": "choosing the device; release builds"},
    "prompt": {"ko": "~/.claude/skills/ship-build 에 /ship-build 스킬을 만들어줘. 순서: JAVA_HOME 설정 → gradlew assembleDebug → APK 를 날짜 붙여 ~/Downloads 로 복사하고 이전 APK 삭제 → 연결된 기기 목록을 보여주고 내가 고르면 adb install. release 빌드는 하지 마.",
               "en": "Create a /ship-build skill in ~/.claude/skills/ship-build. Steps: set JAVA_HOME → gradlew assembleDebug → copy the APK to ~/Downloads with a date suffix and delete the previous one → list connected devices and adb install on the one I pick. Never build release."},
    "note": {"ko": "기존 git-workflow 스킬과 겹치지 않음", "en": "does not overlap the existing git-workflow skill"}
  }],
  "observations": [{"ko": "요청의 45%가 10/19 주에 몰렸다", "en": "45% of prompts fell in the week of 10/19"}]
}
```

**frictions** — read `facets.friction_counts` and `friction_detail` in `sessions.json` and describe the 2–4 most frequent friction types of this window, in both languages. Keep `type` as /insights' key (the report adds the count). `examples` are short restatements of what `friction_detail` actually says; don't invent new ones.

**How to pick automation candidates.** Someone reading the report should be able to decide what to build next.
- Every candidate needs evidence. Link counts through `repeat_keys` or `commands`; leave out candidates without numbers. The report quotes the user's own words from the linked repeat keys, so the link is also the quote.
- Add `friction_types` when the candidate addresses a friction; the report counts that friction across the sessions where the linked repeats occurred.
- Weigh **days** above raw count. Ten times in one day can be one task being reworked; five different days is a habit.
- Work whose core is judgment or taste (planning, copy, design decisions) is not a candidate. Look at the mechanical steps around it (file housekeeping, spec checks, upload prep). If the fix for such friction is a habit like "write a brief first", /insights already suggests it, so don't repeat it here.
- Check for overlap with what exists: `~/.claude/skills/`, hooks in `~/.claude/settings.json`, the project's `.claude/`, scheduled routines. If it overlaps, write "extend X" instead of "build new". If a previous candidate was already built, say in the observations whether its repeat went down in the comparison table.
- `effort` is how much it takes to build: `S` one file, under an hour (a hook, a short script, a skill with fixed steps); `M` half a day to a day, a few places touched (a skill tying several tools together, extending an existing skill); `L` days, or needs design or team agreement (CI changes, cross-repo work). The report spells these out in words.
- `type` is the form it would take: skill, hook, script, scheduled routine, CI, or a settings change. If a step must keep human approval (commit, merge, publishing), say "keeps the approval step" in `approach`.
- 3–6 candidates, highest payoff first.

**Make each candidate buildable, not just a direction.** The reader should be able to copy the prompt and get a working automation. Fill these for every candidate:
- `trigger` — what starts it: a command the user types (`/name`), a hook event (`PreToolUse` on `git commit`, `Stop`, …), a schedule, or CI on push/PR.
- `steps` — 2–6 concrete steps in order, using the real commands, paths and tools seen in `tools.json` and the transcripts (`gradlew assembleDebug`, `adb install`, the actual notes folder) rather than generic verbs. Mark any step that must stay a human decision with `"manual": true` (commit, merge, choosing a device, publishing); the report tags it "needs approval".
- `output` — what the user gets at the end, so they can tell it worked.
- `where` — the file it would live in (`~/.claude/skills/<name>/SKILL.md`, `~/.claude/settings.json` hooks, a project `.claude/`, a script path).
- `keep_manual` — what deliberately stays with the person.
- `prompt` — a ready-to-paste request that tells Claude Code to build exactly this: name, location, steps in order, the approval points, and what it must never do. One paragraph, in both languages.

The success check is generated from `repeat_keys`: the report shows today's count and days as the baseline to beat in the next run, so link the keys the automation should make disappear.

`observations`: 3–6 facts the numbers show, such as a week that dominated, a project's share changing, a type with long active time, a repeat that rose or fell sharply since last run. Put advice in the candidates, not here.

### 5. Render and open

```bash
python3 <skill-dir>/scripts/render.py --work <work folder> --output <report.html> --history <run history>
open <report.html>        # macOS; use xdg-open on Linux, start on Windows
```

- With `--history`, the run is compared with the previous run of the same scope (project filter), then appended. Re-running the same window replaces that entry.
- If the output JSON shows `unlabeled` above 0, a session default is missing. Fill it and render again.

### 6. Report in chat

Don't paste the report into chat. Say briefly:
- window and size (prompts, active time, sessions) and /insights coverage
- the top 2–3 task types and their share
- the top 3 automation candidates, one line each, with their numbers
- any repeat that changed a lot since last run, in one line
- the full path of the report file
- one thing worth building next, as an offer; don't build it unprompted
