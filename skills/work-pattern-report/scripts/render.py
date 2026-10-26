#!/usr/bin/env python3
"""Render the HTML report from extract.py output plus the model's labels (labels/*.tsv) and analysis.json.

labels/*.tsv, one line each (tab-separated, empty cells allowed):
  S012<TAB>task type<TAB>area          session default type, and the work area the session belongs to (optional)
  p0123<TAB>task type<TAB>repeat key    per-prompt override; the repeat key is optional
  p0124<TAB><TAB>repeat key<TAB>rule     a fourth column tags a rule the user stated (correction, preference)
Lines starting with '#' are comments. Task types and repeat keys are ids; their display text comes from
analysis.json, so the ids can stay in one language while the report switches between two.

analysis.json — every display text may be a plain string or {"ko": "...", "en": "..."}:
  {"lang": "ko" | "en",                         language shown first
   "categories": [{"name": "<id>", "label": T, "desc": T}],
   "repeats": [{"key": "<id>", "label": T, "desc": T}],
   "areas": [{"id": "<area id>", "label": T, "desc": T, "stages": [T], "rules": [{"key": "<rule id>", "text": T}],
              "existing": ["<skill name>"], "mode": "new" | "extend",
              "skills": [{"name": "...", "purpose": T, "contains": [T], "triggers": T}], "prompt": T, "note": T}],
   "frictions": [{"type": "wrong_approach", "title": T, "desc": T, "examples": [T, ...]}],
   "candidates": [{"title": T, "problem": T, "approach": T, "type": T, "effort": "S|M|L",
                   "repeat_keys": ["<id>"], "commands": ["gradlew assemble*"], "friction_types": ["wrong_approach"],
                   "note": T}],
   "observations": [T, ...]}

With --history (a JSON list), the run is compared with the previous run of the same scope and then appended.

Usage: python3 render.py --work DIR --output FILE.html [--history FILE.json] [--lang ko|en]
"""
import argparse
import collections
import datetime as dt
import glob
import html
import json
import os

UTILITY_CMDS = {"grep", "head", "tail", "sed", "ls", "cat", "cut", "sort", "uniq", "wc", "find", "awk", "tr", "date",
                "seq", "stat", "mkdir", "cp", "mv", "rm", "touch", "xargs", "tee", "diff", "basename", "dirname",
                "realpath", "readlink", "which", "file", "du", "df", "jq", "python3 (inline)", "bash", "sh", "zsh",
                "printf", "test", "env", "pwd", "less", "nl", "column", "od", "xxd", "iconv", "base64", "shasum",
                "md5", "unzip", "zip", "tar", "gzip"}

LABELS = {
    "ko": {
        "friction": {"wrong_approach": "잘못된 접근", "misunderstood_request": "요청을 잘못 이해", "buggy_code": "버그 있는 코드",
                     "excessive_changes": "과한 변경", "tool_errors": "도구 오류", "tool_ui_difficulty": "도구·UI 어려움",
                     "external_limitation": "외부 제약", "user_error_wrong_paste": "잘못 붙여넣기",
                     "incomplete_work": "작업 미완", "slow_response": "느린 응답", "hallucination": "사실과 다른 답"},
        "outcome": {"fully_achieved": "완전히 달성", "mostly_achieved": "대부분 달성", "partially_achieved": "일부 달성",
                    "not_achieved": "달성 못함", "unclear_from_transcript": "불분명", "unknown": "알 수 없음"},
        "satisfaction": {"happy": "매우 만족", "satisfied": "만족", "likely_satisfied": "대체로 만족",
                         "dissatisfied": "불만족", "frustrated": "답답함"},
    },
    "en": {"friction": {}, "outcome": {}, "satisfaction": {}},  # English falls back to the humanized key
}

T = {
    "ko": {
        "title": "작업 패턴 리포트",
        "subtitle": "{since} ~ {until} · {days}일{scope}",
        "meta": "Claude Code 대화 기록과 /insights 분석으로 만든 로컬 파일 · {gen}",
        "scope": " · 범위 {x}",
        "u_count": "건", "u_times": "회", "u_items": "개",
        "hours": "{h:.1f}시간", "minutes": "{m}분",
        "t_prompts": "직접 보낸 요청", "t_delta": "직전 {days}일보다 {sign}{d}", "t_noprev": "직전 기간 기록 없음",
        "t_active": "추정 작업 시간", "t_active_sub": "활동이 기록된 5분 칸",
        "t_sessions": "세션", "t_sessions_sub": "{a}/{d}일 활동",
        "t_repeats": "반복 요청", "t_repeats_sub": "여러 날 다시 나온 요청 종류",
        "t_tools": "Claude 도구 호출", "t_tools_sub": "Bash·Read·Edit 등",
        "nav": {"areas": "업무 영역 스킬", "candidates": "작은 자동화", "changes": "지난번 대비", "tasks": "작업 유형", "repeats": "반복 요청",
                "friction": "막힌 지점", "weekly": "주별 흐름", "commands": "실행한 명령", "when": "언제·어디서",
                "sessions": "긴 세션", "notes": "관찰"},
        "count": "{n}개", "expand_all": "모두 펼치기", "collapse_all": "모두 접기",
        "sum_rules": "규칙 {n}개", "sum_after": " · 스킬 만든 뒤 다시 나온 것 {n}개", "sum_existing": "스킬 {s}개 · 메모리 {m}개",
        "sum_skills": "스킬 {n}개", "sum_prompt": "복사해서 Claude Code에 붙여 넣기", "sum_evidence": "반복 요청 {r} · 명령 {c}",
        "sum_quotes": "{n}개", "sum_success": "기준 {n}개",
        "area_h": "업무 영역 스킬 후보",
        "area_lede": "한 업무 영역에서 같은 흐름을 여러 날 반복하고, 고쳐 가며 같은 규칙을 다시 말한 곳입니다. 그 규칙과 흐름을 담아 둘 스킬 묶음을 제안합니다.",
        "area_stats": "세션 {s}개 · {d}일 · 요청 {p}건 · 약 {t}",
        "mode_new": "새 스킬 묶음", "mode_extend": "기존 스킬 보강",
        "flow": "작업 흐름", "rules": "쌓인 규칙", "rules_hint": "고쳐 가며 말한 기준. 스킬에 넣으면 다시 말하지 않아도 됩니다.",
        "rule_cols": ["규칙", "횟수", "날", "마지막", "실제로 하신 말", "스킬 만든 뒤"],
        "existing": "이미 있는 것", "existing_skill": "<code>{n}</code> {c} 만듦",
        "existing_mem": "메모리 {n}개 (마지막 {d})", "existing_md": "CLAUDE.md ({c} 만듦)",
        "after_note": "스킬을 다 만든 {d} 이후에도 다시 말한 규칙이 {n}개 있습니다. 이 규칙들을 스킬에 넣으세요.",
        "proposal": "제안하는 스킬", "prop_cols": ["스킬", "역할", "담을 것", "언제 쓰나"],
        "no_area": "여러 날에 걸쳐 같은 흐름과 규칙이 반복된 업무 영역을 찾지 못했습니다.",
        "cand_h": "작은 자동화 (명령·hook)",
        "cand_lede": "반복 요청, 실제로 실행된 명령, /insights 마찰 기록에서 센 숫자를 근거로 골랐습니다.",
        "cand_now": "지금", "cand_auto": "자동화하면", "cand_evidence": "근거",
        "effort": {"S": "만들기 쉬움", "M": "만들기 보통", "L": "만들기 어려움"},
        "ev_missing": "<b>{k}</b> 이번 기간 기록 없음",
        "ev_cmd": "<code>{k}</code> {n}회 실행",
        "ev_fric": "같은 세션들의 /insights 마찰 <b>{f}</b> {n}회",
        "quotes": "실제로 하신 말", "no_cand": "후보 없음",
        "ev_cols": ["반복 요청", "횟수", "날", "세션", "마지막"],
        "design": "설계", "trigger": "언제 실행되나", "steps": "단계", "output": "결과물", "where": "만들 위치",
        "manual": "사람이 남길 일", "step_auto": "자동", "step_human": "승인 필요",
        "success": "성공 기준", "success_line": "지금 <b>{k}</b> {n}회 · {d}일 → 다음 리포트에서 줄었는지 확인",
        "prompt": "만들기 프롬프트", "prompt_hint": "Claude Code에 그대로 붙여 넣으면 이 자동화를 만듭니다.",
        "copy": "복사", "copied": "복사됨",
        "chg_h": "지난번 리포트 대비",
        "chg_lede": "직전 실행 {ps}~{pu}({pd}일, 요청 {pp}건)과 이번 {s}~{u}({d}일, 요청 {p}건)을 같은 반복 키로 비교했습니다. 기간 길이가 다르면 날 수를 같이 보세요.",
        "chg_cols": ["반복 요청", "지난번", "이번", "변화", ""], "chg_cell": "{n}회 · {d}일",
        "chg_tags": {"new": "새로 나옴", "gone": "사라짐", "down": "줄어듦", "up": "늘어남", "same": "같음"},
        "chg_none": "같은 범위로 실행한 이전 기록이 없어 이번 실행을 기준점으로 저장했습니다. 다음 실행부터 변화가 보입니다.",
        "tasks_h": "무슨 일을 가장 많이 했나", "tasks_lede": "요청 수 기준. 막대 오른쪽은 비중, 추정 작업 시간, 세션 수입니다.",
        "cat_sub": "{pct}% · 약 {time} · 세션 {n}", "unlabeled": "미분류 {n}건",
        "tasks_cols": ["작업 유형", "설명"],
        "rep_h": "반복해서 요청한 것",
        "rep_lede": "같은 의도의 요청이 다른 날에 다시 나온 것. 날 수가 많을수록 습관이고, 자동화 효과가 큽니다.",
        "rep_cols": ["반복 요청", "횟수", "날", "세션", "기간", "실제 문장"], "none": "없음",
        "fr_h": "막힌 지점",
        "fr_lede": "/insights 가 세션마다 남긴 분석을 이 기간만 모았습니다. 적용 범위 {cov}, 마지막 /insights {d}.",
        "fr_cov": "세션 {a}/{b}개 · 요청 {c}/{dd}건",
        "fr_types": "마찰 유형", "fr_outcome": "세션 결과", "fr_satis": "추정 만족도(모델 추정)",
        "fr_missing": "/insights 분석 데이터가 없습니다. Claude Code에서 <code>/insights</code> 를 먼저 실행하면 막힌 지점과 세션 결과가 여기에 나옵니다.",
        "wk_h": "주별 흐름", "wk_lede": "작업 유형별 주간 요청 수. 진할수록 많습니다.",
        "wk_label": "{md}주", "wk_tip": "{c} · {w}주: {v}건",
        "cmd_h": "Claude가 실제로 돌린 것", "cmd_work": "작업성 명령",
        "cmd_util": "grep·sed·cat 같은 조회용 {n}회는 뺐습니다.", "skills": "스킬", "mcp": "MCP 서버",
        "when_h": "언제·어디서", "daily": "날짜별 요청", "weekend": "옅은 막대는 주말", "proj": "프로젝트별 요청",
        "proj_prev": "직전 {n}", "weekdays": ["월", "화", "수", "목", "금", "토", "일"],
        "day_tip": "{date} ({wd}) {v}건",
        "ses_h": "긴 세션", "ses_cols": ["세션", "프로젝트", "제목", "요청", "작업 시간", "시작", "결과"],
        "untitled": "(제목 없음)",
        "obs_h": "관찰", "nodata": "데이터 없음",
        "method_h": "집계 방법",
        "method": "~/.claude/projects 의 세션 기록에서 사람이 직접 입력한 메시지(제안 수락·대기열 포함)만 셌습니다. 서브에이전트 대화, 시스템 알림, /compact 뒤 자동으로 붙는 요약은 뺐습니다. 작업 시간은 요청 하나부터 다음 요청 전까지 기록이 찍힌 5분 칸 수라, 자리를 비운 시간은 빠지고 Claude가 혼자 오래 돈 시간은 들어갑니다. 작업 유형과 반복 요청은 Claude가 세션 제목과 메시지를 읽고 붙인 분류입니다. 막힌 지점·세션 결과는 /insights 가 세션마다 남긴 분석(~/.claude/usage-data/facets)을 그대로 모은 것입니다. 실제 문장 인용과 세션 제목은 원문 그대로입니다.",
    },
    "en": {
        "title": "Work Pattern Report",
        "subtitle": "{since} – {until} · {days} days{scope}",
        "meta": "Local file built from Claude Code transcripts and /insights analysis · {gen}",
        "scope": " · scope {x}",
        "u_count": "", "u_times": "×", "u_items": "",
        "hours": "{h:.1f} h", "minutes": "{m} min",
        "t_prompts": "Prompts you typed", "t_delta": "{sign}{d} vs previous {days} days", "t_noprev": "no records in the previous window",
        "t_active": "Estimated active time", "t_active_sub": "5-minute bins with activity",
        "t_sessions": "Sessions", "t_sessions_sub": "active on {a} of {d} days",
        "t_repeats": "Repeated requests", "t_repeats_sub": "kinds that came back on other days",
        "t_tools": "Claude tool calls", "t_tools_sub": "Bash, Read, Edit and others",
        "nav": {"areas": "Area skills", "candidates": "Small automations", "changes": "Since last run", "tasks": "Task types", "repeats": "Repeats",
                "friction": "Friction", "weekly": "Weekly", "commands": "Commands", "when": "When & where",
                "sessions": "Sessions", "notes": "Notes"},
        "count": "{n}", "expand_all": "Expand all", "collapse_all": "Collapse all",
        "sum_rules": "{n} rules", "sum_after": " · {n} came back after the skills existed", "sum_existing": "{s} skills · {m} memory notes",
        "sum_skills": "{n} skills", "sum_prompt": "copy and paste into Claude Code", "sum_evidence": "{r} repeated requests · {c} commands",
        "sum_quotes": "{n}", "sum_success": "{n} checks",
        "area_h": "Work-area skill candidates",
        "area_lede": "Places where you ran the same flow on many days and kept restating the same rules while correcting the work. Each gets a proposed set of skills that holds those rules and that flow.",
        "area_stats": "{s} sessions · {d} days · {p} prompts · ~{t}",
        "mode_new": "New skill set", "mode_extend": "Extend existing skills",
        "flow": "Work flow", "rules": "Rules you built up", "rules_hint": "Standards you stated while correcting the work. Put them in a skill and you won't have to say them again.",
        "rule_cols": ["Rule", "Count", "Days", "Last", "What you said", "After skill"],
        "existing": "Already there", "existing_skill": "<code>{n}</code> created {c}",
        "existing_mem": "{n} memory notes (last {d})", "existing_md": "CLAUDE.md (created {c})",
        "after_note": "{n} rules came up again after the skills were finished on {d}. Add these to the skills.",
        "proposal": "Proposed skills", "prop_cols": ["Skill", "Role", "Holds", "Use when"],
        "no_area": "No work area showed the same flow and rules repeated across many days.",
        "cand_h": "Small automations (commands, hooks)",
        "cand_lede": "Chosen from repeated requests, commands Claude actually ran and /insights friction, all counted from this period's records.",
        "cand_now": "Now", "cand_auto": "Automated", "cand_evidence": "Evidence",
        "effort": {"S": "Easy to build", "M": "Moderate to build", "L": "Hard to build"},
        "ev_missing": "<b>{k}</b> not seen this period",
        "ev_cmd": "<code>{k}</code> run {n}×",
        "ev_fric": "/insights friction <b>{f}</b> in the same sessions: {n}×",
        "quotes": "What you actually said", "no_cand": "No candidates",
        "ev_cols": ["Repeated request", "Count", "Days", "Sessions", "Last"],
        "design": "Design", "trigger": "Runs when", "steps": "Steps", "output": "Produces", "where": "Lives in",
        "manual": "Stays with you", "step_auto": "auto", "step_human": "needs approval",
        "success": "Success check", "success_line": "Now <b>{k}</b> {n}× · {d} days → check it goes down in the next report",
        "prompt": "Build prompt", "prompt_hint": "Paste this into Claude Code and it will build the automation.",
        "copy": "Copy", "copied": "Copied",
        "chg_h": "Compared with the last run",
        "chg_lede": "The last run {ps}–{pu} ({pd} days, {pp} prompts) and this run {s}–{u} ({d} days, {p} prompts), compared by the same repeat keys. If the windows differ in length, look at days too.",
        "chg_cols": ["Repeated request", "Last run", "This run", "Change", ""], "chg_cell": "{n}× · {d}d",
        "chg_tags": {"new": "new", "gone": "gone", "down": "down", "up": "up", "same": "same"},
        "chg_none": "No earlier run with the same scope, so this run was saved as the baseline. Changes appear from the next run.",
        "tasks_h": "What you spent the most on", "tasks_lede": "By prompt count. After each bar: share, estimated active time, sessions.",
        "cat_sub": "{pct}% · ~{time} · {n} sessions", "unlabeled": "{n} unlabeled",
        "tasks_cols": ["Task type", "What it covers"],
        "rep_h": "Things you asked for repeatedly",
        "rep_lede": "Requests with the same intent that came back on another day. The more days, the more it is a habit and the more automation pays off.",
        "rep_cols": ["Repeated request", "Count", "Days", "Sessions", "Span", "What you said"], "none": "None",
        "fr_h": "Where things got stuck",
        "fr_lede": "Per-session analysis left by /insights, limited to this period. Coverage {cov}; last /insights run {d}.",
        "fr_cov": "{a}/{b} sessions · {c}/{dd} prompts",
        "fr_types": "Friction types", "fr_outcome": "Session outcomes", "fr_satis": "Satisfaction (model-estimated)",
        "fr_missing": "No /insights data. Run <code>/insights</code> in Claude Code first and friction and session outcomes will appear here.",
        "wk_h": "Week by week", "wk_lede": "Prompts per task type per week. Darker means more.",
        "wk_label": "wk {md}", "wk_tip": "{c} · week of {w}: {v}",
        "cmd_h": "What Claude actually ran", "cmd_work": "Work commands",
        "cmd_util": "Lookup utilities such as grep, sed and cat ({n} calls) are left out.", "skills": "Skills", "mcp": "MCP servers",
        "when_h": "When and where", "daily": "Prompts per day", "weekend": "Lighter bars are weekends",
        "proj": "Prompts per project", "proj_prev": "prev {n}",
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "day_tip": "{date} ({wd}) {v}",
        "ses_h": "Longest sessions", "ses_cols": ["Session", "Project", "Title", "Prompts", "Active", "Start", "Outcome"],
        "untitled": "(untitled)",
        "obs_h": "Observations", "nodata": "No data",
        "method_h": "How this was counted",
        "method": "Only messages a person typed (including accepted suggestions and queued messages) in ~/.claude/projects are counted. Subagent traffic, system notices and the summary inserted after /compact are excluded. Active time is the number of 5-minute bins with any recorded activity between a prompt and the next one, so time away is excluded and long autonomous Claude runs are included. Task types and repeat keys are labels Claude assigned after reading session titles and messages. Friction and outcomes are the per-session analysis /insights left in ~/.claude/usage-data/facets. Quotes and session titles are shown as written.",
    },
}

E = html.escape

# Cool neutral palette after newspaper data desks: one signal red, slate text, a single blue for data.
INK, SLATE, RED, BLUE, BLUE_LT = "var(--ink)", "var(--slate)", "var(--red)", "var(--blue)", "var(--blue-lt)"


class R:
    """Language-bound helpers."""

    def __init__(self, lang):
        self.lang = lang if lang in T else "en"
        self.s = T[self.lang]
        self.l = LABELS[self.lang]

    def t(self, key, **kw):
        v = self.s[key]
        return v.format(**kw) if kw else v

    def label(self, kind, key):
        return self.l[kind].get(key) or key.replace("_", " ").capitalize()

    def dur(self, m):
        return self.t("hours", h=m / 60) if m >= 60 else self.t("minutes", m=m)

    def tx(self, v):
        """A display text that may be a plain string or {"ko": ..., "en": ...}."""
        if isinstance(v, dict):
            return v.get(self.lang) or next((x for x in v.values() if x), "")
        return v or ""


def load(work):
    prompts = [json.loads(l) for l in open(os.path.join(work, "prompts.jsonl")) if l.strip()]
    sessions = json.load(open(os.path.join(work, "sessions.json")))
    tools = json.load(open(os.path.join(work, "tools.json")))
    stats = json.load(open(os.path.join(work, "stats.json")))
    ip = os.path.join(work, "insights.json")
    insights = json.load(open(ip)) if os.path.exists(ip) else {"available": False}
    ap = os.path.join(work, "analysis.json")
    analysis = json.load(open(ap)) if os.path.exists(ap) else {}
    sess_default, sess_area, per_prompt = {}, {}, {}
    for f in sorted(glob.glob(os.path.join(work, "labels", "*.tsv"))):
        for line in open(f):
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = [x.strip() for x in line.split("\t")]
            key = parts[0]
            cat = parts[1] if len(parts) > 1 else ""
            rep = parts[2] if len(parts) > 2 else ""
            if key.startswith("S"):
                if cat:
                    sess_default[key] = cat
                if rep:
                    sess_area[key] = rep
            elif key.startswith("p"):
                cur = per_prompt.setdefault(key, {})
                if cat:
                    cur["task"] = cat
                if rep:
                    cur["repeat"] = rep
                if len(parts) > 3 and parts[3]:
                    cur["rule"] = parts[3]
    for p in prompts:
        lab = per_prompt.get(p["id"], {})
        p["task"] = lab.get("task") or sess_default.get(p["sid"]) or "?"
        p["repeat"] = lab.get("repeat")
        p["rule"] = lab.get("rule")
        p["area"] = sess_area.get(p["sid"])
        p.setdefault("active_min", 0)
    asp = os.path.join(work, "assets.json")
    analysis["_assets"] = json.load(open(asp)) if os.path.exists(asp) else None
    return prompts, sessions, tools, stats, insights, analysis


def text_width(s):
    """Rough rendered width in px at 12.5px: CJK glyphs are about twice as wide as Latin ones."""
    return sum(12.5 if ord(ch) > 0x2E80 else 7 for ch in s)


def hbar(r, rows, unit="", width=1080, max_rows=14, highlight_first=False):
    """Horizontal bars with direct labels. rows: [(label, value, sub)]"""
    rows = rows[:max_rows]
    if not rows:
        return f"<p class='muted'>{r.t('nodata')}</p>"
    vmax = max(x[1] for x in rows) or 1
    lw = min(220, max(80, max(text_width(str(x[0])) for x in rows) + 12))
    tail = max(text_width(f"{x[1]}{unit}" + (f"  {x[2]}" if x[2] else "")) for x in rows) + 10
    bw = max(120, width - lw - tail)
    rh = 24
    h = len(rows) * rh + 6
    out = [f"<svg class='chart' viewBox='0 0 {width} {h}' width='{width}' role='img'>",
           f"<line x1='{lw}' x2='{lw}' y1='0' y2='{h}' class='axis'/>"]
    for i, (lab, v, sub) in enumerate(rows):
        y = i * rh + 4
        w = max(1.5, bw * v / vmax)
        fill = RED if (highlight_first and i == 0) else BLUE
        out.append(f"<text x='{lw-8}' y='{y+14}' text-anchor='end' class='lab'>{E(str(lab))}</text>")
        out.append(f"<rect x='{lw}' y='{y+3}' width='{w:.1f}' height='{rh-9}' fill='{fill}'><title>{E(str(lab))}: {v}{unit}</title></rect>")
        out.append(f"<text x='{lw+w+6:.1f}' y='{y+14}' class='val'><tspan class='num'>{v}{unit}</tspan>{('  ' + E(sub)) if sub else ''}</text>")
    out.append("</svg>")
    return "".join(out)


def heatmap(r, prompts, cats, names, weeks):
    if not weeks or not cats:
        return ""
    cnt = collections.Counter((p["task"], p["week"]) for p in prompts)
    vmax = max(cnt.values()) if cnt else 1
    lw = min(220, max(80, max(text_width(names[c]) for c in cats) + 12))
    cw, rh, top = 58, 22, 22
    width = lw + cw * len(weeks) + 4
    h = top + rh * len(cats) + 2
    out = [f"<svg class='chart' viewBox='0 0 {width} {h}' width='{width}' role='img'>"]
    for j, w in enumerate(weeks):
        out.append(f"<text x='{lw + j*cw + 4}' y='14' class='lab'>{E(r.t('wk_label', md=w[5:].replace('-', '/')))}</text>")
    for i, c in enumerate(cats):
        y = top + i * rh
        out.append(f"<text x='{lw-8}' y='{y+15}' text-anchor='end' class='lab'>{E(names[c])}</text>")
        for j, w in enumerate(weeks):
            v = cnt.get((c, w), 0)
            op = 0 if v == 0 else 0.18 + 0.82 * v / vmax
            out.append(f"<rect x='{lw + j*cw}' y='{y}' width='{cw-2}' height='{rh-2}' fill='var(--cell)'/>")
            if v:
                out.append(f"<rect x='{lw + j*cw}' y='{y}' width='{cw-2}' height='{rh-2}' fill='{BLUE}' opacity='{op:.2f}'><title>{E(r.t('wk_tip', c=names[c], w=w, v=v))}</title></rect>")
                cls = "cell inv" if op > 0.55 else "cell"
                out.append(f"<text x='{lw + j*cw + 6}' y='{y+15}' class='{cls}'>{v}</text>")
    out.append("</svg>")
    return "".join(out)


def daybars(r, stats):
    days = dict(stats["by_day"])
    d0 = dt.date.fromisoformat(stats["since"])
    n = stats["days"]
    vals = [(d0 + dt.timedelta(days=i)) for i in range(n)]
    vmax = max(days.values()) if days else 1
    width, h, bot = 520, 130, 20
    bw = width / max(n, 1)
    every = 1 if n <= 14 else 7
    wd = r.t("weekdays")
    out = [f"<svg class='chart' viewBox='0 0 {width} {h}' width='{width}' role='img'>",
           f"<line x1='0' x2='{width}' y1='{h-bot}' y2='{h-bot}' class='base'/>"]
    for i, d in enumerate(vals):
        v = days.get(d.isoformat(), 0)
        bh = (h - bot - 14) * v / vmax
        fill = BLUE if d.weekday() < 5 else BLUE_LT
        tip = r.t("day_tip", date=d.isoformat(), wd=wd[d.weekday()], v=v)
        out.append(f"<rect x='{i*bw+1:.1f}' y='{h-bot-bh:.1f}' width='{max(bw-2,1):.1f}' height='{bh:.1f}' fill='{fill}'><title>{E(tip)}</title></rect>")
        if every == 1 or d.weekday() == 0 or i == 0:
            label = f"{d.month}/{d.day}" + (f" {wd[d.weekday()]}" if every == 1 else "")
            x = i * bw + (bw / 2 if every == 1 else 1)
            anchor = "text-anchor='middle'" if every == 1 else ""
            out.append(f"<text x='{x:.1f}' y='{h-5}' class='lab' {anchor}>{E(label)}</text>")
            if every == 1 and v:
                out.append(f"<text x='{i*bw + bw/2:.1f}' y='{h-bot-bh-4:.1f}' class='val num' text-anchor='middle'>{v}</text>")
    out.append("</svg>")
    return "".join(out)


def repeat_table(prompts):
    groups = collections.defaultdict(list)
    for p in prompts:
        if p.get("repeat"):
            groups[p["repeat"]].append(p)
    rows = []
    for k, ps in groups.items():
        quotes, seen = [], set()
        for p in sorted(ps, key=lambda x: (len(x["text"]) < 8, x["ts"])):
            t = p["text"][:120]
            if t not in seen:
                seen.add(t)
                quotes.append(t)
        rows.append({"key": k, "n": len(ps), "sessions": len({p["sid"] for p in ps}), "sids": {p["sid"] for p in ps},
                     "days": len({p["date"] for p in ps}), "first": min(p["date"] for p in ps),
                     "last": max(p["date"] for p in ps), "examples": quotes[:3]})
    rows.sort(key=lambda x: (-x["days"], -x["n"]))
    return rows


def history_compare(path, stats, reps):
    """Find the previous run with the same scope (project filter), compare, then append this run."""
    if not path:
        return None
    hist = []
    if os.path.exists(path):
        try:
            hist = json.load(open(path))
        except (OSError, json.JSONDecodeError):
            hist = []
    scope = stats.get("project_filter") or ""
    prev = None
    for h in sorted(hist, key=lambda h: h["until"]):
        if (h.get("scope") or "") == scope and h["until"] < stats["until"]:
            prev = h
    entry = {"since": stats["since"], "until": stats["until"], "days": stats["days"], "scope": scope,
             "prompts": stats["prompts"], "generated": dt.datetime.now().isoformat(timespec="minutes"),
             "repeats": {x["key"]: {"n": x["n"], "days": x["days"]} for x in reps}}
    hist = [h for h in hist if not (h["since"] == entry["since"] and h["until"] == entry["until"]
                                    and (h.get("scope") or "") == scope)] + [entry]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(hist, fh, ensure_ascii=False, indent=1)
    return prev


OPEN_SECTIONS = {"areas", "changes"}  # everything else starts folded, with its count beside the title


def section(num, sid, title, lede, inner, meta=""):
    return (f"<details class='sec'{' open' if sid in OPEN_SECTIONS else ''}><summary class='sh'>"
            f"<span class='no'>{num:02d}</span><h2>{E(title)}</h2>"
            + (f"<span class='meta'>{E(meta)}</span>" if meta else "") + "<span class='tg' aria-hidden='true'></span></summary>"
            + "<div class='secbody'>" + (f"<p class='lede'>{lede}</p>" if lede else "") + inner + "</div></details>")


def blk(title, content, meta="", open_=False):
    """One foldable block inside a card: the title and a one-line summary stay visible."""
    if not content:
        return ""
    return (f"<details class='blk'{' open' if open_ else ''}><summary><h4>{title}</h4>"
            f"<span class='sum'>{meta}</span></summary><div class='bd'>{content}</div></details>")


def figure(title, inner, note=""):
    return (f"<figure><figcaption><span class='tag'></span>{E(title)}</figcaption>{inner}"
            + (f"<p class='src'>{E(note)}</p>" if note else "") + "</figure>")


def build_page(r, prompts, sessions, tools, stats, insights, analysis, prev, history_on):
    """One full page (nav + main) with every display text in r's language."""
    U_CNT, U_X, U_IT = r.t("u_count"), r.t("u_times"), r.t("u_items")
    sess_by_sid = {s["sid"]: s for s in sessions}
    cat_meta = {c["name"]: c for c in analysis.get("categories", [])}
    rep_meta = {x["key"]: x for x in analysis.get("repeats", [])}
    cname = lambda c: r.tx(cat_meta.get(c, {}).get("label")) or c
    kname = lambda k: r.tx(rep_meta.get(k, {}).get("label")) or k

    cat_counts = collections.Counter(p["task"] for p in prompts)
    cat_minutes = collections.Counter()
    for p in prompts:
        cat_minutes[p["task"]] += p["active_min"]
    cat_order = sorted([c for c in cat_counts if c != "?"], key=lambda c: -cat_counts[c]) + (["?"] if "?" in cat_counts else [])
    names = {c: cname(c) for c in cat_order}
    total = len(prompts) or 1
    sess_by_cat = collections.defaultdict(set)
    for p in prompts:
        sess_by_cat[p["task"]].add(p["sid"])
    weeks = sorted({p["week"] for p in prompts})
    reps = repeat_table(prompts)
    rep_by_key = {x["key"]: x for x in reps}
    unlabeled = cat_counts.get("?", 0)

    cmd_count = dict(tools["commands"])
    work_cmds = [(k, v, "") for k, v in tools["commands"] if k not in UTILITY_CMDS][:14]
    util_total = sum(v for k, v in tools["commands"] if k in UTILITY_CMDS)
    proj_prev = dict(stats.get("prev_by_project", []))
    proj_rows = [(k, v, r.t("proj_prev", n=proj_prev.get(k, 0))) for k, v in stats["by_project"]]
    delta = stats["prompts"] - stats["prev_prompts"]
    delta_txt = (r.t("t_delta", days=stats["days"], sign="+" if delta >= 0 else "", d=delta)
                 if stats["prev_prompts"] else r.t("t_noprev"))

    sections = []  # (id, title-for-nav, html)

    # ---- work-area skill candidates (the main output)
    assets = analysis.get("_assets") or {}
    skill_born = {}
    for place in assets.get("places", []):
        for sk in place.get("skills", []):
            skill_born[sk["name"]] = sk["created"]
    for sk in assets.get("user_skills", []):
        skill_born.setdefault(sk["name"], sk["created"])
    rules_by_key = collections.defaultdict(list)
    for p in prompts:
        if p.get("rule"):
            rules_by_key[p["rule"]].append(p)
    area_cards = []
    for i, ar in enumerate(analysis.get("areas", []), 1):
        aps = [p for p in prompts if p.get("area") == ar.get("id")]
        a_s, a_d = len({p["sid"] for p in aps}), len({p["date"] for p in aps})
        a_t = r.dur(sum(p["active_min"] for p in aps))
        existing = [n for n in ar.get("existing", []) if n in skill_born]
        done_on = max((skill_born[n] for n in existing), default=None)
        stages = "".join(f"<li>{E(r.tx(x))}</li>" for x in ar.get("stages", []))
        rrows, after_n = [], 0
        for rl in ar.get("rules", []):
            ps = rules_by_key.get(rl.get("key"), [])
            if not ps:
                continue
            after = sum(1 for p in ps if done_on and p["date"] > done_on)
            after_n += 1 if after else 0
            q = "<br>".join(E(p["text"][:90]) for p in ps[:2])
            rrows.append((len({p['date'] for p in ps}), len(ps),
                          f"<tr><td>{E(r.tx(rl.get('text')) or rl.get('key'))}</td><td class='num'>{len(ps)}</td>"
                          f"<td class='num'>{len({p['date'] for p in ps})}</td><td class='num'>{max(p['date'] for p in ps)[5:]}</td>"
                          f"<td class='ex'>{q}</td><td class='num {'up' if after else ''}'>{after if done_on else '–'}</td></tr>"))
        rrows.sort(key=lambda x: (-x[0], -x[1]))
        rhead = "".join(f"<th>{E(h)}</th>" for h in r.t("rule_cols"))
        rules_html = (f"<p class='hint'>{r.t('rules_hint')}</p><table class='ev rules'><thead><tr>{rhead}</tr></thead>"
                      f"<tbody>{''.join(x[2] for x in rrows)}</tbody></table>") if rrows else ""
        ex_items = [r.t("existing_skill", n=E(n), c=skill_born[n]) for n in existing]
        cwd_place = next((pl for pl in assets.get("places", []) if any(sk["name"] in existing for sk in pl["skills"])), None)
        if cwd_place and cwd_place.get("claude_md"):
            ex_items.append(r.t("existing_md", c=cwd_place["claude_md"]["created"]))
        proj = collections.Counter(p["project"] for p in aps).most_common(1)
        mems = [m for m in assets.get("memory", []) if proj and m["project"] == proj[0][0]]
        if mems:
            ex_items.append(r.t("existing_mem", n=len(mems), d=max(m["created"] for m in mems)))
        existing_html = ("<ul class='evx'>" + "".join(f"<li>{x}</li>" for x in ex_items) + "</ul>") if ex_items else ""
        if done_on and after_n:
            existing_html += f"<p class='warn'>{r.t('after_note', n=after_n, d=done_on)}</p>"
        prow = []
        for sk in ar.get("skills", []):
            holds = "".join(f"<li>{E(r.tx(x))}</li>" for x in sk.get("contains", []))
            prow.append(f"<tr><td><code>{E(sk.get('name', ''))}</code></td><td>{E(r.tx(sk.get('purpose')))}</td>"
                        f"<td><ul class='holds'>{holds}</ul></td><td class='muted'>{E(r.tx(sk.get('triggers')))}</td></tr>")
        phead = "".join(f"<th>{E(h)}</th>" for h in r.t("prop_cols"))
        prop_html = f"<table class='prop'><thead><tr>{phead}</tr></thead><tbody>{''.join(prow)}</tbody></table>" if prow else ""
        prompt = r.tx(ar.get("prompt"))
        mode = r.t("mode_extend") if ar.get("mode") == "extend" else r.t("mode_new")
        note = r.tx(ar.get("note"))
        area_cards.append(f"""
<article class="cand area">
  <header class="ch"><span class="rank">{i}</span><h3>{E(r.tx(ar.get('label')))}</h3><span class="badges"><span class="badge">{E(mode)}</span></span></header>
  <p class="kind">{E(r.t('area_stats', s=a_s, d=a_d, p=len(aps), t=a_t))}{(' — ' + E(r.tx(ar.get('desc')))) if r.tx(ar.get('desc')) else ''}</p>
  {('<div class="blk static"><h4>' + r.t('flow') + '</h4><div><ol class="flow">' + stages + '</ol></div></div>') if stages else ''}
  {blk(r.t('rules'), rules_html, E(r.t('sum_rules', n=len(rrows)) + (r.t('sum_after', n=after_n) if done_on and after_n else '')))}
  {blk(r.t('existing'), existing_html, E(r.t('sum_existing', s=len(existing), m=len(mems))))}
  {blk(r.t('proposal'), prop_html, E(r.t('sum_skills', n=len(prow))))}
  {blk(r.t('prompt'), ('<div class="prompt"><pre>' + E(prompt) + '</pre><button type="button" class="copy" data-done="' + E(r.t('copied')) + '">' + r.t('copy') + '</button></div>') if prompt else '', E(r.t('sum_prompt')), open_=True)}
  {('<p class="note">' + E(note) + '</p>') if note else ''}
</article>""")
    sections.append(("areas", r.t("area_h"), r.t("area_lede"),
                     "".join(area_cards) or f"<p class='muted'>{r.t('no_area')}</p>"))

    # ---- automation candidates
    cards = []
    for i, c in enumerate(analysis.get("candidates", []), 1):
        ev_rows, extra, quotes, sids, succ = [], [], [], set(), []
        for k in c.get("repeat_keys", []):
            x = rep_by_key.get(k)
            if x:
                ev_rows.append(f"<tr><td>{E(kname(k))}</td><td class='num'>{x['n']}</td><td class='num'>{x['days']}</td>"
                               f"<td class='num'>{x['sessions']}</td><td class='num'>{x['last'][5:]}</td></tr>")
                quotes += x["examples"][:2]
                sids |= x["sids"]
                succ.append(r.t("success_line", k=E(kname(k)), n=x["n"], d=x["days"]))
            else:
                extra.append(r.t("ev_missing", k=E(kname(k))))
        for k in c.get("commands", []):
            extra.append(r.t("ev_cmd", k=E(k), n=cmd_count.get(k, 0)))
        for ft in c.get("friction_types", []):
            if sids:
                n = sum(((sess_by_sid.get(s_) or {}).get("facets") or {}).get("friction_counts", {}).get(ft, 0) for s_ in sids)
                extra.append(r.t("ev_fric", f=E(r.label("friction", ft)), n=n))
        ev_head = "".join(f"<th>{E(h)}</th>" for h in r.t("ev_cols"))
        evidence = ((f"<table class='ev'><thead><tr>{ev_head}</tr></thead><tbody>{''.join(ev_rows)}</tbody></table>" if ev_rows else "")
                    + (f"<ul class='evx'>{''.join('<li>' + x + '</li>' for x in extra)}</ul>" if extra else ""))
        qhtml = "".join(f"<li>{E(q)}</li>" for q in quotes[:3])

        # design: what exactly gets built
        steps = []
        for st in c.get("steps", []):
            st = st if isinstance(st, dict) else {"text": st}
            human = bool(st.get("manual"))
            steps.append(f"<li><span class='stp {'h' if human else 'a'}'>{r.t('step_human' if human else 'step_auto')}</span>"
                         f"{E(r.tx(st.get('text')))}</li>")
        design_rows = [(r.t("trigger"), E(r.tx(c.get("trigger")))),
                       (r.t("steps"), f"<ol class='steps'>{''.join(steps)}</ol>" if steps else ""),
                       (r.t("output"), E(r.tx(c.get("output")))),
                       (r.t("where"), f"<code>{E(r.tx(c.get('where')))}</code>" if r.tx(c.get("where")) else ""),
                       (r.t("manual"), E(r.tx(c.get("keep_manual"))))]
        design = "".join(f"<dt>{h}</dt><dd>{v}</dd>" for h, v in design_rows if v)
        prompt = r.tx(c.get("prompt"))
        effort = r.t("effort").get(str(c.get("effort", "")).upper(), "")
        badges = "".join(f"<span class='badge'>{E(x)}</span>" for x in [r.tx(c.get("type")), effort] if x)
        note = r.tx(c.get("note"))
        cards.append(f"""
<article class="cand">
  <header class="ch"><span class="rank">{i}</span><h3>{E(r.tx(c.get('title')))}</h3><span class="badges">{badges}</span></header>
  <div class="ba">
    <div class="b"><h4>{r.t('cand_now')}</h4><p>{E(r.tx(c.get('problem')))}</p></div>
    <div class="arrow" aria-hidden="true">→</div>
    <div class="a"><h4>{r.t('cand_auto')}</h4><p>{E(r.tx(c.get('approach')))}</p></div>
  </div>
  {blk(r.t('cand_evidence'), evidence, E(r.t('sum_evidence', r=len(ev_rows), c=len(c.get('commands', [])))))}
  {blk(r.t('quotes'), ('<ul class="quotes">' + qhtml + '</ul>') if qhtml else '', E(r.t('sum_quotes', n=len(quotes[:3]))))}
  {blk(r.t('design'), ('<dl class="design">' + design + '</dl>') if design else '', E(r.tx(c.get('trigger'))))}
  {blk(r.t('success'), ('<ul class="succ">' + ''.join('<li>' + x + '</li>' for x in succ) + '</ul>') if succ else '', E(r.t('sum_success', n=len(succ))))}
  {blk(r.t('prompt'), ('<div class="prompt"><pre>' + E(prompt) + '</pre><button type="button" class="copy" data-done="' + E(r.t('copied')) + '">' + r.t('copy') + '</button></div>') if prompt else '', E(r.t('sum_prompt')), open_=True)}
  {('<p class="note">' + E(note) + '</p>') if note else ''}
</article>""")
    sections.append(("candidates", r.t("cand_h"), r.t("cand_lede"),
                     "".join(cards) or f"<p class='muted'>{r.t('no_cand')}</p>"))

    # ---- since last run
    if prev:
        keys = sorted(set(prev["repeats"]) | set(rep_by_key),
                      key=lambda k: -(rep_by_key.get(k, {}).get("n", 0) + prev["repeats"].get(k, {}).get("n", 0)))
        tags = r.t("chg_tags")
        rows = []
        for k in keys[:20]:
            b = prev["repeats"].get(k)
            nw = rep_by_key.get(k)
            bn, bd = (b["n"], b["days"]) if b else (0, 0)
            nn, nd = (nw["n"], nw["days"]) if nw else (0, 0)
            d = nn - bn
            tag = "new" if not b else ("gone" if not nw else ("down" if d < 0 else ("up" if d > 0 else "same")))
            cls = {"down": "down", "gone": "down", "up": "up", "new": "up"}.get(tag, "")
            rows.append(f"<tr><td>{E(kname(k))}</td><td class='num'>{r.t('chg_cell', n=bn, d=bd)}</td><td class='num'>{r.t('chg_cell', n=nn, d=nd)}</td>"
                        f"<td class='num {cls}'>{'+' if d > 0 else ''}{d}</td><td class='{cls}'>{tags[tag]}</td></tr>")
        lede = E(r.t("chg_lede", ps=prev["since"], pu=prev["until"], pd=prev["days"], pp=prev["prompts"],
                     s=stats["since"], u=stats["until"], d=stats["days"], p=stats["prompts"]))
        head = "".join(f"<th>{E(x)}</th>" for x in r.t("chg_cols"))
        sections.append(("changes", r.t("chg_h"), lede,
                         f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"))
    elif history_on:
        sections.append(("changes", r.t("chg_h"), r.t("chg_none"), ""))

    # ---- task types
    cat_rows = [(names[c], cat_counts[c], r.t("cat_sub", pct=f"{cat_counts[c]*100/total:.0f}", time=r.dur(cat_minutes[c]),
                                              n=len(sess_by_cat[c]))) for c in cat_order]
    desc_rows = "".join(f"<tr><td>{E(names[c])}</td><td class='muted'>{E(r.tx(cat_meta.get(c, {}).get('desc')))}</td></tr>"
                        for c in cat_order if r.tx(cat_meta.get(c, {}).get("desc")))
    head = "".join(f"<th>{E(x)}</th>" for x in r.t("tasks_cols"))
    sections.append(("tasks", r.t("tasks_h"), r.t("tasks_lede"),
                     hbar(r, cat_rows, U_CNT, highlight_first=True)
                     + (f"<p class='src'>{r.t('unlabeled', n=unlabeled)}</p>" if unlabeled else "")
                     + (f"<table class='compact'><thead><tr>{head}</tr></thead><tbody>{desc_rows}</tbody></table>" if desc_rows else "")))

    # ---- repeats
    rep_rows = []
    for x in reps[:25]:
        desc = r.tx(rep_meta.get(x["key"], {}).get("desc"))
        ex = "<br>".join(E(t[:110]) for t in x["examples"])
        rep_rows.append(f"<tr><td><b>{E(kname(x['key']))}</b>{('<div class=muted>' + E(desc) + '</div>') if desc else ''}</td>"
                        f"<td class='num'>{x['n']}</td><td class='num'>{x['days']}</td><td class='num'>{x['sessions']}</td>"
                        f"<td class='num'>{x['first'][5:]}–{x['last'][5:]}</td><td class='ex'>{ex}</td></tr>")
    head = "".join(f"<th>{E(x)}</th>" for x in r.t("rep_cols"))
    empty = f"<tr><td colspan='6' class='muted'>{r.t('none')}</td></tr>"
    sections.append(("repeats", r.t("rep_h"), r.t("rep_lede"),
                     f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rep_rows) or empty}</tbody></table>"))

    # ---- friction (/insights)
    if insights.get("available"):
        fr_rows = [(r.label("friction", k), v, "") for k, v in insights["friction"]]
        oc_rows = [(r.label("outcome", k), v, "") for k, v in insights["outcome"]]
        sa_rows = [(r.label("satisfaction", k), v, "") for k, v in insights["satisfaction"]]
        notes = ""
        fcount = dict(insights["friction"])
        for f in analysis.get("frictions", []):
            exs = f.get("examples", [])
            exs = exs.get(r.lang, []) if isinstance(exs, dict) else exs
            exhtml = "".join(f"<li>{E(r.tx(x))}</li>" for x in exs)
            cnt = fcount.get(f.get("type"))
            notes += (f"<div class='fric'><h3>{E(r.tx(f.get('title')))}"
                      + (f" <span class='cnt num'>{cnt}{U_X}</span>" if cnt else "") + "</h3>"
                      f"<p>{E(r.tx(f.get('desc')))}</p>{('<ul>' + exhtml + '</ul>') if exhtml else ''}</div>")
        cov = r.t("fr_cov", a=insights["sessions_with_facets"], b=insights["sessions_total"],
                  c=insights["prompts_covered"], dd=insights["prompts_total"])
        lede = E(r.t("fr_lede", cov=cov, d=insights.get("latest_report_date") or "-"))
        sections.append(("friction", r.t("fr_h"), lede, notes + "<div class='cols'>"
                         + figure(r.t("fr_types"), hbar(r, fr_rows, unit=U_X, width=520, highlight_first=True))
                         + figure(r.t("fr_outcome"), hbar(r, oc_rows, unit=U_IT, width=520))
                         + figure(r.t("fr_satis"), hbar(r, sa_rows, unit=U_X, width=520)) + "</div>"))
    else:
        sections.append(("friction", r.t("fr_h"), r.t("fr_missing"), ""))

    # ---- weekly, commands, when/where, sessions, notes
    sections.append(("weekly", r.t("wk_h"), r.t("wk_lede"), heatmap(r, prompts, cat_order, names, weeks)))
    skills_rows = [(k, v, "") for k, v in tools["skills"]][:10]
    mcp_rows = [(k, v, "") for k, v in tools["mcp_servers"]][:8]
    sections.append(("commands", r.t("cmd_h"), "", "<div class='cols'>"
                     + figure(r.t("cmd_work"), hbar(r, work_cmds, unit=U_X, width=520), r.t("cmd_util", n=f"{util_total:,}"))
                     + figure(r.t("skills"), hbar(r, skills_rows, unit=U_X, width=520))
                     + figure(r.t("mcp"), hbar(r, mcp_rows, unit=U_X, width=520)) + "</div>"))
    sections.append(("when", r.t("when_h"), "", "<div class='cols'>"
                     + figure(r.t("daily"), daybars(r, stats), r.t("weekend"))
                     + figure(r.t("proj"), hbar(r, proj_rows, unit=U_CNT, width=520)) + "</div>"))
    top_sessions = sorted(sessions, key=lambda s: -s["prompts"])[:10]
    sess_rows = "".join(
        f"<tr><td class='num'>{E(s['sid'])}</td><td>{E(s['project'])}</td><td>{E(s['title'] or r.t('untitled'))}</td>"
        f"<td class='num'>{s['prompts']}</td><td class='num'>{E(r.dur(s.get('active_min', 0)))}</td><td class='num'>{E((s['start'] or '')[5:10])}</td>"
        f"<td>{E(r.label('outcome', s['facets'].get('outcome') or 'unknown')) if s.get('facets') else '–'}</td></tr>"
        for s in top_sessions)
    head = "".join(f"<th>{E(x)}</th>" for x in r.t("ses_cols"))
    sections.append(("sessions", r.t("ses_h"), "", f"<table><thead><tr>{head}</tr></thead><tbody>{sess_rows}</tbody></table>"))
    obs = "".join(f"<li>{E(r.tx(o))}</li>" for o in analysis.get("observations", []))
    if obs:
        sections.append(("notes", r.t("obs_h"), "", f"<ol class='obs'>{obs}</ol>"))

    counts = {"areas": len(area_cards), "candidates": len(cards), "tasks": len(cat_order), "repeats": len(reps),
              "friction": len(insights.get("friction") or []), "weekly": len(weeks), "commands": len(work_cmds),
              "sessions": len(top_sessions), "notes": len(analysis.get("observations", []))}
    nav_names = r.t("nav")
    # ids carry the language so the two pages in one file don't collide
    nav = "<div class='links'>" + "".join(f"<a href='#{r.lang}-{sid}' data-target='{r.lang}-{sid}'>{E(nav_names[sid])}</a>"
                                          for sid, *_ in sections) + "</div>"
    # the controls sit outside the scrolling link strip so they never get cut off
    nav += ("<div class='ctl'><span class='folds'><button type='button' class='fold' data-open='1'>"
            + E(r.t("expand_all")) + "</button><button type='button' class='fold' data-open='0'>" + E(r.t("collapse_all"))
            + "</button></span><span class='langs'><button type='button' class='lang' data-set='ko'>한국어</button>"
            "<button type='button' class='lang' data-set='en'>English</button></span></div>")
    body = "\n".join(f"<section id='{r.lang}-{sid}'>{section(i, sid, title, lede, inner, r.t('count', n=counts[sid]) if counts.get(sid) else '')}</section>"
                     for i, (sid, title, lede, inner) in enumerate(sections, 1))
    generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    scope_txt = r.t("scope", x=E(stats["project_filter"])) if stats.get("project_filter") else ""

    figs = [
        (f"{stats['prompts']:,}", r.t("t_prompts"), delta_txt),
        (r.dur(stats.get("active_min", 0)), r.t("t_active"), r.t("t_active_sub")),
        (f"{stats['sessions']}", r.t("t_sessions"), r.t("t_sessions_sub", a=stats["active_days"], d=stats["days"])),
        (f"{len(reps)}", r.t("t_repeats"), r.t("t_repeats_sub")),
        (f"{stats['tool_calls']:,}", r.t("t_tools"), r.t("t_tools_sub")),
    ]
    keyfigs = "".join(f"<div class='kf'><b class='num'>{E(v)}</b><span>{E(l)}</span><small>{E(s)}</small></div>" for v, l, s in figs)

    page = f"""<div class="pg" lang="{r.lang}" data-lang="{r.lang}">
<nav class="toc" aria-label="sections"><div class="in">{nav}</div></nav>
<main>
<div class="mast">
  <h1>{E(r.t('title'))}</h1>
  <p class="dek">{r.t('subtitle', since=E(stats['since']), until=E(stats['until']), days=stats['days'], scope=scope_txt)}</p>
  <p class="src">{E(r.t('meta', gen=generated))}</p>
</div>
<div class="keyfigs">{keyfigs}</div>
{body}
<details class="method"><summary>{r.t('method_h')}</summary><p>{r.t('method')}</p></details>
</main>
</div>"""
    return page, {"unlabeled": unlabeled, "categories": len(cat_order), "repeat_keys": len(reps)}


CSS = """
:root{--paper:#fff;--ink:#121417;--slate:#4d5a63;--mute:#7d8a93;--rule:#121417;--line:#d9dee2;--zebra:#f2f4f6;
--cell:#eef1f4;--red:#d7261e;--blue:#1f5f8b;--blue-lt:#9cb7cc;--up:#d7261e;--down:#1f7a5c}
@media (prefers-color-scheme:dark){:root{--paper:#0e1113;--ink:#e9ecee;--slate:#a9b4bb;--mute:#7f8b93;--rule:#e9ecee;
--line:#2a3136;--zebra:#161b1f;--cell:#1a2025;--red:#ff4b3e;--blue:#5b9bd0;--blue-lt:#2f5574;--up:#ff6a5e;--down:#45b98e}}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);
font:16px/1.6 "Pretendard","Apple SD Gothic Neo","Noto Sans KR",-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
word-break:keep-all;-webkit-font-smoothing:antialiased}
.num{font-variant-numeric:tabular-nums lining-nums}
nav.toc{position:sticky;top:0;z-index:10;background:var(--paper);border-bottom:2px solid var(--rule)}
nav.toc .in{max-width:1120px;margin:0 auto;padding:0 20px;display:flex;align-items:stretch;gap:12px}
nav.toc .links{display:flex;flex:1 1 auto;min-width:0;overflow-x:auto;scrollbar-width:none;-webkit-mask-image:linear-gradient(90deg,#000 calc(100% - 24px),transparent);mask-image:linear-gradient(90deg,#000 calc(100% - 24px),transparent)}
nav.toc .links::-webkit-scrollbar{display:none}
nav.toc .ctl{display:flex;align-items:center;flex:none}
nav.toc a{flex:none;font-size:14px;font-weight:600;color:var(--slate);text-decoration:none;padding:12px 12px 10px;
border-bottom:3px solid transparent;margin-bottom:-2px;white-space:nowrap}
nav.toc a:first-child{padding-left:0}
nav.toc a:hover{color:var(--ink)} nav.toc a.on{color:var(--ink);border-bottom-color:var(--red)}
nav.toc .sp{display:none}
@media (max-width:720px){nav.toc .folds{display:none}}
nav.toc .langs{display:flex;align-items:center;gap:0;flex:none}
nav.toc button.lang{font:inherit;font-size:13px;font-weight:600;color:var(--mute);background:none;border:0;padding:6px 8px;cursor:pointer}
nav.toc button.lang+button.lang{border-left:1px solid var(--line)}
nav.toc button.lang:hover{color:var(--ink)}
.pg{display:none}
html[data-lang=ko] .pg[data-lang=ko],html[data-lang=en] .pg[data-lang=en]{display:block}
html[data-lang=ko] button.lang[data-set=ko],html[data-lang=en] button.lang[data-set=en]{color:var(--ink);text-decoration:underline;text-decoration-color:var(--red);text-decoration-thickness:3px;text-underline-offset:6px}
main{max-width:1120px;margin:0 auto;padding:40px 20px 80px}
.mast h1{font-size:44px;line-height:1.1;font-weight:800;letter-spacing:-.02em;margin:0}
.mast .dek{font-size:20px;color:var(--slate);margin:10px 0 2px}
.src{font-size:13px;color:var(--mute);margin:6px 0 0}
.muted{color:var(--slate)}
.keyfigs{display:grid;grid-template-columns:repeat(5,1fr);gap:0;margin:36px 0 8px;border-top:2px solid var(--rule)}
.kf{padding:14px 16px 12px 0;border-right:1px solid var(--line);margin-right:16px}
.kf:last-child{border-right:0;margin-right:0}
.kf b{display:block;font-size:36px;line-height:1.1;font-weight:800;letter-spacing:-.02em}
.kf span{display:block;font-size:14px;font-weight:700;margin-top:6px}
.kf small{display:block;font-size:13px;color:var(--mute);margin-top:2px}
@media (max-width:820px){.keyfigs{grid-template-columns:repeat(2,1fr)} .kf{border-right:0;margin-right:0;border-bottom:1px solid var(--line)}}
section{margin-top:56px;scroll-margin-top:56px}
details.sec>summary{list-style:none;cursor:pointer}
details.sec>summary::-webkit-details-marker,details.blk>summary::-webkit-details-marker{display:none}
.sh .meta{font-size:15px;font-weight:700;color:var(--mute)}
.sh .tg{margin-left:auto;width:12px;height:12px;border-right:2.5px solid var(--ink);border-bottom:2.5px solid var(--ink);transform:rotate(45deg);position:relative;top:-4px;transition:transform .15s}
details.sec:not([open])>summary .tg{transform:rotate(-45deg);top:0}
details.sec:not([open])>summary{padding-bottom:12px}
details.sec>summary:hover h2{text-decoration:underline;text-decoration-color:var(--red);text-decoration-thickness:3px;text-underline-offset:6px}
.secbody{padding-top:4px}
.sh{display:flex;align-items:baseline;gap:14px;border-top:4px solid var(--rule);padding-top:12px}
.sh .no{font-size:15px;font-weight:800;color:var(--red)}
.sh h2{font-size:28px;line-height:1.25;font-weight:800;letter-spacing:-.01em;margin:0}
.lede{font-size:16px;color:var(--slate);margin:8px 0 22px;max-width:780px}
h3{font-size:19px;line-height:1.35;font-weight:800;margin:0}
figure{margin:0 0 8px}
figcaption{font-size:15px;font-weight:800;margin:0 0 10px}
figcaption .tag{display:block;width:32px;height:6px;background:var(--red);margin-bottom:8px}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,460px),1fr));gap:32px 48px;margin-top:20px}
svg.chart{max-width:100%;height:auto}
svg.chart text{fill:var(--ink);font-size:12.5px}
svg.chart .lab{fill:var(--slate)} svg.chart .val{fill:var(--slate)} svg.chart .val .num,svg.chart .num{fill:var(--ink);font-weight:700}
svg.chart .axis,svg.chart .base{stroke:var(--rule);stroke-width:1.5}
svg.chart .cell{font-size:12px;font-weight:700;fill:var(--ink)} svg.chart .cell.inv{fill:#fff}
table{border-collapse:collapse;width:100%;font-size:15px;margin-top:4px}
thead th{text-align:left;font-size:13px;font-weight:800;color:var(--ink);padding:8px 10px;border-bottom:2px solid var(--rule);white-space:nowrap}
tbody td{padding:9px 10px;vertical-align:top}
tbody tr:nth-child(odd) td{background:var(--zebra)}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
thead th:nth-child(n+2){text-align:right} table.compact thead th:nth-child(n+2){text-align:left}
#ko-repeats thead th:last-child,#en-repeats thead th:last-child,#ko-sessions thead th:nth-child(2),#en-sessions thead th:nth-child(2),
#ko-sessions thead th:nth-child(3),#en-sessions thead th:nth-child(3),#ko-sessions thead th:last-child,#en-sessions thead th:last-child,
#ko-changes thead th:last-child,#en-changes thead th:last-child{text-align:left}
td.ex{color:var(--slate);font-size:14px;min-width:240px}
table.compact{margin-top:20px} table.compact td{padding:6px 10px}
td.up,.up{color:var(--up);font-weight:700} td.down,.down{color:var(--down);font-weight:700}
.cand{padding:28px 0 32px;border-bottom:2px solid var(--rule)}
.cand:last-of-type{border-bottom:0}
.cand .ch{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;margin-bottom:18px}
.cand .rank{font-size:48px;line-height:.9;font-weight:800;color:var(--red);letter-spacing:-.04em;min-width:44px}
.cand .ch h3{font-size:22px;flex:1 1 320px}
.cand .badges{display:flex;gap:6px}
.cand .badge{font-size:13px;font-weight:700;border:1.5px solid var(--ink);padding:2px 8px}
.cand h4{font-size:13px;font-weight:800;color:var(--red);margin:0 0 6px}
.cand .ba{display:grid;grid-template-columns:1fr 40px 1fr;align-items:stretch;margin:0 0 18px}
.cand .ba>div:not(.arrow){padding:14px 16px}
.cand .ba .b{background:var(--zebra)}
.cand .ba .a{background:var(--paper);border:2px solid var(--ink)}
.cand .ba .b h4{color:var(--slate)}
.cand .ba p{margin:0;font-size:16px}
.cand .arrow{display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:800;color:var(--red)}
.cand .blk>div{min-width:0}
.cand details.blk{display:block;padding:0;border-top:1px solid var(--line)}
.cand details.blk>summary{display:grid;grid-template-columns:140px minmax(0,1fr);gap:12px;padding:12px 0;cursor:pointer;list-style:none;align-items:baseline}
.cand details.blk>summary h4{margin:0;position:relative;padding-left:16px}
.cand details.blk>summary h4::before{content:"";position:absolute;left:0;top:4px;width:6px;height:6px;border-right:2px solid var(--red);border-bottom:2px solid var(--red);transform:rotate(-45deg);transition:transform .15s}
.cand details.blk[open]>summary h4::before{transform:rotate(45deg);top:2px}
.cand details.blk>summary .sum{font-size:14px;color:var(--mute)}
.cand details.blk[open]>summary .sum{visibility:hidden}
.cand details.blk>summary:hover h4{color:var(--red)}
.cand details.blk>.bd{margin:-4px 0 0 152px;padding-bottom:14px;min-width:0}
.cand .blk.static h4{padding-left:16px}
nav.toc .folds{display:flex;flex:none;margin-right:10px}
nav.toc button.fold{font:inherit;font-size:13px;font-weight:600;color:var(--mute);background:none;border:0;padding:6px 8px;cursor:pointer}
nav.toc button.fold:hover{color:var(--ink)}
.cand .blk{display:grid;grid-template-columns:140px minmax(0,1fr);gap:12px;padding:12px 0;border-top:1px solid var(--line)}
.cand .blk h4{margin:2px 0 0;color:var(--ink)}
.cand table.ev{margin:0;font-size:14px;max-width:640px} .cand table.ev td,.cand table.ev th{padding:5px 8px}
.cand table.ev thead th{font-size:12px}
.cand table.rules thead th:first-child,.cand table.rules thead th:nth-child(5){text-align:left}
.cand ul{margin:0;padding:0;list-style:none}
.cand ul.evx{margin-top:6px;font-size:14px;color:var(--slate)} .cand ul.evx li{padding:1px 0}
.cand ul.quotes li{color:var(--slate);padding:1px 0} .cand ul.quotes li::before{content:"“"} .cand ul.quotes li::after{content:"”"}
.cand dl.design{display:grid;grid-template-columns:120px 1fr;gap:6px 14px;margin:0}
.cand dl.design dt{font-size:14px;font-weight:700;color:var(--slate)} .cand dl.design dd{margin:0}
.cand ol.steps{margin:0;padding-left:20px} .cand ol.steps li{padding:2px 0}
.cand .stp{display:inline-block;font-size:12px;font-weight:800;padding:0 6px;margin-right:8px;border:1.5px solid}
.cand .stp.a{color:var(--blue);border-color:var(--blue)} .cand .stp.h{color:var(--red);border-color:var(--red)}
.cand ul.succ li{padding:1px 0}
.cand .hint{font-size:13px;color:var(--mute);margin:0 0 6px}
.cand .prompt{position:relative;background:var(--zebra);border-left:4px solid var(--ink)}
.cand .prompt pre{margin:0;padding:12px 76px 12px 14px;white-space:pre-wrap;word-break:keep-all;font:14px/1.6 inherit;font-family:inherit}
.cand .prompt button.copy{position:absolute;top:8px;right:8px;font:inherit;font-size:13px;font-weight:700;background:var(--ink);color:var(--paper);border:0;padding:4px 10px;cursor:pointer}
.cand .note{font-size:14px;color:var(--mute);margin:12px 0 0}
@media (max-width:720px){.cand details.blk>summary{grid-template-columns:1fr;gap:2px} .cand details.blk>.bd{margin-left:0} .cand .ba{grid-template-columns:1fr} .cand .arrow{transform:rotate(90deg);height:32px} .cand .blk{grid-template-columns:1fr;gap:4px} .cand dl.design{grid-template-columns:1fr}}
.cand.area .kind{margin-top:-8px}
.cand ol.flow{display:flex;flex-wrap:wrap;gap:6px 0;margin:0;padding:0;list-style:none;counter-reset:st}
.cand ol.flow li{counter-increment:st;font-size:14px;font-weight:600;padding:4px 10px;border:1.5px solid var(--ink);background:var(--paper)}
.cand ol.flow li::before{content:counter(st) " ";color:var(--red);font-weight:800}
.cand ol.flow li+li{margin-left:22px;position:relative}
.cand ol.flow li+li::after{content:"→";position:absolute;left:-17px;top:3px;color:var(--red);font-weight:800}
.cand table.prop{margin:0;font-size:14px} .cand table.prop td{padding:7px 8px;vertical-align:top}
.cand table.prop thead th{font-size:12px;text-align:left!important}
.cand ul.holds{margin:0;padding-left:16px;list-style:disc} .cand ul.holds li{padding:1px 0}
.cand p.warn{margin:8px 0 0;font-size:14px;font-weight:700;color:var(--red)}
.fric{padding:0 0 18px;margin:0 0 18px;border-bottom:1px solid var(--line)}
.fric .cnt{font-size:15px;color:var(--red);margin-left:6px}
.fric p{margin:6px 0} .fric ul{margin:4px 0 0;padding-left:18px;color:var(--slate)}
ol.obs{margin:0;padding-left:22px;font-size:17px} ol.obs li{padding:6px 0} ol.obs li::marker{color:var(--red);font-weight:800}
code{font-family:ui-monospace,Menlo,monospace;font-size:.88em;background:var(--zebra);padding:1px 4px}
details.method{margin-top:64px;border-top:2px solid var(--rule);padding-top:12px;color:var(--slate);font-size:14px}
details.method summary{cursor:pointer;font-weight:800;color:var(--ink)}
@media print{nav.toc{display:none} section{break-inside:avoid-page} .sh .tg{display:none}}
"""

JS = """
(function(){
  var root = document.documentElement;
  function setLang(l){
    root.dataset.lang = l; root.lang = l;
    try { localStorage.setItem('wpr-lang', l); } catch (e) {}
    spy();
  }
  document.querySelectorAll('button.lang').forEach(function(b){
    b.addEventListener('click', function(){
      var y = window.scrollY;
      setLang(b.dataset.set);
      window.scrollTo(0, y);
    });
  });
  var io = null;
  function spy(){
    if (io) io.disconnect();
    if (!('IntersectionObserver' in window)) return;
    var pg = document.querySelector('.pg[data-lang="' + root.dataset.lang + '"]');
    if (!pg) return;
    var bar = pg.querySelector('nav.toc .links');
    var links = pg.querySelectorAll('nav.toc a');
    var byId = {};
    links.forEach(function(a){ byId[a.dataset.target] = a; });
    io = new IntersectionObserver(function(entries){
      entries.forEach(function(e){
        if (!e.isIntersecting) return;
        var a = byId[e.target.id];
        if (!a) return;
        links.forEach(function(x){ x.classList.remove('on'); });
        a.classList.add('on');
        // Move only the nav strip, instantly and only when the link is out of view:
        // scrollIntoView or a smooth strip scroll can fight the page's own smooth scroll.
        var l = a.offsetLeft - bar.offsetLeft, r = l + a.offsetWidth;
        if (l < bar.scrollLeft || r > bar.scrollLeft + bar.clientWidth) {
          bar.scrollLeft = Math.max(0, l - (bar.clientWidth - a.offsetWidth) / 2);
        }
      });
    }, {rootMargin: '-45% 0px -50% 0px'});
    pg.querySelectorAll('main section[id]').forEach(function(s){ io.observe(s); });
  }
  document.querySelectorAll('button.copy').forEach(function(b){
    b.addEventListener('click', function(){
      var text = b.previousElementSibling.textContent, label = b.textContent;
      function done(){ b.textContent = b.dataset.done; setTimeout(function(){ b.textContent = label; }, 1500); }
      if (navigator.clipboard && window.isSecureContext !== false) {
        navigator.clipboard.writeText(text).then(done, function(){ fallback(); });
      } else { fallback(); }
      function fallback(){
        var t = document.createElement('textarea'); t.value = text; document.body.appendChild(t);
        t.select(); try { document.execCommand('copy'); done(); } catch (e) {} document.body.removeChild(t);
      }
    });
  });
  function openTarget(id){
    var t = document.getElementById(id);
    if (t) { var d = t.querySelector('details.sec'); if (d) d.open = true; }
  }
  document.querySelectorAll('nav.toc a').forEach(function(a){
    a.addEventListener('click', function(){ openTarget(a.dataset.target); });
  });
  document.querySelectorAll('button.fold').forEach(function(b){
    b.addEventListener('click', function(){
      var open = b.dataset.open === '1';
      b.closest('.pg').querySelectorAll('details').forEach(function(d){ d.open = open; });
    });
  });
  window.addEventListener('beforeprint', function(){ document.querySelectorAll('details').forEach(function(d){ d.open = true; }); });
  if (location.hash) openTarget(location.hash.slice(1));

  var saved = null;
  try { saved = localStorage.getItem('wpr-lang'); } catch (e) {}
  if (saved && document.querySelector('.pg[data-lang="' + saved + '"]')) setLang(saved); else spy();
})();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--history")
    ap.add_argument("--lang", help="language shown first: ko or en; defaults to analysis.json's lang, then en")
    a = ap.parse_args()
    prompts, sessions, tools, stats, insights, analysis = load(a.work)
    first = R(a.lang or analysis.get("lang") or "en").lang
    langs = [first] + [l for l in T if l != first]
    prev = history_compare(a.history, stats, repeat_table(prompts))
    pages, meta = [], {}
    for l in langs:
        page, m = build_page(R(l), prompts, sessions, tools, stats, insights, analysis, prev, bool(a.history))
        pages.append(page)
        meta = meta or m
    r = R(first)
    doc = (f"<!doctype html>\n<html lang='{first}' data-lang='{first}'><head><meta charset='utf-8'>"
           f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>{E(r.t('title'))} {E(stats['since'])}–{E(stats['until'])}</title>"
           f"<style>{CSS}</style></head><body>\n{''.join(pages)}\n<script>{JS}</script>\n</body></html>")
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    with open(a.output, "w") as fh:
        fh.write(doc)
    print(json.dumps({"output": a.output, "lang": first, "prompts": len(prompts), "unlabeled": meta["unlabeled"],
                      "categories": meta["categories"], "repeat_keys": meta["repeat_keys"],
                      "candidates": len(analysis.get("candidates", [])),
                      "insights": insights.get("available", False),
                      "compared_with": f"{prev['since']}~{prev['until']}" if prev else None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
