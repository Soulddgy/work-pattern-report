#!/usr/bin/env python3
"""Extract work-pattern material from Claude Code transcripts (~/.claude/projects/*/*.jsonl).

Outputs (in --out):
  prompts.jsonl   one human-typed message per line
  sessions.json   per-session title, span, prompt count, tool use, /insights facets
  tools.json      tool, Bash command, skill and MCP counts for the window
  stats.json      window, totals, per-day/week/project counts, previous same-length window
  insights.json   /insights friction, outcome and satisfaction totals for the window
  batches/        prompt batches for the model to label, grouped by session for context

Usage:
  python3 extract.py --out DIR [--days 30 | --since YYYY-MM-DD --until YYYY-MM-DD]
                     [--project SUBSTRING] [--batch-size 150]
"""
import argparse
import collections
import datetime as dt
import glob
import json
import os
import re
import shlex

KST = dt.timezone(dt.timedelta(hours=9))
PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
HOME_PREFIX = "-" + os.path.expanduser("~").strip("/").replace("/", "-")

# Tools whose subcommand is part of the command signature
SUBCMD_TOOLS = {"git", "gh", "adb", "npx", "npm", "pnpm", "yarn", "docker", "kubectl", "brew", "pip", "pip3"}
# Leading keywords: drop them and look at what follows
SKIP_WORDS = {"then", "do", "done", "fi", "else", "elif", "if", "!", "{", "}", "[[", "]]", "export", "local"}
# Shell plumbing: drop the whole segment
SKIP_SEGMENT = {"cd", "set", "echo", "printf", "sleep", "true", "false", "for", "while", "until", "case", "esac",
                "read", "source", ".", ":", "test", "[", "wait", "trap", "unset", "shift", "return", "exit", "break"}


def short_project(dirname: str) -> str:
    name = dirname
    if name.startswith(HOME_PREFIX):
        name = name[len(HOME_PREFIX):]
    name = name.strip("-")
    return name or "~"


def parse_ts(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(KST)
    except ValueError:
        return None


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    return ""


def is_human_prompt(e) -> bool:
    if e.get("type") != "user" or e.get("isSidechain") or e.get("isMeta"):
        return False
    origin = e.get("origin")
    if isinstance(origin, dict):
        return origin.get("kind") == "human"
    # Older transcripts have no origin: a plain-string body that does not start with a system tag is human input
    c = e.get("message", {}).get("content")
    return isinstance(c, str) and not c.lstrip().startswith("<")


USAGE_DIR = os.path.expanduser("~/.claude/usage-data")
# Summary the system inserts as a user message after /compact: not written by a human
COMPACT_PREFIXES = ("This session is being continued from a previous conversation",)

SLASH_RE = re.compile(r"<command-name>/?([^<]+)</command-name>")
PASTE_RE = re.compile(r"<pasted_content[^>]*>.*?</pasted_content>", re.S)


def clean_prompt(t: str) -> str:
    t = PASTE_RE.sub("[pasted]", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def command_signatures(cmd: str):
    """Meaningful executables in one Bash command, e.g. 'git commit', 'adb install', 'gradlew assemble*'."""
    aliases = {}
    for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)=(\"[^\"]*\"|'[^']*'|\S+)", cmd):
        val = m.group(2).strip("\"'")
        base = os.path.basename(val.rstrip("/"))
        if base:
            aliases[m.group(1)] = base
    # Heredoc bodies and line continuations are not commands
    cmd = re.sub(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\b", " ", cmd, flags=re.S)
    cmd = cmd.replace("\\\n", " ")
    cmd = re.sub(r"\d*[<>]&\d+|&>", " ", cmd)  # redirects such as 2>&1
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|()\n`")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    segs, cur = [], []
    try:
        for tok in lex:
            if tok and set(tok) <= set(";&|()\n`"):
                segs.append(cur)
                cur = []
            else:
                cur.append(tok)
    except ValueError:
        # Unbalanced quotes: take a rough look at the first line only
        segs, cur = [cmd.split("\n")[0].split()], []
    segs.append(cur)
    sigs = []
    for words in segs:
        words = [w for w in words if w]
        if words and words[0] in ("sudo", "time", "nohup", "env", "exec"):
            words = words[1:]
        while words and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]) or words[0] in SKIP_WORDS):
            words = words[1:]
        # A redirect target (> file) is not a word
        clean, skip = [], False
        for w in words:
            if skip:
                skip = False
                continue
            if re.match(r"^\d*[<>]{1,2}$", w):
                skip = True
                continue
            if re.match(r"^\d*[<>]", w):
                continue
            clean.append(w)
        words = clean
        if not words or words[0] in SKIP_SEGMENT:
            continue
        w0 = words[0]
        m = re.match(r"^\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?$", w0)
        if m:
            w0 = aliases.get(m.group(1), "")
        w0 = os.path.basename(w0)
        if not w0 or not re.match(r"^[A-Za-z][A-Za-z0-9_.+-]*$", w0) or w0 in SKIP_WORDS or w0 in SKIP_SEGMENT:
            continue
        if w0.endswith(".sh") or w0.endswith(".py") and w0 not in ("python", "python3"):
            sigs.append("script " + w0)
            continue
        if w0 in ("gradlew", "gradle"):
            tasks = [w for w in words[1:] if not w.startswith("-")]
            norm = sorted({re.sub(r"^(assemble|test|lint|detekt|install|bundle|clean|connected)\w*", r"\1*", t.split(":")[-1])
                           for t in tasks}) or ["(flags only)"]
            sigs.append("gradlew " + " ".join(norm[:3]))
            continue
        if w0 in SUBCMD_TOOLS:
            rest = [w for w in words[1:] if not w.startswith("-")]
            if w0 == "adb" and words[1:2] == ["-s"]:
                rest = [w for w in words[3:] if not w.startswith("-")]
            sigs.append(f"{w0} {rest[0]}" if rest else w0)
            continue
        if w0 in ("python", "python3"):
            rest = [w for w in words[1:] if not w.startswith("-")]
            target = os.path.basename(rest[0]) if rest else ""
            sigs.append("python3 " + (target if target.endswith(".py") else "(inline)"))
            continue
        sigs.append(w0)
    return sigs


def _read_json(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def load_insights(sid):
    """Per-session analysis (facets) and metadata (session-meta) left by /insights; empty dict if absent."""
    out = {}
    meta = _read_json(os.path.join(USAGE_DIR, "session-meta", sid + ".json"))
    if meta:
        out["meta"] = {k: meta.get(k) for k in ("duration_minutes", "git_commits", "git_pushes",
                                                "user_interruptions", "tool_errors", "first_prompt")}
    fac = _read_json(os.path.join(USAGE_DIR, "facets", sid + ".json"))
    if fac:
        out["facets"] = {k: fac.get(k) for k in ("underlying_goal", "goal_categories", "outcome", "session_type",
                                                 "user_satisfaction_counts", "claude_helpfulness",
                                                 "friction_counts", "friction_detail", "primary_success",
                                                 "brief_summary")}
    return out


def summarize_insights(sess_out):
    reports = sorted(glob.glob(os.path.join(USAGE_DIR, "report-*.html")), key=os.path.getmtime)
    latest = reports[-1] if reports else None
    with_fac = [s for s in sess_out if s.get("facets")]
    friction, outcome, satisfaction = collections.Counter(), collections.Counter(), collections.Counter()
    for s in with_fac:
        f = s["facets"]
        friction.update(f.get("friction_counts") or {})
        outcome[f.get("outcome") or "unknown"] += 1
        satisfaction.update(f.get("user_satisfaction_counts") or {})
    return {
        "available": bool(with_fac),
        "latest_report": latest,
        "latest_report_date": (dt.datetime.fromtimestamp(os.path.getmtime(latest), KST).date().isoformat()
                               if latest else None),
        "sessions_total": len(sess_out),
        "sessions_with_facets": len(with_fac),
        "prompts_covered": sum(s["prompts"] for s in with_fac),
        "prompts_total": sum(s["prompts"] for s in sess_out),
        "friction": friction.most_common(),
        "outcome": outcome.most_common(),
        "satisfaction": satisfaction.most_common(),
        "minutes_total": sum((s.get("meta") or {}).get("duration_minutes") or 0 for s in sess_out),
    }


def _born(path):
    st = os.stat(path)
    t = getattr(st, "st_birthtime", None) or st.st_mtime
    return dt.datetime.fromtimestamp(t, KST).date().isoformat()


def _front(path):
    """name and description from a Markdown file's front matter (one-line values only)."""
    out = {}
    try:
        with open(path, errors="ignore") as fh:
            text = fh.read(4000)
    except OSError:
        return out
    if text.startswith("---"):
        head = text[3:].split("\n---", 1)[0]
        for line in head.splitlines():
            if ":" in line and not line.startswith((" ", "\t")):
                k, v = line.split(":", 1)
                if k.strip() in ("name", "description"):
                    out[k.strip()] = v.strip().strip('"\'')[:300]
    return out


def scan_assets(cwds, projdirs):
    """What the user already built for each place they work: skills, CLAUDE.md and memory, with creation dates.

    The interpretation step uses this to tell "build a new skill set" from "extend what is there", and the report
    counts rules the user re-stated after the related skill already existed."""
    places = []
    home = os.path.expanduser("~")
    for cwd in sorted(cwds):
        if cwd == home:
            continue  # ~/.claude/skills is listed once, as user_skills
        entry = {"cwd": cwd, "skills": [], "claude_md": None}
        for sk in sorted(glob.glob(os.path.join(cwd, ".claude", "skills", "*", "SKILL.md"))):
            fm = _front(sk)
            entry["skills"].append({"name": fm.get("name") or os.path.basename(os.path.dirname(sk)),
                                    "description": fm.get("description", ""), "created": _born(sk),
                                    "modified": dt.datetime.fromtimestamp(os.path.getmtime(sk), KST).date().isoformat()})
        cm = os.path.join(cwd, "CLAUDE.md")
        if os.path.exists(cm):
            entry["claude_md"] = {"created": _born(cm), "bytes": os.path.getsize(cm)}
        if entry["skills"] or entry["claude_md"]:
            places.append(entry)
    memory = []
    for pd in sorted(projdirs):
        for m in sorted(glob.glob(os.path.join(PROJECTS_DIR, pd, "memory", "*.md"))):
            if os.path.basename(m) == "MEMORY.md":
                continue
            fm = _front(m)
            memory.append({"project": short_project(pd), "file": os.path.basename(m), "name": fm.get("name", ""),
                           "description": fm.get("description", ""), "created": _born(m)})
    user_skills = []
    for sk in sorted(glob.glob(os.path.expanduser("~/.claude/skills/*/SKILL.md"))):
        fm = _front(sk)
        user_skills.append({"name": fm.get("name") or os.path.basename(os.path.dirname(sk)),
                            "description": fm.get("description", ""), "created": _born(sk)})
    return {"places": places, "user_skills": user_skills, "memory": memory}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--project", help="only project directories whose name contains this")
    ap.add_argument("--batch-size", type=int, default=150)
    ap.add_argument("--no-assets", action="store_true",
                    help="don't collect existing skills, CLAUDE.md and memory (for blind tests)")
    a = ap.parse_args()

    today = dt.datetime.now(KST).date()
    until = dt.date.fromisoformat(a.until) if a.until else today
    since = dt.date.fromisoformat(a.since) if a.since else until - dt.timedelta(days=a.days - 1)
    span = (until - since).days + 1
    prev_since, prev_until = since - dt.timedelta(days=span), since - dt.timedelta(days=1)

    os.makedirs(os.path.join(a.out, "batches"), exist_ok=True)
    prompts, sessions = [], {}
    tools = collections.Counter()
    cmds = collections.Counter()
    skills = collections.Counter()
    slash = collections.Counter()
    mcp = collections.Counter()
    prev_prompts = collections.Counter()

    files = sorted(glob.glob(os.path.join(PROJECTS_DIR, "*", "*.jsonl")))
    for f in files:
        projdir = os.path.basename(os.path.dirname(f))
        if a.project and a.project not in projdir:
            continue
        proj = short_project(projdir)
        sid = os.path.basename(f)[:-6]
        s = {"id": sid, "project": proj, "title": None, "start": None, "end": None, "prompts": 0,
             "tools": collections.Counter(), "commands": collections.Counter(), "skills": collections.Counter()}
        in_window = False
        with open(f, errors="ignore") as fh:
            for line in fh:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = e.get("type")
                if t in ("ai-title", "custom-title"):
                    title = e.get("customTitle") or e.get("aiTitle") or e.get("title")
                    if title and (t == "custom-title" or not s.get("_custom")):
                        s["title"] = title
                        s["_custom"] = s.get("_custom") or t == "custom-title"
                    continue
                ts = parse_ts(e.get("timestamp"))
                if ts is None:
                    continue
                d = ts.date()
                if prev_since <= d <= prev_until and is_human_prompt(e):
                    prev_prompts[proj] += 1
                if not (since <= d <= until) or e.get("isSidechain"):
                    continue
                if t in ("user", "assistant"):
                    s.setdefault("events", []).append(ts)
                    if e.get("cwd") and not s.get("cwd"):
                        s["cwd"] = e["cwd"]
                if t == "user":
                    body = text_of(e.get("message", {}).get("content"))
                    for m in SLASH_RE.finditer(body):
                        slash[m.group(1).strip()] += 1
                    if not is_human_prompt(e):
                        continue
                    txt = clean_prompt(body)
                    if not txt or txt.startswith("[Request interrupted"):
                        continue
                    if txt.startswith(COMPACT_PREFIXES):
                        s["compacts"] = s.get("compacts", 0) + 1
                        continue
                    in_window = True
                    s["prompts"] += 1
                    s["start"] = s["start"] or ts.isoformat()
                    s["end"] = ts.isoformat()
                    prompts.append({"ts": ts.isoformat(timespec="minutes"), "date": d.isoformat(),
                                    "week": (d - dt.timedelta(days=d.weekday())).isoformat(),
                                    "hour": ts.hour, "project": proj, "session": sid,
                                    "source": (e.get("promptSource") or "typed"), "text": txt[:600]})
                elif t == "assistant":
                    for c in e.get("message", {}).get("content") or []:
                        if not (isinstance(c, dict) and c.get("type") == "tool_use"):
                            continue
                        in_window = True
                        name = c.get("name", "?")
                        tools[name] += 1
                        s["tools"][name] += 1
                        if name.startswith("mcp__"):
                            mcp[name.split("__")[1]] += 1
                        if name == "Bash":
                            for sig in command_signatures(c.get("input", {}).get("command", "")):
                                cmds[sig] += 1
                                s["commands"][sig] += 1
                        if name == "Skill":
                            sk = c.get("input", {}).get("skill", "?")
                            skills[sk] += 1
                            s["skills"][sk] += 1
        if in_window:
            s.pop("_custom", None)
            sessions[sid] = s

    # Drop the same text re-sent within the hour (resends)
    prompts.sort(key=lambda p: p["ts"])
    dedup, last = [], {}
    for p in prompts:
        key = (p["session"], p["text"])
        if key in last and p["ts"][:13] == last[key]:
            continue
        last[key] = p["ts"][:13]
        dedup.append(p)
    prompts = dedup
    for i, p in enumerate(prompts, 1):
        p["id"] = f"p{i:04d}"

    sess_index = {sid: f"S{i:03d}" for i, sid in enumerate(sorted(sessions, key=lambda k: sessions[k]["start"] or "~"), 1)}
    for p in prompts:
        p["sid"] = sess_index[p["session"]]

    # Estimated active time: 5-minute bins with any user/Claude activity between a prompt and the next one.
    # Time away leaves no records and is excluded; long autonomous Claude runs are included.
    def bin5(x):
        return int(x.timestamp() // 300)
    by_session = collections.defaultdict(list)
    for p in prompts:
        by_session[p["session"]].append(p)
    for sid, ps in by_session.items():
        evs = sorted(sessions[sid].get("events", []))
        bounds = [dt.datetime.fromisoformat(p["ts"]) for p in ps] + [dt.datetime.max.replace(tzinfo=KST)]
        j = 0
        for i, p in enumerate(ps):
            lo, hi = bounds[i], bounds[i + 1]
            while j < len(evs) and evs[j] < lo:
                j += 1
            k, bins = j, set()
            while k < len(evs) and evs[k] < hi:
                bins.add(bin5(evs[k]))
                k += 1
            p["active_min"] = max(5, len(bins) * 5)
        sessions[sid]["active_min"] = sum(p["active_min"] for p in ps)

    with open(os.path.join(a.out, "prompts.jsonl"), "w") as fh:
        for p in prompts:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")

    sess_out = []
    for sid, s in sessions.items():
        row = {"sid": sess_index[sid], "id": sid, "project": s["project"], "cwd": s.get("cwd"), "title": s["title"],
               "start": s["start"], "end": s["end"], "prompts": s["prompts"], "compacts": s.get("compacts", 0),
               "active_min": s.get("active_min", 0),
               "tools": dict(s["tools"].most_common(8)), "commands": dict(s["commands"].most_common(10)),
               "skills": dict(s["skills"])}
        row.update(load_insights(sid))
        sess_out.append(row)
    sess_out.sort(key=lambda s: s["sid"])
    insights = summarize_insights(sess_out)
    with open(os.path.join(a.out, "sessions.json"), "w") as fh:
        json.dump(sess_out, fh, ensure_ascii=False, indent=1)

    if not a.no_assets:
        cwds = {s["cwd"] for s in sessions.values() if s.get("cwd") and os.path.isdir(s["cwd"])}
        projdirs = {os.path.basename(os.path.dirname(f)) for f in files
                    if os.path.basename(f)[:-6] in sessions}
        with open(os.path.join(a.out, "assets.json"), "w") as fh:
            json.dump(scan_assets(cwds, projdirs), fh, ensure_ascii=False, indent=1)
    elif os.path.exists(os.path.join(a.out, "assets.json")):
        os.remove(os.path.join(a.out, "assets.json"))

    with open(os.path.join(a.out, "insights.json"), "w") as fh:
        json.dump(insights, fh, ensure_ascii=False, indent=1)

    with open(os.path.join(a.out, "tools.json"), "w") as fh:
        json.dump({"tools": tools.most_common(40), "commands": cmds.most_common(60), "skills": skills.most_common(),
                   "slash_commands": slash.most_common(), "mcp_servers": mcp.most_common()}, fh, ensure_ascii=False, indent=1)

    by_day = collections.Counter(p["date"] for p in prompts)
    by_week = collections.Counter(p["week"] for p in prompts)
    by_proj = collections.Counter(p["project"] for p in prompts)
    by_hour = collections.Counter(p["hour"] for p in prompts)
    stats = {"since": since.isoformat(), "until": until.isoformat(), "days": span, "project_filter": a.project,
             "active_min": sum(p["active_min"] for p in prompts),
             "prev_since": prev_since.isoformat(), "prev_until": prev_until.isoformat(),
             "prompts": len(prompts), "sessions": len(sess_out), "active_days": len(by_day),
             "tool_calls": sum(tools.values()), "prev_prompts": sum(prev_prompts.values()),
             "by_day": sorted(by_day.items()), "by_week": sorted(by_week.items()),
             "by_project": by_proj.most_common(), "prev_by_project": prev_prompts.most_common(),
             "by_hour": sorted(by_hour.items())}
    with open(os.path.join(a.out, "stats.json"), "w") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=1)

    # Labeling batches grouped by session so short follow-ups ("commit it") can be judged in context
    by_sess = collections.defaultdict(list)
    for p in prompts:
        by_sess[p["sid"]].append(p)
    title_of = {s["sid"]: (s["title"] or "(untitled)", s["project"]) for s in sess_out}
    goal_of = {s["sid"]: (s.get("facets") or {}).get("underlying_goal") for s in sess_out}
    batches, cur, n = [], [], 0
    for sid in sorted(by_sess):
        block = [f"## {sid} · {title_of[sid][1]} · {title_of[sid][0]}"]
        if goal_of.get(sid):
            block.append(f"#  insights goal: {goal_of[sid][:200]}")
        block += [f"{p['id']} {p['date'][5:]} | {p['text'][:220]}" for p in by_sess[sid]]
        if n and n + len(block) - 1 > a.batch_size:
            batches.append(cur)
            cur, n = [], 0
        cur += block
        n += len(block) - 1
    if cur:
        batches.append(cur)
    for old in glob.glob(os.path.join(a.out, "batches", "*.txt")):
        os.remove(old)
    for i, b in enumerate(batches, 1):
        with open(os.path.join(a.out, "batches", f"batch-{i:02d}.txt"), "w") as fh:
            fh.write("\n".join(b) + "\n")

    print(json.dumps({"out": a.out, "since": stats["since"], "until": stats["until"], "prompts": len(prompts),
                      "sessions": len(sess_out), "batches": len(batches), "prev_prompts": stats["prev_prompts"],
                      "compact_summaries_skipped": sum(s["compacts"] for s in sess_out),
                      "insights": {"sessions_with_facets": insights["sessions_with_facets"],
                                   "prompts_covered": insights["prompts_covered"],
                                   "latest_report_date": insights["latest_report_date"]}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
