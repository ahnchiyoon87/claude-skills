# -*- coding: utf-8 -*-
"""원본 인계 묶음과 사본(요약 인계 문서)을 **세서 대조한다.**

    python 인계대조.py --원본 <폴더|파일> [--원본 <폴더|파일> ...] --사본 <파일>

    --원본  폴더면 그 안의 *.md 전부(이름순), 파일이면 그 파일. 여러 번 줄 수 있다.
    --사본  요약해 만든 인계 문서 하나.

종료 코드: 0 = 규범·범위 경계 소실 0 / 1 = 소실 있음 / 2 = 입력 오류.
외부 모듈·프로젝트 탐지에 기대지 않는다. 경로는 인자로만 받는다.

「빠뜨리지 말자」는 매번 실패한다. **세야 잡힌다.**
실제로 원본 규범 126개 중 사본에 1개, 범위 경계 16개 중 0개만 넘어온 적이 있다.
산출물 목록은 옮겨지는데 **「하지 마라」와 「여긴 우리 담당 아니다」가 통째로 증발한다.**

⚠ 이 도구가 세는 것은 **양**이다. 양이 맞아도 내용이 맞는지는 사람이 읽어야 한다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

W = 72

# 무엇을 세나 — 이름, 정규식, 무엇을 뜻하나
항목 = [
    ("헤딩",     re.compile(r"^#{1,6} ", re.M),                       "절의 수"),
    ("표행",     re.compile(r"^\|", re.M),                            "표로 적힌 사실"),
    ("번호항목", re.compile(r"^\s*(?:\|\s*)?\*{0,2}\d+[.)\s|]", re.M), "번호 매긴 목록"),
    ("규범",     re.compile(r"금지|하지 마|하지 않는다|안 된다|되살리지|위반|\d+조"),
                 "★ 하지 마라 — 제일 잘 사라진다"),
    ("범위경계", re.compile(r"다루지 않|범위 밖|우리 담당이 아|다른 담당|손대지 않"),
                 "★ 여긴 우리 몫이 아니다 — 제일 잘 사라진다"),
    ("수치",     re.compile(r"\d[\d,.]*\s*(?:개|행|줄|건|초|분|시간|명|주|일|%|MB|GB)"),
                 "잰 값"),
]

# 통과선 — 이 아래로 내려가면 멈춘다
통과선 = {"규범": 1.0, "범위경계": 1.0}      # 소실 0 이어야 한다


def 센다(글: str) -> dict[str, int]:
    return {이름: len(pat.findall(글)) for 이름, pat, _ in 항목}


def 글모으기(경로들: list[Path]) -> str:
    buf = []
    for f in 경로들:
        try:
            buf.append(f.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            print(f"  ⚠ 못 읽음 {f} — {e}")
    return "\n".join(buf)


def 인자읽기(인자: list[str]) -> tuple[list[Path], Path | None, list[str]]:
    원본지정: list[Path] = []
    사본지정: Path | None = None
    오류: list[str] = []
    i = 0
    while i < len(인자):
        a = 인자[i]
        if a in ("--원본", "--사본"):
            if i + 1 >= len(인자) or 인자[i + 1].startswith("--"):
                오류.append(f"{a} 뒤에 경로가 없다")
                i += 1
                continue
            if a == "--원본":
                원본지정.append(Path(인자[i + 1]))
            else:
                사본지정 = Path(인자[i + 1])
            i += 2
            continue
        if a in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        오류.append(f"알 수 없는 인자: {a}")
        i += 1
    return 원본지정, 사본지정, 오류


def main() -> None:
    원본지정, 사본, 오류 = 인자읽기(sys.argv[1:])
    if not 원본지정:
        오류.append("--원본 이 없다")
    if 사본 is None:
        오류.append("--사본 이 없다")
    if 오류:
        for e in 오류:
            print(f"  ❌ {e}")
        print(__doc__)
        sys.exit(2)

    원본들: list[Path] = []
    for p in 원본지정:
        if p.is_dir():
            찾음 = sorted(f for f in p.glob("*.md") if f.is_file())
            if not 찾음:
                print(f"  ❌ 원본 폴더에 .md 가 없다 — {p}")
                sys.exit(2)
            원본들 += 찾음
        elif p.is_file():
            원본들.append(p)
        else:
            print(f"  ❌ 원본 경로가 없다 — {p}")
            sys.exit(2)

    if not 사본.is_file():
        print(f"  ❌ 사본을 못 찾았다 — {사본}")
        sys.exit(2)

    # 사본이 원본 목록에 섞이면 자기 자신과 비교하게 된다
    원본들 = [f for f in dict.fromkeys(원본들) if f.resolve() != 사본.resolve()]
    if not 원본들:
        print("  ❌ 사본을 빼고 나니 원본 파일이 하나도 없다. 경로를 확인하라.")
        sys.exit(2)

    원 = 센다(글모으기(원본들))
    사 = 센다(사본.read_text(encoding="utf-8", errors="replace"))

    print("=" * W)
    print("  인계 대조 — 원본 묶음 vs 사본")
    print("=" * W)
    print(f"  원본  {len(원본들)}개 파일")
    for f in 원본들:
        print(f"          {f.name}")
    print(f"  사본  {사본.name}")
    print()
    print(f"  {'무엇':<10}{'원본':>7}{'사본':>7}{'비율':>8}   {'':<4}뜻")
    print("  " + "─" * (W - 4))

    막힘 = []
    for 이름, _, 뜻 in 항목:
        o, s = 원[이름], 사[이름]
        비율 = (s / o) if o else 1.0
        선 = 통과선.get(이름)
        표시 = "  "
        if 선 is not None and 비율 < 선:
            표시 = "❌"
            막힘.append((이름, o, s))
        print(f"  {이름:<10}{o:>7}{s:>7}{비율*100:>7.1f}% {표시}  {뜻}")

    print()
    print("=" * W)
    if 막힘:
        for 이름, o, s in 막힘:
            print(f"  ❌ **{이름}** — 원본 {o} 중 사본에 {s}. **{o - s}개가 사라졌다**")
        print()
        print("  옮기거나, 왜 뺐는지 사본에 적어라. **둘 다 안 하면 그것이 누락이다.**")
        print("  양이 맞아도 끝이 아니다 — **원본을 읽고 내용이 살아 있는지 눈으로 본다.**")
        print("=" * W)
        sys.exit(1)

    print("  ✅ 규범·범위 경계 소실 0")
    print("  ⚠ **양만 본 것이다.** 내용이 맞는지는 원본을 읽어서 판정한다.")
    print("=" * W)


if __name__ == "__main__":
    main()
