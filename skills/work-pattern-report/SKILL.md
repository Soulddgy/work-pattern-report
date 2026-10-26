---
name: work-pattern-report
description: Finds the areas of your work where Claude keeps needing the same corrections and the same multi-step flow, and proposes the skills to build for them, the way you'd package a video pipeline into copy / generation / edit / review skills once you notice you keep telling Claude the same rules. Reads your local Claude Code transcripts (~/.claude/projects), what /insights left in ~/.claude/usage-data, and the skills, CLAUDE.md and memory you already have; counts sessions, days, restated rules and repeated requests; and writes a local HTML report (Korean/English) with a proposed skill set per area, the rules to put in it quoted from what you said, and a prompt that builds it. Also lists smaller command/hook automations and, on later runs, whether repeats went down. Use for "what skills should I make", "where should I make a skill", "what do I keep telling Claude", "work pattern report", "find repetitive work", "weekly/monthly retro", "did my skills help", "어떤 스킬을 만들면 좋을까", "내가 무슨 작업 많이 하는지", "작업 패턴 분석", "반복 작업 찾아줘", "자동화할 만한 거", "주간 회고", "지난번보다 줄었나". When someone asks for skill or automation ideas, count their records with this skill instead of answering from memory. Not for git commit statistics or GitHub contribution stats of a single repository.
---

# Work Pattern Report — which skills to build

People who use Claude a lot end up building **work-area skills**: after weeks of making short videos, someone notices they keep telling Claude the same things (which shots are allowed, how captions are worded, how a cut is built, which checks to run before spending credits) and packages that into a set of skills, one per stage of the work. This skill finds where that is worth doing **before** the person notices, from their own records:

1. **Work-area skill candidates — the main output.** An area is a body of work with its own flow and standards (a product's short-form videos, an app's device testing, compliance documents, a resume). An area qualifies when the same multi-step flow ran on many days and the person kept stating the same rules while correcting Claude. For each one the report shows the flow, the rules with their own words and dates, what already exists (skills, CLAUDE.md, memory) and which rules came back after it existed, a proposed set of skills, and a prompt that builds them.
2. **Small automations.** Single mechanical steps asked for again and again (build and copy an artifact, commit and push), as a command, hook or script.
3. Supporting counts: task types, repeated requests, commands Claude ran, `/insights` friction, change since the last run.

Every claim must be backed by a number counted from the records. **Judgment and taste are in scope for area skills**: the point of such a skill is to hold the person's standards so Claude stops needing the same correction. (They are out of scope for small automations.)

**Do not redo what /insights already does.** Session goals, outcomes and friction come straight from its facets, and CLAUDE.md line suggestions are its job.

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
- `compact_summaries_skipped` counts the summaries the system inserts after `/compact`. Excluding them is expected.
- **Is /insights stale?** It is stale when `insights.sessions_with_facets` is 0, when `insights.latest_report_date` is more than 7 days older than the window end, or when `insights.prompts_covered` is under half of `insights.prompts_total`. If so, stop before labeling and ask the user to refresh it first, in their language, for example:

  > /insights 분석이 오래돼서(마지막 실행 2026-10-02, 이번 기간 세션 4/12개만 반영) 먼저 돌려야 합니다. `/insights` 를 입력하신 뒤 "계속"이라고 해 주세요. 지금 데이터로 그냥 만들려면 "그냥 진행"이라고 해 주세요.

  `/insights` only runs when the user types it: it is blocked from the Skill tool, and you must not imitate it some other way (for example through `claude -p`). So ask, then wait for the answer. When they come back after running it, run step 1 again so the new facets are picked up, then continue. If they say to go ahead without it, continue; the report shows the coverage it had.

  If you see `/insights`' own output in the conversation (it ends with an instruction to reply with a fixed message), that reply belongs to the user's `/insights` run. Do not let it replace this report: continue with these steps.

Outputs:
- `sessions.json` — per session: title, prompt count, estimated active time, top tools/commands/skills; with /insights data, `facets` (goal, outcome, friction counts and detail, summary) and `meta` (commits and so on)
- `insights.json` — /insights friction, outcome and satisfaction totals for the window, and its coverage
- `tools.json` — Bash command signatures (`git commit`, `npm test`, `gradlew assemble*`, …), skills, MCP servers
- `stats.json` — prompts per day/week/project, active time, the previous same-length window
- `batches/batch-NN.txt` — prompts to label, grouped by session; each session header has its title and, when /insights analyzed it, an `# insights goal:` line
- `assets.json` — what the person already built where they work: project skills (`<project>/.claude/skills`) and user skills with their creation dates, CLAUDE.md, and memory notes per project with dates

Claude Code deletes transcripts older than `cleanupPeriodDays` (30 by default), so a window longer than that sees only what is left. If the user wants longer history from now on, tell them they can raise that setting.

### 2. Choose work areas and task types

**Work areas (2–6).** Group sessions into the bodies of work they belong to, using titles, `cwd`, project names and `/insights` goals: usually a product or project plus the kind of work, e.g. `brand short-form videos`, `app device testing`, `regulatory documents`, `resume & job search`. One-off sessions get no area. Give each a short id in the user's language.

**Task types.**

Skim the titles and `facets.underlying_goal` / `brief_summary` in `sessions.json` and pick **7–12 task types**. Because /insights already summarized each session's goal, you can usually settle the types before reading every batch.

Name types at the level of "what was the person trying to get done", in their own working vocabulary.
- Good: `device / emulator testing`, `build & release`, `PR, review, merge`, `matching the design spec`, `video generation`, `compliance docs`
- Bad: `Bash work`, `questions`, `misc requests`, `session context`

If one type exceeds 30%, see whether it splits. Give each type a one-line description.

### 3. Label — session default + repeat keys

**First, if the run history exists, read the `repeats` key names of the last entry with the same scope.** Reuse those names for the same work; otherwise the comparison splits one habit into "gone" and "new".

Write `<work folder>/labels/batch-NN.tsv` for each batch, tab-separated:

```
S012	PR, review, merge	app development
p0130	build & release	build debug artifact → Downloads
p0131		ask for a review comment
p0207			no compositing of real product photos
```

- `S###` lines set the session's default type (second column) and its work area (third column, blank for one-offs). Write exactly one for every session; most prompts need nothing more.
- Write a `p####` line only when the prompt is clearly a different type from the session default (second column), gets a repeat key (third column), or states a rule (fourth column). Do not write a line for every prompt.

**Rules (fourth column) drive the area skills.** A rule is a standard the person states about *how* the work in that area must be done: a correction ("the product looks pasted on, don't composite real photos"), a preference ("feed posts are 4:5, no black bars"), a constraint ("don't reuse the same model's face in every video"), a quality bar or a reason for rejecting a result ("there's no action, it's just a zoom — redo"). Write it as a short imperative in the user's language, and give the same rule the same key every time it comes back, on any day. Questions, approvals ("ok, go") and one-time instructions for a single file are not rules.

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

**areas** — the main output. Add this to `analysis.json`:

```json
"areas": [{
  "id": "브랜드 숏폼", "label": {"ko": "브랜드 숏폼 영상", "en": "brand short-form videos"},
  "desc": {"ko": "기획부터 게시까지 숏폼 한 편", "en": "one short video from idea to post"},
  "stages": [{"ko": "기획·카피", "en": "concept & copy"}, {"ko": "AI 영상 생성", "en": "AI video generation"},
             {"ko": "검수", "en": "review"}, {"ko": "편집·빌드", "en": "edit & build"}, {"ko": "게시 문구", "en": "post copy"}],
  "rules": [{"key": "실사 누끼 합성 금지", "text": {"ko": "실사 누끼를 합성하지 않는다", "en": "don't composite cut-out product photos"}}],
  "existing": ["shorts-generate", "shorts-edit"],
  "mode": "extend",
  "skills": [{"name": "shorts-generate", "purpose": {"ko": "…", "en": "…"},
              "contains": [{"ko": "실사 누끼 합성 금지 — 제품 컷은 생성 도구가 그리게", "en": "…"}],
              "triggers": {"ko": "\"이 컷 만들어줘\", \"착용 씬\"", "en": "…"}}],
  "prompt": {"ko": "skill-creator 로 …", "en": "Use skill-creator to …"},
  "note": {"ko": "…", "en": "…"}
}]
```

How to fill it:
- **Which areas.** Rank by days active × distinct rules restated. An area needs work on at least ~3 different days and either ~3 or more rules or a flow of 3+ stages that keeps repeating. List 1–4 areas; an area with nothing to propose stays out.
- **stages** — the flow as it actually ran in those sessions, 3–6 stages, in order.
- **rules** — every rule key of this area that came up on 2+ days, or once with an explicit "always/never". The report counts them, shows the quotes and dates, and marks those that came back after the area's existing skills were created.
- **existing / mode** — look in `assets.json` for skills that cover this area (the project's `.claude/skills`, user skills) and list their exact names; then `mode` is `extend`. Also note CLAUDE.md and memory: a rule that sits in memory or CLAUDE.md but keeps being restated isn't being applied when it matters, and belongs in the skill that is loaded for that stage. With nothing there, `mode` is `new`.
- **skills** — the set to build (`new`) or the changes to make (`extend`). Split a large area by stage when stages differ in inputs, tools or standards (concept & copy / generation / edit / review are separate skills in a video pipeline), and add a small entry skill that routes between them only when there are 3+. Name them `<area>-<stage>` in kebab-case. `contains` lists concrete content — the actual rules by name, file and folder conventions, verified commands or prompt patterns, the checks to run before spending money or time. `triggers` uses phrases the person actually typed. For `extend`, list only skills that change and only what to add.
- **prompt** — one paragraph telling Claude Code to build exactly this with the skill-creator skill: where (`<project>/.claude/skills/`), which skills, what each holds (the rules spelled out), and their triggers. In both languages.

**frictions** — read `facets.friction_counts` and `friction_detail` in `sessions.json` and describe the 2–4 most frequent friction types of this window, in both languages. Keep `type` as /insights' key (the report adds the count). `examples` are short restatements of what `friction_detail` actually says; don't invent new ones.

**Small automations** (`candidates`) come after the areas and are deliberately narrower: one mechanical step or chain, as a command, hook or script. Leave out anything an area skill already covers, and keep this list short (0–4).

**How to pick small automations.** Someone reading the report should be able to decide what to build next.
- Every candidate needs evidence. Link counts through `repeat_keys` or `commands`; leave out candidates without numbers. The report quotes the user's own words from the linked repeat keys, so the link is also the quote.
- Add `friction_types` when the candidate addresses a friction; the report counts that friction across the sessions where the linked repeats occurred.
- Weigh **days** above raw count. Ten times in one day can be one task being reworked; five different days is a habit.
- Work whose core is judgment or taste (planning, copy, design decisions) is not a candidate. Look at the mechanical steps around it (file housekeeping, spec checks, upload prep). If the fix for such friction is a habit like "write a brief first", /insights already suggests it, so don't repeat it here.
- Check for overlap with what exists: `~/.claude/skills/`, the project's `.claude/skills/` and `CLAUDE.md`, scheduled routines. If it overlaps, write "extend X" instead of "build new". If a previous candidate was already built, say in the observations whether its repeat went down in the comparison table.
- `effort` is how much it takes to build: `S` one file, under an hour (a hook, a short script, a skill with fixed steps); `M` half a day to a day, a few places touched (a skill tying several tools together, extending an existing skill); `L` days, or needs design or team agreement (CI changes, cross-repo work). The report spells these out in words.
- `type` is the form it would take: skill, hook, script, scheduled routine, CI, or a settings change. If a step must keep human approval (commit, merge, publishing), say "keeps the approval step" in `approach`.
- At most 4, highest payoff first.

**Make each candidate buildable, not just a direction.** The reader should be able to copy the prompt and get a working automation. Fill these for every candidate:
- `trigger` — what starts it: a command the user types (`/name`), a hook event (`PreToolUse` on `git commit`, `Stop`, …), a schedule, or CI on push/PR.
- `steps` — 2–6 concrete steps in order, using the real commands, paths and tools seen in `tools.json` and the transcripts (`gradlew assembleDebug`, `adb install`, the actual notes folder) rather than generic verbs. Mark any step that must stay a human decision with `"manual": true` (commit, merge, choosing a device, publishing); the report tags it "needs approval".
- `output` — what the user gets at the end, so they can tell it worked.
- `where` — the file it would live in (`~/.claude/skills/<name>/SKILL.md`, a hooks entry in Claude Code settings, a project `.claude/`, a script path).
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
- the work-area skill candidates, one line each: the area, sessions and days, how many rules kept coming back, and the proposed skills (or what to add to existing ones)
- the top small automations in one line
- any repeat that changed a lot since last run, in one line
- the full path of the report file
- one thing worth building next, as an offer; don't build it unprompted
