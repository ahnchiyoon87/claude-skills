# -*- coding: utf-8 -*-
"""근태 JSON 생성 — 채우고 base64 로 인코딩해 파일로 낸다.

    python 근태만들기.py <원본json> <출력json> <연> <월> \n        [--공휴일 "15:광복절,17:대체공휴일"] [--연차 7,14] [--오전반차 21] [--오후반차 5]

형식 (사용자가 준 실물 샘플에서 확인 · 프로그램 DLL 의 StartWorkTime/EndWorkTime 과 일치)
    {"<사번>":{"Name":"<이름>","WorkTime":{
        "2026-06-01":{"StartWorkTime":"2026-06-01 09:35","EndWorkTime":"2026-06-01 17:56"}}}}
    · 날짜 키 = "YYYY-MM-DD"
    · 시각 값 = "YYYY-MM-DD HH:MM"  (날짜를 같이 적는다)

규칙
    출근 09:30 고정 · 퇴근 18:00~18:30 랜덤
    주말·공휴일·연차 = 항목 자체를 안 만든다
    오전 반차 = 13:30 출근 · 오후 반차 = 13:30 퇴근
"""
from __future__ import annotations

import base64
import calendar
import datetime as dt
import json
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

요일 = ["월", "화", "수", "목", "금", "토", "일"]

# ★ 공휴일은 **이번에 도는 달 것만** 인자로 받는다.
#   ⚠ 여기에 박아 두면 **다음 달을 돌릴 때마다 사람이 이 파일을 고쳐 줘야 한다.**
#     연차·반차를 인자로 뺀 것과 같은 이유다.
#   ⚠ 안 주면 **멈춘다.** 모르는 채 만들면 쉬는 날에 출근 기록이 생긴다.
공휴일: dict[int, str] = {}

# ★ 연차·반차는 **사용자가 이번에 말한 것만** 인자로 받는다.
#   ⚠ 여기에 박아 두면 다음 달에 **남의 연차가 조용히 다시 들어간다.**
#     실제로 8/7 연차·8/21 오전반차가 박혀 있었고, 같은 달을 다시 돌리면
#     사용자가 말하지 않아도 그대로 들어갔다. 스킬이 금지한 바로 그것이다.
연차: set[int] = set()
오전반차: set[int] = set()
오후반차: set[int] = set()

출근 = "09:30"
반차경계 = "13:30"


def 퇴근(rnd: random.Random) -> str:
    return f"18:{rnd.randint(0, 30):02d}"


def 만든다(연: int, 월: int, seed: int) -> tuple[dict, list]:
    rnd = random.Random(seed)
    표: dict[str, dict[str, str]] = {}
    기록 = []
    for 일 in range(1, calendar.monthrange(연, 월)[1] + 1):
        d = dt.date(연, 월, 일)
        w = 요일[d.weekday()]
        날짜 = d.isoformat()                      # 2026-08-03

        휴 = 공휴일.get(일)
        if d.weekday() >= 5:
            # 공휴일이 주말과 겹치면 **둘 다 적는다.** 「주말」로만 적으면
            # 공휴일 대조 검사가 그 이름을 못 찾아 영원히 실패한다
            기록.append((일, w, "", "", f"주말 · {휴}" if 휴 else "주말")); continue
        if 휴:
            기록.append((일, w, "", "", 휴)); continue
        if 일 in 연차:
            기록.append((일, w, "", "", "연차")); continue

        if 일 in 오전반차:
            s, e, 비고 = 반차경계, 퇴근(rnd), "오전반차"
        elif 일 in 오후반차:
            s, e, 비고 = 출근, 반차경계, "오후반차"
        else:
            s, e, 비고 = 출근, 퇴근(rnd), ""

        표[날짜] = {"StartWorkTime": f"{날짜} {s}", "EndWorkTime": f"{날짜} {e}"}
        기록.append((일, w, s, e, 비고))
    return 표, 기록


def main() -> None:
    # 인자가 모자라면 **트레이스백 대신 사용법**을 낸다.
    # 다음 사람이 「도구가 깨졌나」 하고 헤매지 않게.
    global 연차, 오전반차, 오후반차
    # ⚠ 자리 인자와 옵션 값을 **한 번에** 가른다.
    #   따로 훑으면 `--연차 7` 의 `7` 이 자리 인자로도 세어져 개수가 틀린다.
    자리: list[str] = []
    옵션: dict[str, str] = {}
    잔여 = sys.argv[1:]
    i = 0
    while i < len(잔여):
        if 잔여[i].startswith("--"):
            옵션[잔여[i][2:]] = 잔여[i + 1] if i + 1 < len(잔여) else ""
            i += 2
        else:
            자리.append(잔여[i])
            i += 1

    if len(자리) != 4:
        print(__doc__)
        print("  받은 인자:", sys.argv[1:] or "없음")
        print("  예)  python 근태만들기.py 8월011.json 8월011.json 2026 8 --연차 7 --오전반차 21")
        sys.exit(2)

    def 날짜들(키: str) -> set[int]:
        v = 옵션.get(키, "").strip()
        if not v:
            return set()
        try:
            return {int(x) for x in v.replace(" ", "").split(",") if x}
        except ValueError:
            print(f"  --{키} 는 숫자를 쉼표로 — 받은 것 {v!r}")
            sys.exit(2)

    def 휴일들(키: str) -> dict[int, str]:
        """`--공휴일 "15:광복절,17:대체공휴일"` → {15: "광복절", 17: "대체공휴일"}"""
        v = 옵션.get(키, "").strip()
        if v == "없음":
            return {}
        out: dict[int, str] = {}
        # ⚠ 공백을 통째로 털면 「광복절 대체공휴일」이 붙어 버린다. **날짜에서만 턴다**
        for 조각 in (x.strip() for x in v.split(",") if x.strip()):
            if ":" not in 조각:
                print(f"  --{키} 는 `일:이름` 을 쉼표로 — 받은 것 {조각!r}")
                sys.exit(2)
            일, 이름 = 조각.split(":", 1)
            try:
                out[int(일.strip())] = 이름.strip()
            except ValueError:
                print(f"  --{키} 의 날은 숫자여야 한다 — 받은 것 {일!r}")
                sys.exit(2)
        return out

    global 공휴일
    공휴일 = 휴일들("공휴일")
    연차 = 날짜들("연차")
    오전반차 = 날짜들("오전반차")
    오후반차 = 날짜들("오후반차")

    원본, 출력 = 자리[0], 자리[1]
    try:
        연, 월 = int(자리[2]), int(자리[3])
    except ValueError:
        print(f"  연·월은 숫자여야 한다 — 받은 것 {자리[2]!r} {자리[3]!r}")
        sys.exit(2)
    if not 1 <= 월 <= 12:
        print(f"  월이 1~12 가 아니다 — {월}")
        sys.exit(2)

    p원본 = Path(원본)
    if not p원본.exists():
        print(f"  원본이 없다 — {원본}")
        sys.exit(2)

    # ★ 공휴일을 모르는 달은 **찍어서 만들지 않는다.** 멈추고 알린다.
    #   그 달에 공휴일이 정말 없으면 `--공휴일 없음` 으로 그렇다고 말해 준다.
    if "공휴일" not in 옵션:
        print(f"  ⚠ {연}년 {월}월 공휴일을 안 받았다.")
        print('     예)  --공휴일 "15:광복절,17:광복절 대체공휴일"')
        print("     그 달에 공휴일이 없으면  --공휴일 없음")
        print("     모른 채 만들면 쉬는 날에 출근 기록이 생긴다.")
        sys.exit(2)

    본 = json.loads(base64.b64decode(p원본.read_text(encoding="utf-8").strip()).decode("utf-8"))
    사번 = next(iter(본))                       # 껍데기를 물려받는다
    표, 기록 = 만든다(연, 월, seed=연 * 100 + 월)
    본[사번]["WorkTime"] = 표

    평문 = json.dumps(본, ensure_ascii=False, separators=(",", ":"))
    Path(출력).write_text(base64.b64encode(평문.encode("utf-8")).decode("ascii"), encoding="utf-8")

    print("=" * 58)
    print(f"  {연}년 {월}월 · {본[사번]['Name']} ({사번})")
    print("=" * 58)
    for 일, w, s, e, 비고 in 기록:
        print(f"  {일:2d} {w}   {s + ' ~ ' + e if s else '':17}{비고}")
    print("-" * 58)
    print(f"  기록된 근무일 {len(표)}일   출력 {출력}")
    print(f"  공휴일 {공휴일 or '없음'}")
    print(f"  연차 {sorted(연차) or '없음'} · 오전반차 {sorted(오전반차) or '없음'}"
          f" · 오후반차 {sorted(오후반차) or '없음'}  ← 인자로 받은 것만")
    print("=" * 58)
    print()
    되읽음 = json.loads(base64.b64decode(Path(출력).read_text(encoding="utf-8")).decode("utf-8"))
    print("[왕복 검증] 디코드 결과가 같은가:", 되읽음 == 본)
    print()
    print("[첫 항목 — 형식 확인]")
    첫키 = next(iter(표))
    print("  ", json.dumps({첫키: 표[첫키]}, ensure_ascii=False))
    print()
    print("[base64]")
    print(Path(출력).read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
