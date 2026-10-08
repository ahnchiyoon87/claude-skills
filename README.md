# claude-skills

어느 프로젝트에서나 쓰는 **공용 헌법(CLAUDE.md)과 공용 스킬**의 원본. 고칠 곳은 여기 한 군데다.

## 무엇이 어디에 있나

| 층 | 내용 | 위치 |
|---|---|---|
| 헌법 | 모든 작업에 항상 켜지는 짧은 원칙 | 이 레포 `CLAUDE.md` |
| 공용 스킬 | 프로젝트와 무관하게 절차가 같은 일(인계·보고·디버깅·E2E 등) | 이 레포 `skills/<이름>/SKILL.md` |
| 도메인 스킬 | 그 레포 파일을 알아야 도는 절차 | 각 레포 `.claude/skills/` |
| 프로젝트 사실 | 경로·명령·포트·배속 등 | 각 레포 `CLAUDE.md` |

스킬 폴더는 `skills/<이름>/SKILL.md` 한 단계만 인식된다. 하위 분류 폴더를 만들지 않는다.

## 설치

### 로컬 Windows (데스크톱 앱 · VS Code 확장 · CLI 공통)

```powershell
powershell -ExecutionPolicy Bypass -File D:\work\claude-skills\scripts\install.ps1
```

- `~/.claude/skills/<이름>` 을 이 레포 `skills/<이름>` 에 **스킬마다 Junction** 으로 연결한다.
  폴더 통째로 연결하지 않는다 — `~/.claude/skills/synced/`(데스크톱 앱이 claude.ai 스킬을 받아 두는 곳)와
  npm 이 관리하는 `agent-browser` 가 같은 폴더에 있기 때문이다.
- 같은 이름의 실제 폴더가 있으면 지우지 않고 `~/.claude/skills-backup/<시각>/` 으로 옮긴다.
- `~/.claude/CLAUDE.md` 에 `@D:/work/claude-skills/CLAUDE.md` 한 줄을 추가해 헌법을 불러온다.
- 스킬을 새로 추가했으면 다시 실행한다. 기존 스킬 수정은 연결이라 바로 반영된다.

### 로컬 Linux / macOS

```bash
bash scripts/install.sh
```

### 클라우드 세션 (claude.ai/code)

클라우드는 레포만 clone 하고 `~/.claude` 를 가져가지 않는다. 프로젝트 레포에서 끌어온다.

1. `templates/cloud-bootstrap.sh` 를 프로젝트 레포 `.claude/hooks/cloud-bootstrap.sh` 로 복사한다.
2. 프로젝트 `.claude/settings.json` 에 SessionStart 훅을 등록한다(hyd-iot-edu 참고).
3. `CLAUDE_CODE_REMOTE=true` 일 때만 이 레포를 clone 해 스킬을 링크하고(`reloadSkills`),
   헌법 본문을 세션 컨텍스트로 넣는다. 로컬에서는 바로 끝난다.
4. 이 레포 주소는 환경변수 `CLAUDE_SKILLS_REPO` 로 바꿀 수 있다.

clone 에 실패하면 조용히 넘어가지 않고 "부트스트랩 실패"를 컨텍스트에 남긴다.

### claude.ai 채팅용 zip

```bash
python scripts/build_zips.py          # 전부
python scripts/build_zips.py handoff  # 하나만
```

`dist/<이름>.zip` 이 생긴다. 업로드는 claude.ai 설정 → Skills 에서 직접 한다(자동화 없음).
claude.ai 가 받지 않는 머리말 키는 zip 안에서만 빠지고, 설명 200자 초과는 경고한다.

## 스킬 추가·수정 규칙

- 머리말: `name`(= 폴더명, 소문자·숫자·하이픈) + `description`(하는 일 + 실제 요청 표현 + 인접 스킬과의 경계).
- 프로젝트 고유 경로·포트·이름을 스킬 본문에 박지 않는다. 그 값은 각 프로젝트 `CLAUDE.md` 에 둔다.
- 같은 일을 하는 스킬을 두 벌 만들지 않는다. 스타일·대상이 다르면 프로젝트 쪽 참조 파일로 나눈다.
