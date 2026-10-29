"""스킬 폴더 구조·참조 검사기. 의미(내용이 맞는지)는 판정하지 않는다 — 그건 사람·리뷰 몫이다.

검사 항목
  F1 머리말: name 이 있고 폴더명과 같다, description 이 있다
  F2 description 길이 > 200 (claude.ai 업로드 호환) — 경고
  L1 본문의 상대 링크·`references/…` `scripts/…` `assets/…` `templates/…` 경로가 실제로 있다
  N1 금지어: 없어진 스킬 이름, Codex 흔적 (보관·기록 문맥도 잡으므로 예외는 --allow 로)
  S1 scripts/ 의 .py 가 문법상 컴파일된다(실행은 하지 않는다)
종료 코드: 오류 0개면 0, 있으면 1. 경고만 있으면 0.

사용: python scripts/check_skills.py <skills 폴더> [<skills 폴더> ...] [--allow 단어 ...]
예:   python scripts/check_skills.py skills D:/work/study/.claude/skills D:/work/robo/.claude/skills
"""
from __future__ import annotations

import argparse
import py_compile
import re
import sys
from pathlib import Path

RETIRED = [
    "lecture-work", "lecture-resume", "lecture-handoff", "lecture-report", "lecture-contract",
    "lecture-guide", "lecture-sync", "lecture-package", "lecture-upload",
    "robo-work", "robo-handoff", "robo-report", "robo-tune", "robo-research-note", "robo-demo-recording",
    "goal-prompt", "todo-value-dod", "debug", "e2e-verify", "handoff", "demo-video", "worktime-json",
]
CODEX = [r"\bCodex\b", r"\.agents[/\\]", r"\bAGENTS\.md\b", r"openai\.yaml", r"\.codex[/\\]"]
PATH_RE = re.compile(r"(?<![\w/.-])((?:\.\./|\./)?(?:[\w가-힣.-]+/)*(?:references|scripts|assets|templates)/[\w가-힣./ -]*?[\w가-힣-]+\.[A-Za-z0-9]+)")
LINK_RE = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
SKIP_DIRS = {"__pycache__", ".pytest_cache", "node_modules", "runtime"}


def frontmatter(text: str) -> dict[str, str] | None:
    m = re.match(r"^\ufeff?---\r?\n(.*?)\r?\n---", text, re.S)
    if not m:
        return None
    out = {}
    for line in m.group(1).splitlines():
        kv = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if kv:
            out[kv.group(1)] = kv.group(2).strip().strip('"').strip("'")
    return out


def text_files(skill: Path):
    for p in skill.rglob("*"):
        if p.is_file() and not (SKIP_DIRS & set(p.parts)) and p.suffix in {".md", ".json", ".py", ".ps1", ".sh", ".txt", ".yaml", ".yml"}:
            yield p


def check_skill(skill: Path, allow: set[str]) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    md = skill / "SKILL.md"
    if not md.exists():
        return [f"{skill.name}: SKILL.md 없음"], []
    text = md.read_text(encoding="utf-8", errors="replace")
    fm = frontmatter(text)
    if fm is None:
        errors.append("F1 머리말 없음")
    else:
        if fm.get("name") != skill.name:
            errors.append(f"F1 name={fm.get('name')!r} ≠ 폴더명 {skill.name!r}")
        desc = fm.get("description", "")
        if not desc:
            errors.append("F1 description 없음")
        elif len(desc) > 200:
            warns.append(f"F2 description {len(desc)}자 > 200")

    for f in text_files(skill):
        rel = f.relative_to(skill).as_posix()
        body = f.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(body.splitlines(), 1):
            if f.suffix == ".md":
                cands = set(LINK_RE.findall(line)) | {m.group(1) for m in PATH_RE.finditer(line)}
                for c in cands:
                    if re.match(r"^[a-z]+://", c) or c.startswith(("mailto:", "/", "~")) or re.match(r"^[A-Za-z]:", c) or "<" in c or "*" in c:
                        continue
                    target = (f.parent / c)
                    alt = skill / c  # 스킬 루트 기준으로 쓴 경로도 허용
                    if not target.exists() and not alt.exists():
                        errors.append(f"L1 {rel}:{i} 없는 경로 {c}")
            for name in RETIRED:
                if name in allow or name == skill.name:
                    continue
                if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", line):
                    errors.append(f"N1 {rel}:{i} 옛 스킬명 {name}")
            for pat in CODEX:
                if pat not in allow and re.search(pat, line):
                    errors.append(f"N1 {rel}:{i} Codex 흔적 /{pat}/")
        if f.suffix == ".py" and "scripts" in f.relative_to(skill).parts[:1]:
            try:
                py_compile.compile(str(f), doraise=True, cfile=str(Path(sys.argv[0]).parent / ".pyc_tmp"))
            except py_compile.PyCompileError as e:
                errors.append(f"S1 {rel} 컴파일 실패: {e.msg.strip().splitlines()[-1]}")
    return errors, warns


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+", type=Path)
    ap.add_argument("--allow", nargs="*", default=[])
    args = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(errors="replace")
    total_err = 0
    for root in args.roots:
        skills = sorted(p for p in root.iterdir() if p.is_dir() and (p / "SKILL.md").exists())
        if not skills:
            print(f"!! {root}: SKILL.md 가 있는 폴더가 없다")
            total_err += 1
            continue
        for skill in skills:
            errors, warns = check_skill(skill, set(args.allow))
            total_err += len(errors)
            mark = "FAIL" if errors else ("WARN" if warns else "OK  ")
            print(f"{mark} {root.name}/{skill.name}")
            for e in errors:
                print(f"     ✗ {e}")
            for w in warns:
                print(f"     △ {w}")
    tmp = Path(sys.argv[0]).parent / ".pyc_tmp"
    tmp.unlink(missing_ok=True)
    print(f"\n오류 {total_err}개")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
