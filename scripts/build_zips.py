"""스킬별 claude.ai 업로드용 zip 을 dist/ 에 만든다.

claude.ai 규격(https://support.claude.com/en/articles/12512198):
- zip 최상위에 스킬 폴더 하나, 폴더명 = name
- 머리말은 name·description·license·compatibility·metadata·allowed-tools 만 허용
  (다른 키가 있으면 업로드가 거부되므로 zip 안의 SKILL.md 에서만 뺀다. 원본은 건드리지 않는다)
- name ≤ 64자. description 길이 제한은 문서마다 다르다(200 / 1536) → 200 초과는 경고만 한다.

사용: python scripts/build_zips.py [스킬이름 ...]
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
DIST = ROOT / "dist"
ALLOWED = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
SKIP_PARTS = {"__pycache__", ".pytest_cache"}


def split_frontmatter(text: str) -> tuple[list[str], str]:
    text = text.lstrip("﻿")
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        raise ValueError("머리말(--- ... ---)이 없다")
    return m.group(1).splitlines(), text[m.end():]


def clean_frontmatter(lines: list[str]) -> tuple[list[str], list[str], dict[str, str]]:
    """허용 키만 남긴다. 들여쓴 줄(metadata 하위 등)은 직전 최상위 키를 따른다."""
    kept, dropped, values = [], [], {}
    keep_current = False
    for line in lines:
        top = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if top:
            key = top.group(1)
            keep_current = key in ALLOWED
            if keep_current:
                values[key] = top.group(2).strip().strip('"').strip("'")
            else:
                dropped.append(key)
        if keep_current:
            kept.append(line)
    return kept, dropped, values


def build(skill_dir: Path) -> list[str]:
    name = skill_dir.name
    fm, body = split_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    kept, dropped, values = clean_frontmatter(fm)
    problems = []
    if values.get("name") != name:
        raise ValueError(f"{name}: 머리말 name({values.get('name')!r})이 폴더명과 다르다")
    if len(name) > 64:
        raise ValueError(f"{name}: name 이 64자를 넘는다")
    if not values.get("description"):
        raise ValueError(f"{name}: description 이 없다")
    if len(values["description"]) > 200:
        problems.append(f"description {len(values['description'])}자(>200, 업로드 거부 가능)")
    if dropped:
        problems.append("zip 에서 뺀 머리말: " + ", ".join(dropped))

    DIST.mkdir(exist_ok=True)
    out = DIST / f"{name}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(skill_dir.rglob("*")):
            if path.is_dir() or SKIP_PARTS & set(path.parts) or path.suffix == ".pyc":
                continue
            arc = f"{name}/{path.relative_to(skill_dir).as_posix()}"
            if path.name == "SKILL.md" and path.parent == skill_dir:
                zf.writestr(arc, "---\n" + "\n".join(kept) + "\n---\n" + body)
            else:
                zf.write(path, arc)
    return problems


def main(argv: list[str]) -> int:
    targets = [SKILLS / n for n in argv] if argv else sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").exists())
    failed = 0
    for d in targets:
        try:
            problems = build(d)
            print(f"OK   {d.name}.zip" + ("" if not problems else "  ⚠ " + " / ".join(problems)))
        except Exception as e:  # 스킬 하나가 깨져도 나머지는 만들고, 종료 코드로 알린다
            failed += 1
            print(f"FAIL {d.name}: {e}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
