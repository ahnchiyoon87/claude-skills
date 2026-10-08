# -*- coding: utf-8 -*-
"""대화 기록(JSONL)에서 **사용자가 실제로 한 말만** 순서대로 뽑는다.

    python 사용자발화추출.py <대화기록.jsonl> [--출력 <파일.md>] [--이후 2026-09-29T06:00]

왜: 인계는 "사용자와 나눈 대화를 옮기는 일"이다. 기억이나 요약으로 쓰면 빠지고, 바뀌고, 옛 해석이 남는다.
이 도구로 발화 목록을 먼저 만들고, 발화마다 인계 문서의 어디에 반영됐는지 대응표를 채운다(SKILL.md 4절).

지원: Claude Code 기록(`~/.claude/projects/<프로젝트>/<세션>.jsonl`).
  - 일반 사용자 메시지(type=user, 도구 결과가 아닌 것)
  - 작업 중에 보낸 메시지(type=attachment, queued_command, origin=human. 옛 형식은 도구 결과 안의
    "The user sent a new message while you were working:" 블록)
  - 선택지 질문의 답("User has answered your questions" / "The user answered:"), 슬래시 명령 인자("[명령 /goal] …")
그 밖의 기록 형식은 role=="user"이고 글자 내용이 있는 항목을 사용자 발화로 본다. 형식이 다르면 결과를 눈으로 확인한다.
뺀다: 시스템 알림(<system-reminder>, <task-notification>, 로컬 명령 안내), 자동 알림(origin≠human), 서브에이전트 대화(isSidechain),
맥락 압축 요약, 빈 메시지, 깨진 줄.
⚠ 이 도구는 발화를 모을 뿐이다. 각 발화의 뜻과 반영 여부는 사람이 읽고 판단한다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

작업중표지 = "The user sent a new message while you were working:"
요약표지 = "This session is being continued from a previous conversation"
선택답표지 = ("User has answered your questions", "The user answered:")
작업중끝 = "This is how Claude Code surfaces"
잡음 = re.compile(
    r"<system-reminder>.*?</system-reminder>|<task-notification>.*?</task-notification>"
    r"|<local-command-caveat>.*?</local-command-caveat>|<command-(?:name|message|args)>.*?</command-(?:name|message|args)>"
    r"|<local-command-stdout>.*?</local-command-stdout>|<ide_selection>.*?</ide_selection>|<ide_opened_file>.*?</ide_opened_file>",
    re.S,
)
중단표시 = re.compile(r"^\[Request interrupted by user[^\]]*\]$", re.M)


명령 = re.compile(r"<command-name>(.*?)</command-name>.*?<command-args>(.*?)</command-args>", re.S)


def 정리(글: str) -> str:
    # 슬래시 명령(예: /goal …)의 인자는 사용자가 쓴 지시이므로 남긴다.
    명령들 = [f"[명령 {n.strip()}] {a.strip()}" for n, a in 명령.findall(글) if a.strip()]
    글 = 잡음.sub("", 글)
    if 명령들:
        글 = "\n".join(명령들 + ([글] if 글.strip() else []))
    글 = 중단표시.sub("", 글)
    return 글.strip()


def 글꺼내기(content) -> tuple[list[str], list[str]]:
    """(사용자 글, 도구 결과 글)"""
    사용자, 도구 = [], []
    if isinstance(content, str):
        사용자.append(content)
    elif isinstance(content, list):
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text":
                사용자.append(b.get("text", ""))
            elif b.get("type") == "tool_result":
                c = b.get("content")
                if isinstance(c, str):
                    도구.append(c)
                elif isinstance(c, list):
                    도구 += [x.get("text", "") for x in c if isinstance(x, dict)]
    return 사용자, 도구


def 작업중메시지(글: str) -> list[str]:
    out = []
    i = 0
    while True:
        i = 글.find(작업중표지, i)
        if i < 0:
            return out
        j = 글.find(작업중끝, i)
        조각 = 글[i + len(작업중표지): j if j > 0 else None]
        out.append(조각.strip())
        i = i + len(작업중표지)


def main() -> None:
    인자 = sys.argv[1:]
    if not 인자:
        print(__doc__)
        sys.exit(2)
    기록 = Path(인자[0])
    출력 = None
    이후 = ""
    if "--출력" in 인자:
        출력 = Path(인자[인자.index("--출력") + 1])
    if "--이후" in 인자:
        이후 = 인자[인자.index("--이후") + 1]

    발화: list[tuple[str, str, str]] = []  # (시각, 종류, 글)
    본것 = set()
    for 줄 in 기록.open(encoding="utf-8", errors="replace"):
        try:
            r = json.loads(줄)
        except json.JSONDecodeError:
            continue
        if r.get("isSidechain"):
            continue
        시각 = r.get("timestamp", "")
        if 이후 and 시각 and 시각 < 이후:
            continue
        # 작업 중에 보낸 메시지: attachment(queued_command, origin=human)로 저장된다
        a = r.get("attachment")
        if r.get("type") == "attachment" and isinstance(a, dict):
            if a.get("type") == "queued_command" and (a.get("origin") or {}).get("kind") == "human":
                사용자, _ = 글꺼내기(a.get("prompt"))
                for 글 in 사용자:
                    t = 정리(글)
                    if t and t not in 본것:
                        본것.add(t)
                        발화.append((a.get("timestamp", 시각), "작업 중", t))
            continue
        m = r.get("message") if isinstance(r.get("message"), dict) else r
        if m.get("role") != "user" and r.get("type") != "user":
            continue
        if r.get("isMeta"):
            continue
        사용자, 도구 = 글꺼내기(m.get("content"))
        for 글 in 사용자:
            t = 정리(글)
            if t.startswith(요약표지):   # 맥락 압축 요약은 사용자 발화가 아니다(안의 발화 목록은 따로 참고)
                continue
            if t and t not in 본것:
                본것.add(t)
                발화.append((시각, "메시지", t))
        for 글 in 도구:
            if 글.startswith(선택답표지):   # 선택지 질문에 사용자가 고른 답
                t = 정리(글)
                if t and t not in 본것:
                    본것.add(t)
                    발화.append((시각, "선택 답", t))
            for t in 작업중메시지(글):
                t = 정리(t)
                if t and t not in 본것:
                    본것.add(t)
                    발화.append((시각, "작업 중", t))

    줄들 = [f"# 사용자 발화 {len(발화)}개 — {기록.name}", "",
           "| # | 시각(UTC) | 종류 | 발화 | 인계 반영 위치 |", "|---|---|---|---|---|"]
    for n, (시각, 종류, 글) in enumerate(발화, 1):
        한줄 = 글.replace("\n", " / ").replace("|", "\\|")
        줄들.append(f"| {n} | {시각[:19]} | {종류} | {한줄} |  |")
    결과 = "\n".join(줄들) + "\n"
    if 출력:
        출력.write_text(결과, encoding="utf-8")
        print(f"사용자 발화 {len(발화)}개 → {출력}")
    else:
        print(결과)


if __name__ == "__main__":
    main()
