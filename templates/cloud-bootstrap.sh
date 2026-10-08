#!/usr/bin/env bash
# 클라우드 세션(Claude Code on the web)에서만 공용 헌법·스킬을 받아 온다. 로컬에서는 바로 끝난다.
# 원본: claude-skills/templates/cloud-bootstrap.sh — 각 프로젝트 레포 .claude/hooks/ 에 복사해 쓴다.
# 클라우드는 ~/.claude 를 가져가지 않으므로(공식 문서 cloud-environments) 여기서 채운다.
#  - 스킬: ~/.claude/skills/<이름> 링크 + reloadSkills 로 같은 세션에서 바로 쓴다
#  - 헌법: CLAUDE.md 본문을 additionalContext 로 넣는다
# 실패하면 조용히 넘어가지 않고 그 사실을 컨텍스트에 남겨 Claude 가 사용자에게 알리게 한다.
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0

REPO="${CLAUDE_SKILLS_REPO:-https://github.com/ahnchiyoon87/claude-skills.git}"
DEST="$HOME/.claude-skills"
err=""
if [ -d "$DEST/.git" ]; then
  git -C "$DEST" pull -q --ff-only 2>/tmp/claude-skills.err || err="pull 실패: $(cat /tmp/claude-skills.err)"
else
  git clone -q --depth 1 "$REPO" "$DEST" 2>/tmp/claude-skills.err || err="clone 실패($REPO): $(cat /tmp/claude-skills.err)"
fi

if [ -z "$err" ]; then
  mkdir -p "$HOME/.claude/skills"
  for skill in "$DEST"/skills/*/; do
    ln -sfn "${skill%/}" "$HOME/.claude/skills/$(basename "$skill")"
  done
fi

[ -z "$err" ] && [ ! -f "$DEST/CLAUDE.md" ] && err="$DEST/CLAUDE.md 가 없다"
PY=""
for c in python3 python; do "$c" -c 'import sys' >/dev/null 2>&1 && { PY="$c"; break; }; done
[ -n "$PY" ] || { echo "cloud-bootstrap: python 이 없다" >&2; exit 1; }
"$PY" - "$DEST/CLAUDE.md" "$err" <<'PY'
import json, pathlib, sys
sys.stdout.reconfigure(encoding="utf-8")
path, err = pathlib.Path(sys.argv[1]), sys.argv[2]
if err:
    ctx = "[클라우드 부트스트랩 실패] 공용 헌법·스킬을 받지 못했다. 사용자에게 먼저 알린다.\n" + err
else:
    ctx = "[공용 헌법 — claude-skills/CLAUDE.md]\n" + path.read_text(encoding="utf-8")
print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                         "additionalContext": ctx,
                                         "reloadSkills": not err}}, ensure_ascii=False))
PY
