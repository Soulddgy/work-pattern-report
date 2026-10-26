#!/usr/bin/env python3
"""Build a synthetic work folder (no real transcripts) and render sample reports in Korean and English.

The persona is a solo web developer who also writes a blog. Everything here is made up so the
README can show the report without exposing anyone's conversations.

Usage: python3 examples/make_sample.py   (writes examples/sample-report.{ko,en}.html)
"""
import datetime as dt
import json
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.join(HERE, "..", "skills", "work-pattern-report", "scripts", "render.py")
KST = dt.timezone(dt.timedelta(hours=9))
UNTIL = dt.date(2026, 10, 26)
DAYS = 28
SINCE = UNTIL - dt.timedelta(days=DAYS - 1)

# (session title, project, type key, [(prompt text, repeat key or None[, rule key])], insights facets or None)
SESSIONS = [
    ("Checkout page bug", "shop-web", "fix",
     [("the coupon total is wrong on checkout, can you look", None),
      ("don't touch the payment provider config, fix it on our side", None, "never touch payment config"),
      ("run the tests", "run tests"),
      ("commit and push", "commit & push"), ("deploy to staging", "deploy to staging"),
      ("did you update the changelog?", "update changelog")],
     {"friction_counts": {"buggy_code": 2}, "outcome": "mostly_achieved",
      "user_satisfaction_counts": {"likely_satisfied": 3, "dissatisfied": 1}}),
    ("Product list filters", "shop-web", "feature",
     [("add a price filter to the product list", None), ("match the figma spacing", "match design spec"),
      ("use the design tokens, no hard-coded colors", None, "design tokens only"),
      ("run the tests", "run tests"), ("commit and push", "commit & push"), ("open a PR", "open PR & request review")],
     {"friction_counts": {"misunderstood_request": 1}, "outcome": "fully_achieved",
      "user_satisfaction_counts": {"satisfied": 2, "likely_satisfied": 2}}),
    ("Weekly blog post", "blog", "writing",
     [("draft this week's post about caching", None),
      ("the intro is too long again, three sentences max", None, "intro in three sentences"),
      ("only show code you actually ran", None, "only tested code"),
      ("export the cover image at 1200x630", "export cover image"),
      ("no text on the cover", None, "cover without text")],
     {"friction_counts": {"wrong_approach": 2, "excessive_changes": 1}, "outcome": "mostly_achieved",
      "user_satisfaction_counts": {"dissatisfied": 2, "likely_satisfied": 2}}),
    ("Staging deploy failed", "shop-web", "release",
     [("staging deploy failed again", None), ("deploy to staging", "deploy to staging"),
      ("check the server logs", "check server logs"), ("commit and push", "commit & push")],
     {"friction_counts": {"tool_errors": 1, "wrong_approach": 1}, "outcome": "partially_achieved",
      "user_satisfaction_counts": {"frustrated": 1, "likely_satisfied": 2}}),
    ("Search API", "shop-api", "feature",
     [("add pagination to the search endpoint", None), ("run the tests", "run tests"),
      ("open a PR", "open PR & request review"), ("did you update the changelog?", "update changelog")],
     None),
]
AREA = {"fix": "shop", "feature": "shop", "release": "shop", "writing": "blog"}
TEXT_KO = {
    "don't touch the payment provider config, fix it on our side": "결제사 설정은 건드리지 말고 우리 쪽에서 고쳐",
    "use the design tokens, no hard-coded colors": "디자인 토큰 써, 색 하드코딩하지 말고",
    "the intro is too long again, three sentences max": "도입부 또 길다, 세 문장 넘기지 마",
    "only show code you actually ran": "직접 돌려 본 코드만 넣어",
    "no text on the cover": "표지에 글자 넣지 마",
    "the coupon total is wrong on checkout, can you look": "결제 화면에서 쿠폰 합계가 틀려, 좀 봐줄래",
    "run the tests": "테스트 돌려줘", "commit and push": "커밋하고 푸시해", "deploy to staging": "스테이징에 배포해줘",
    "did you update the changelog?": "체인지로그 갱신했어?", "add a price filter to the product list": "상품 목록에 가격 필터 추가해줘",
    "match the figma spacing": "피그마 여백대로 맞춰줘", "open a PR": "PR 열어줘",
    "draft this week's post about caching": "이번 주 캐싱 글 초안 써줘", "make the intro shorter": "도입부 좀 줄여줘",
    "export the cover image at 1200x630": "표지 이미지 1200x630으로 뽑아줘", "staging deploy failed again": "스테이징 배포 또 실패했어",
    "check the server logs": "서버 로그 확인해줘", "add pagination to the search endpoint": "검색 API에 페이지네이션 넣어줘",
}
TYPES = {
    "ko": {"fix": ("버그 수정", "결제·화면 오류 고치기"), "feature": ("기능 개발", "새 화면·API"),
           "writing": ("블로그 글쓰기", "초안, 퇴고, 표지 이미지"), "release": ("배포·운영", "스테이징 배포, 로그 확인")},
    "en": {"fix": ("bug fixing", "checkout and UI defects"), "feature": ("feature work", "new screens and APIs"),
           "writing": ("blog writing", "drafts, edits, cover images"), "release": ("deploy & ops", "staging deploys, logs")},
}
KEYS = {
    "ko": {"run tests": "테스트 실행", "commit & push": "커밋·푸시", "deploy to staging": "스테이징 배포",
           "update changelog": "체인지로그 갱신 확인", "match design spec": "디자인 시안 맞추기",
           "open PR & request review": "PR 열고 리뷰 요청", "export cover image": "표지 이미지 내보내기",
           "check server logs": "서버 로그 확인"},
    "en": {k: k for k in ["run tests", "commit & push", "deploy to staging", "update changelog", "match design spec",
                          "open PR & request review", "export cover image", "check server logs"]},
}
ANALYSIS = {
    "ko": {
        "frictions": [{"type": "wrong_approach", "title": "방향을 정하기 전에 만들기 시작함",
                       "desc": "블로그 초안과 표지를 목적을 정하기 전에 만들어 수정 라운드가 늘었다",
                       "examples": ["캐싱 글: 독자를 정하기 전에 초안을 써서 도입부를 세 번 다시 씀"]}],
        "candidates": [
            {"title": "커밋부터 스테이징 배포까지 한 번에", "problem": "테스트, 커밋·푸시, 스테이징 배포를 매번 따로 시킨다",
             "approach": "/ship 스킬: 테스트 → 커밋(승인 단계 유지) → 푸시 → 스테이징 배포 → 로그 확인", "type": "스킬",
             "effort": "S", "repeat_keys": ["커밋·푸시", "스테이징 배포", "테스트 실행"], "commands": ["npm test", "git push"],
             "friction_types": ["tool_errors"]},
            {"title": "체인지로그 누락 알림 hook", "problem": "체인지로그를 갱신했는지 매번 직접 확인한다",
             "approach": "커밋 직전에 CHANGELOG.md 변경이 없으면 알려 주는 hook", "type": "hook", "effort": "S",
             "repeat_keys": ["체인지로그 갱신 확인"], "commands": [], "friction_types": []},
            {"title": "표지 이미지 규격 내보내기", "problem": "글마다 표지를 1200x630으로 따로 요청한다",
             "approach": "글 폴더의 cover.png를 규격에 맞춰 내보내는 스크립트", "type": "스크립트", "effort": "S",
             "repeat_keys": ["표지 이미지 내보내기"], "commands": [], "friction_types": []}],
        "observations": ["요청의 60%가 shop-web 에서 나왔다", "커밋·푸시는 4주 동안 매주 나왔다"],
    },
    "en": {
        "frictions": [{"type": "wrong_approach", "title": "Started building before the direction was set",
                       "desc": "Blog drafts and covers were made before the purpose was agreed, adding rounds",
                       "examples": ["Caching post: drafted before choosing the audience, intro rewritten three times"]}],
        "candidates": [
            {"title": "From commit to staging in one go", "problem": "Tests, commit & push and the staging deploy are asked for separately every time",
             "approach": "a /ship skill: tests → commit (keeps the approval step) → push → staging deploy → log check", "type": "skill",
             "effort": "S", "repeat_keys": ["commit & push", "deploy to staging", "run tests"], "commands": ["npm test", "git push"],
             "friction_types": ["tool_errors"]},
            {"title": "Changelog reminder hook", "problem": "You check by hand whether the changelog was updated",
             "approach": "a hook that warns before a commit when CHANGELOG.md is unchanged", "type": "hook", "effort": "S",
             "repeat_keys": ["update changelog"], "commands": [], "friction_types": []},
            {"title": "Cover image export", "problem": "Every post needs a separate request for a 1200x630 cover",
             "approach": "a script that exports the post folder's cover.png at the right size", "type": "script", "effort": "S",
             "repeat_keys": ["export cover image"], "commands": [], "friction_types": []}],
        "observations": ["60% of prompts came from shop-web", "commit & push showed up every week for four weeks"],
    },
}
COMMANDS = {"npm test": 64, "git push": 31, "git commit": 29, "gh pr": 18, "npm run": 40, "docker compose": 12,
            "curl": 22, "node": 15, "grep": 300, "sed": 120, "cat": 90}


def bi(ko, en):
    """Pair a Korean and an English text the way analysis.json expects; lists are paired item by item."""
    if isinstance(ko, list):
        return [bi(x, y) for x, y in zip(ko, en)]
    return {"ko": ko, "en": en}


# How each candidate would actually be built; already paired, since these are written for the sample only.
DESIGN = [
    {"trigger": {"ko": "직접 부르는 명령 /ship", "en": "a command you run: /ship"},
     "steps": [{"text": {"ko": "npm test 실행, 실패하면 멈춤", "en": "run npm test, stop on failure"}},
               {"text": {"ko": "변경 요약을 보여 주고 커밋 메시지 확인", "en": "show the change summary and confirm the commit message"}, "manual": True},
               {"text": {"ko": "git push", "en": "git push"}},
               {"text": {"ko": "스테이징 배포 후 서버 로그에서 오류 확인", "en": "deploy to staging, then scan the server logs for errors"}}],
     "output": {"ko": "스테이징 URL과 로그 요약 한 줄", "en": "the staging URL and a one-line log summary"},
     "where": "~/.claude/skills/ship/SKILL.md",
     "keep_manual": {"ko": "커밋 메시지 승인, 운영 배포", "en": "approving the commit message; production deploys"},
     "prompt": {"ko": "~/.claude/skills/ship 에 /ship 스킬을 만들어줘. 순서: npm test(실패하면 멈춤) → 변경 요약을 보여주고 커밋 메시지를 나한테 확인 → git push → 스테이징 배포 → 서버 로그에서 오류만 요약. 운영 배포는 절대 하지 마.",
                "en": "Create a /ship skill in ~/.claude/skills/ship. Steps: npm test (stop on failure) → show me the change summary and confirm the commit message → git push → deploy to staging → summarize only errors from the server logs. Never deploy to production."}},
    {"trigger": {"ko": "커밋 직전 hook (PreToolUse: git commit)", "en": "a hook before commits (PreToolUse: git commit)"},
     "steps": [{"text": {"ko": "staged 파일에 CHANGELOG.md 가 있는지 확인", "en": "check whether CHANGELOG.md is staged"}},
               {"text": {"ko": "없으면 경고하고 커밋을 멈춤", "en": "if not, warn and stop the commit"}}],
     "output": {"ko": "경고 한 줄", "en": "a one-line warning"},
     "where": "~/.claude/settings.json → hooks",
     "keep_manual": {"ko": "체인지로그 문구 쓰기", "en": "writing the changelog entry itself"},
     "prompt": {"ko": "git commit 직전에 CHANGELOG.md 가 staged 됐는지 확인하고, 아니면 경고하고 멈추는 PreToolUse hook 을 ~/.claude/settings.json 에 추가해줘.",
                "en": "Add a PreToolUse hook to ~/.claude/settings.json that checks whether CHANGELOG.md is staged before git commit, and warns and stops if it is not."}},
    {"trigger": {"ko": "직접 실행하는 스크립트", "en": "a script you run"},
     "steps": [{"text": {"ko": "글 폴더의 cover.png 를 찾음", "en": "find cover.png in the post folder"}},
               {"text": {"ko": "1200x630 으로 잘라 cover-og.png 로 저장", "en": "crop to 1200x630 and save as cover-og.png"}}],
     "output": {"ko": "cover-og.png", "en": "cover-og.png"},
     "where": "blog/scripts/export-cover.sh",
     "keep_manual": {"ko": "표지 디자인", "en": "designing the cover"},
     "prompt": {"ko": "blog/scripts/export-cover.sh 를 만들어줘. 인자로 글 폴더를 받아 cover.png 를 1200x630 으로 가운데 잘라 cover-og.png 로 저장해.",
                "en": "Create blog/scripts/export-cover.sh. It takes a post folder, center-crops cover.png to 1200x630 and saves it as cover-og.png."}},
]


AREAS = [
    {"id": "blog", "label": {"ko": "블로그 글쓰기", "en": "Blog writing"},
     "desc": {"ko": "주제부터 게시까지 한 편", "en": "one post from topic to publish"},
     "stages": [{"ko": "주제·개요", "en": "topic & outline"}, {"ko": "초안", "en": "draft"},
                {"ko": "코드 예시 확인", "en": "check code samples"}, {"ko": "표지", "en": "cover"},
                {"ko": "게시", "en": "publish"}],
     "rules": [{"key": "intro in three sentences", "text": {"ko": "도입부는 세 문장 이내", "en": "intro in three sentences or fewer"}},
               {"key": "cover without text", "text": {"ko": "표지에 글자를 넣지 않는다", "en": "no text on the cover"}},
               {"key": "only tested code", "text": {"ko": "직접 실행해 본 코드만 싣는다", "en": "only publish code that was run"}}],
     "existing": ["blog-post"], "mode": "extend",
     "skills": [{"name": "blog-post", "purpose": {"ko": "초안 단계에 빠진 규칙 추가", "en": "add the rules missing from the draft stage"},
                 "contains": [{"ko": "도입부 세 문장 이내", "en": "intro in three sentences or fewer"},
                              {"ko": "코드 블록은 실행 결과를 붙인 것만", "en": "code blocks only with their run output"}],
                 "triggers": {"ko": "\"이번 주 글\", \"초안 써줘\"", "en": "\"this week's post\", \"draft\""}},
                {"name": "blog-cover", "purpose": {"ko": "표지 이미지 규격과 금지 사항", "en": "cover image size and don'ts"},
                 "contains": [{"ko": "1200x630, 글자 없이", "en": "1200x630, no text"}],
                 "triggers": {"ko": "\"표지\", \"커버 이미지\"", "en": "\"cover\", \"cover image\""}}],
     "prompt": {"ko": "skill-creator 로 ~/blog/.claude/skills 의 blog-post 스킬에 '도입부 세 문장 이내', '코드 블록은 실행 결과를 붙인 것만'을 넣고, 표지용 blog-cover 스킬을 새로 만들어줘(1200x630, 글자 없음, \"표지\" \"커버 이미지\" 에 반응).",
                "en": "Use skill-creator to add 'intro in three sentences or fewer' and 'code blocks only with their run output' to the blog-post skill in ~/blog/.claude/skills, and create a blog-cover skill (1200x630, no text; triggers on \"cover\", \"cover image\")."}},
    {"id": "shop", "label": {"ko": "쇼핑몰 웹 개발", "en": "Shop web development"},
     "desc": {"ko": "기능·버그 수정부터 스테이징 배포까지", "en": "features and fixes through to staging"},
     "stages": [{"ko": "구현", "en": "implement"}, {"ko": "시안 맞추기", "en": "match the design"},
                {"ko": "테스트", "en": "test"}, {"ko": "커밋·PR", "en": "commit & PR"}, {"ko": "스테이징 배포", "en": "staging deploy"}],
     "rules": [{"key": "never touch payment config", "text": {"ko": "결제사 설정은 건드리지 않는다", "en": "never touch the payment provider config"}},
               {"key": "design tokens only", "text": {"ko": "색은 디자인 토큰만 쓴다", "en": "colors come from design tokens only"}}],
     "existing": [], "mode": "new",
     "skills": [{"name": "shop-feature", "purpose": {"ko": "구현과 시안 맞추기 기준", "en": "standards for building and matching the design"},
                 "contains": [{"ko": "색은 디자인 토큰만", "en": "colors from design tokens only"},
                              {"ko": "결제사 설정 수정 금지", "en": "no changes to payment provider config"}],
                 "triggers": {"ko": "\"기능 추가\", \"시안대로\"", "en": "\"add a feature\", \"match the design\""}}],
     "prompt": {"ko": "skill-creator 로 shop-web/.claude/skills 에 shop-feature 스킬을 만들어줘. 색은 디자인 토큰만 쓰고, 결제사 설정은 절대 건드리지 않는다는 규칙을 넣고, \"기능 추가\" \"시안대로\" 에 반응하게.",
                "en": "Use skill-creator to create a shop-feature skill in shop-web/.claude/skills: colors from design tokens only, never touch the payment provider config; triggers on \"add a feature\", \"match the design\"."}},
]
ASSETS = {"places": [{"cwd": "~/blog", "skills": [{"name": "blog-post", "description": "", "created": (SINCE + dt.timedelta(days=9)).isoformat(),
                                                    "modified": (SINCE + dt.timedelta(days=9)).isoformat()}], "claude_md": None}],
          "user_skills": [], "memory": [{"project": "blog", "file": "intro.md", "name": "intro", "description": "",
                                          "created": (SINCE + dt.timedelta(days=3)).isoformat()}]}


def bilingual_analysis():
    ko, en = ANALYSIS["ko"], ANALYSIS["en"]
    fr = [{"type": a["type"], "title": bi(a["title"], b["title"]), "desc": bi(a["desc"], b["desc"]),
           "examples": bi(a["examples"], b["examples"])} for a, b in zip(ko["frictions"], en["frictions"])]
    cands = []
    for a, b in zip(ko["candidates"], en["candidates"]):
        cands.append({"title": bi(a["title"], b["title"]), "problem": bi(a["problem"], b["problem"]),
                      "approach": bi(a["approach"], b["approach"]), "type": bi(a["type"], b["type"]),
                      "effort": a["effort"], "repeat_keys": b["repeat_keys"], "commands": a["commands"],
                      "friction_types": a["friction_types"], **DESIGN[len(cands)]})
    return {"categories": [{"name": k, "label": bi(TYPES["ko"][k][0], TYPES["en"][k][0]),
                            "desc": bi(TYPES["ko"][k][1], TYPES["en"][k][1])} for k in TYPES["en"]],
            "repeats": [{"key": k, "label": bi(KEYS["ko"][k], KEYS["en"][k])} for k in KEYS["en"]],
            "frictions": fr, "candidates": cands, "observations": bi(ko["observations"], en["observations"]),
            "areas": AREAS}


def build(lang, out):
    rnd = random.Random(7)
    os.makedirs(os.path.join(out, "labels"), exist_ok=True)
    prompts, sessions, labels, by_day = [], [], [], {}
    pid = 0
    for week in range(4):
        for si, (title, proj, tkey, items, facets) in enumerate(SESSIONS):
            if week == 3 and si == 4:
                continue  # the last week is a little lighter
            day = SINCE + dt.timedelta(days=week * 7 + si % 5)
            sid = f"S{len(sessions) + 1:03d}"
            start = dt.datetime.combine(day, dt.time(9 + si, 0), KST)
            ts = start
            n0 = len(prompts)
            for item in items:
                text, rk = item[0], item[1]
                rule = item[2] if len(item) > 2 else None
                if week == 3 and rule == "only tested code":
                    rule, text = None, "draft the next post outline"  # one rule shows up less often
                text = TEXT_KO.get(text, text) if lang == "ko" else text
                ts += dt.timedelta(minutes=rnd.randint(6, 25))
                pid += 1
                p = {"id": f"p{pid:04d}", "sid": sid, "session": f"sample-{sid}", "ts": ts.isoformat(timespec="minutes"),
                     "date": day.isoformat(), "week": (day - dt.timedelta(days=day.weekday())).isoformat(),
                     "hour": ts.hour, "project": proj, "source": "typed", "text": text,
                     "active_min": rnd.choice([10, 15, 20, 25])}
                prompts.append(p)
                by_day[day.isoformat()] = by_day.get(day.isoformat(), 0) + 1
                if rk or rule:
                    labels.append(f"{p['id']}\t\t{rk or ''}\t{rule or ''}".rstrip("\t"))
            n = len(prompts) - n0
            labels.insert(0, f"{sid}\t{tkey}\t{AREA[tkey]}")
            s = {"sid": sid, "id": f"sample-{sid}", "project": proj, "title": title, "start": start.isoformat(),
                 "end": ts.isoformat(), "prompts": n, "compacts": 0,
                 "active_min": sum(p["active_min"] for p in prompts[n0:]), "tools": {}, "commands": {}, "skills": {}}
            if facets:
                s["facets"] = dict(facets, underlying_goal=title, brief_summary=title)
            sessions.append(s)
    with open(os.path.join(out, "prompts.jsonl"), "w") as fh:
        fh.write("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in prompts))
    json.dump(sessions, open(os.path.join(out, "sessions.json"), "w"), ensure_ascii=False)
    with open(os.path.join(out, "labels", "batch-01.tsv"), "w") as fh:
        fh.write("\n".join(labels) + "\n")
    json.dump({"tools": [["Bash", 820], ["Read", 260], ["Edit", 140]],
               "commands": sorted(COMMANDS.items(), key=lambda kv: -kv[1]),
               "skills": [["git-workflow", 5]], "slash_commands": [], "mcp_servers": [["browser", 30]]},
              open(os.path.join(out, "tools.json"), "w"))
    by_proj = {}
    for p in prompts:
        by_proj[p["project"]] = by_proj.get(p["project"], 0) + 1
    weeks = {}
    for p in prompts:
        weeks[p["week"]] = weeks.get(p["week"], 0) + 1
    json.dump({"since": SINCE.isoformat(), "until": UNTIL.isoformat(), "days": DAYS, "project_filter": None,
               "active_min": sum(p["active_min"] for p in prompts), "prev_since": None, "prev_until": None,
               "prompts": len(prompts), "sessions": len(sessions), "active_days": len(by_day), "tool_calls": 1220,
               "prev_prompts": 61, "by_day": sorted(by_day.items()), "by_week": sorted(weeks.items()),
               "by_project": sorted(by_proj.items(), key=lambda kv: -kv[1]),
               "prev_by_project": [["shop-web", 40], ["blog", 21]], "by_hour": []},
              open(os.path.join(out, "stats.json"), "w"))
    fac = [s["facets"] for s in sessions if s.get("facets")]
    agg = lambda key: sorted({k: sum((f.get(key) or {}).get(k, 0) for f in fac)
                              for f in fac for k in (f.get(key) or {})}.items(), key=lambda kv: -kv[1])
    outc = {}
    for f in fac:
        outc[f["outcome"]] = outc.get(f["outcome"], 0) + 1
    json.dump({"available": True, "latest_report_date": UNTIL.isoformat(), "sessions_total": len(sessions),
               "sessions_with_facets": len(fac), "prompts_covered": sum(s["prompts"] for s in sessions if s.get("facets")),
               "prompts_total": len(prompts), "friction": agg("friction_counts"),
               "outcome": sorted(outc.items(), key=lambda kv: -kv[1]), "satisfaction": agg("user_satisfaction_counts")},
              open(os.path.join(out, "insights.json"), "w"))
    an = bilingual_analysis()
    an["lang"] = lang
    json.dump(an, open(os.path.join(out, "analysis.json"), "w"), ensure_ascii=False)
    json.dump(ASSETS, open(os.path.join(out, "assets.json"), "w"), ensure_ascii=False)
    # a previous run so the "since last run" table has something to show
    prev = {"since": "2026-08-31", "until": "2026-09-27", "days": DAYS, "scope": "", "prompts": 61,
            "generated": "2026-09-27T18:00",
            "repeats": {"commit & push": {"n": 9, "days": 7}, "run tests": {"n": 6, "days": 5},
                        "export cover image": {"n": 5, "days": 4}, "match design spec": {"n": 2, "days": 2}}}
    json.dump([prev], open(os.path.join(out, "history.json"), "w"), ensure_ascii=False)


def main():
    for lang in ("ko", "en"):
        work = os.path.join(HERE, "sample-data", lang)
        build(lang, work)
        subprocess.run([sys.executable, RENDER, "--work", work, "--output",
                        os.path.join(HERE, f"sample-report.{lang}.html"), "--history",
                        os.path.join(work, "history.json"), "--lang", lang], check=True)


if __name__ == "__main__":
    main()
