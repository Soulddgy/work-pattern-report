# Privacy Policy

**work-to-skills** · last updated 2026-10-26 · [한국어](#개인정보-처리방침)

work-to-skills is a Claude Code plugin that runs entirely on your own computer. The author does not run a server and does not collect, receive or store any of your data.

## What it reads

On your computer, when you ask for a report:

- your Claude Code transcripts (`~/.claude/projects/*/*.jsonl`) and per-project memory (`~/.claude/projects/*/memory/`)
- what `/insights` left in `~/.claude/usage-data/`
- the skills and `CLAUDE.md` you already have (`~/.claude/skills/`, and `.claude/skills/` and `CLAUDE.md` in the folders you work in)

Transcripts can contain personal data such as names and email addresses, as well as source code or credentials you pasted into a conversation.

## What it stores

Only in `~/Documents/work-to-skills/` (or a folder you name): the HTML report, its working data (including your prompts, quoted) and the run history. It stays there until you delete it. Deleting that folder removes everything the plugin created.

## What it sends

Nothing. The bundled scripts make no network requests, and the report loads nothing from the internet. To label your requests, Claude reads batches of your prompts inside your Claude Code session, the same way it reads any file you ask it to. That processing is covered by your agreement with Anthropic, not by this plugin.

The skill does not upload or share the report anywhere unless you explicitly ask it to.

## Children

The plugin is not intended for people under 18.

## Changes and contact

Changes to this policy are recorded in this file's history and the [changelog](CHANGELOG.md). Questions: open an issue at https://github.com/Soulddgy/work-to-skills/issues.

---

## 개인정보 처리방침

work-to-skills는 사용자 컴퓨터 안에서만 동작하는 Claude Code 플러그인입니다. 제작자는 서버를 운영하지 않으며, 사용자의 데이터를 수집하거나 받거나 보관하지 않습니다.

- **읽는 것:** 리포트를 요청했을 때, 내 컴퓨터의 Claude Code 대화 기록과 프로젝트별 메모리, `/insights` 분석 결과(`~/.claude/usage-data/`), 이미 만든 스킬과 `CLAUDE.md`. 대화 기록에는 이름·이메일 같은 개인정보나, 대화에 붙여 넣은 코드·인증 정보가 들어 있을 수 있습니다.
- **저장하는 것:** `~/Documents/work-to-skills/`(또는 지정한 폴더)에만 리포트, 중간 데이터(요청 원문 포함), 실행 기록을 저장합니다. 사용자가 지울 때까지 남고, 이 폴더를 지우면 플러그인이 만든 것이 모두 사라집니다.
- **보내는 것:** 없습니다. 스크립트는 네트워크 요청을 하지 않고, 리포트도 인터넷에서 아무것도 불러오지 않습니다. 요청을 분류하려고 Claude가 세션 안에서 요청 묶음을 읽는데, 이 처리는 이 플러그인이 아니라 사용자와 Anthropic 사이의 약관을 따릅니다. 사용자가 직접 요청하지 않는 한 리포트를 어디에도 올리지 않습니다.
- **18세 미만:** 대상으로 하지 않습니다.
- **변경과 문의:** 변경 내역은 이 파일의 기록과 [변경 내역](CHANGELOG.md)에 남습니다. 문의는 https://github.com/Soulddgy/work-to-skills/issues 에 남겨 주세요.
