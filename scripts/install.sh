#!/usr/bin/env bash
# 로컬(Linux/macOS) 설치: ~/.claude/skills/<이름> → 이 레포 skills/<이름> 심볼릭 링크.
# 같은 이름의 실제 폴더는 지우지 않고 ~/.claude/skills-backup/<시각>/ 으로 옮긴다.
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
dst="$HOME/.claude/skills"
backup="$HOME/.claude/skills-backup/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$dst"

for skill in "$repo"/skills/*/; do
  name="$(basename "$skill")"; skill="${skill%/}"; link="$dst/$name"
  if [ -L "$link" ]; then
    if [ "$(readlink -f "$link")" = "$(readlink -f "$skill")" ]; then echo "그대로  $name"
    else echo "건너뜀  $name — 다른 곳을 가리키는 링크($(readlink "$link"))"; fi
    continue
  fi
  if [ -e "$link" ]; then mkdir -p "$backup"; mv "$link" "$backup/"; echo "보관    $name → $backup"; fi
  ln -s "$skill" "$link"; echo "연결    $name"
done

import="@$repo/CLAUDE.md"
touch "$HOME/.claude/CLAUDE.md"
if ! grep -qxF "$import" "$HOME/.claude/CLAUDE.md"; then
  echo "$import" >> "$HOME/.claude/CLAUDE.md"; echo "추가    ~/.claude/CLAUDE.md 에 $import"
fi
