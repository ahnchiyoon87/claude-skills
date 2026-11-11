"""회의록 Google Docs에서 그날 머리줄 바로 아래에 요약을 끼워 넣는 batchUpdate 요청을 만든다.

사용:
  python -X utf8 minutes_insert.py <read_doc 결과 JSON> <날짜 YYYY-MM-DD> <요약.json> <출력.json> [--header "머리줄 전체"]
요약.json: {"sections":[{"time":"09:49~12:42","title":"…","bullets":["…"]}]}
- 머리줄(「2026-11-10(화) 회의록 …」)이 문서에 없으면 --header로 받은 머리줄을 맨 위에 새로 만든다(빈 줄 하나로 다음 날짜와 나눈다).
- 머리줄 아래가 이미 비어 있지 않으면(그날 내용이 있으면) 멈춘다. 같은 날을 두 번 쓰지 않는다.
출력: {"revisionId": …, "requests": […]} — update_doc에 writeControl.requiredRevisionId와 함께 보낸다.
"""
import json, re, sys, argparse
from pathlib import Path


def u16(s):
    return len(s.encode("utf-16-le")) // 2


def ptext(el):
    return "".join(e["textRun"]["content"] for e in el["paragraph"]["elements"] if "textRun" in e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc"); ap.add_argument("date"); ap.add_argument("summary"); ap.add_argument("out")
    ap.add_argument("--header")
    a = ap.parse_args()
    d = json.loads(Path(a.doc).read_text(encoding="utf-8"))["content"]
    body = d["tabs"][0]["documentTab"]["body"]["content"]
    paras = [el for el in body if "paragraph" in el]
    pat = re.compile(re.escape(a.date).replace("\\-", "[-–]") + r"\s*\(")
    hits = [el for el in paras if pat.match(ptext(el).strip())]
    req = []
    if hits:
        h = hits[0]
        i = paras.index(h)
        nxt = ptext(paras[i + 1]).strip() if i + 1 < len(paras) else ""
        if nxt:
            sys.exit(f"{a.date} 머리줄 아래에 이미 내용이 있음: {nxt[:40]!r} — 같은 날을 두 번 쓰지 않는다")
        at = h["endIndex"]
    else:
        if not a.header:
            sys.exit(f"{a.date} 머리줄이 문서에 없음 — --header로 머리줄을 준다")
        req.append({"insertText": {"location": {"index": 1}, "text": a.header + "\n\n"}})
        req.append({"updateTextStyle": {"range": {"startIndex": 1, "endIndex": 1 + u16(a.header)},
                                        "textStyle": {"bold": False}, "fields": "bold"}})
        m = re.search(r"https?://\S+", a.header)
        if m:
            s = 1 + u16(a.header[:m.start()])
            req.append({"updateTextStyle": {"range": {"startIndex": s, "endIndex": s + u16(m.group(0))},
                                            "textStyle": {"link": {"url": m.group(0)}}, "fields": "link"}})
        at = 1 + u16(a.header) + 1

    sm = json.loads(Path(a.summary).read_text(encoding="utf-8"))
    lines = []                                    # (글, 종류)
    for s in sm["sections"]:
        lines += [(s["time"], "time"), (s["title"], "title")] + [(b, "item") for b in s["bullets"]]
    text = "".join(t + "\n" for t, _ in lines)
    req.append({"insertText": {"location": {"index": at}, "text": text}})
    end = at + u16(text)
    req.append({"updateTextStyle": {"range": {"startIndex": at, "endIndex": end}, "textStyle": {"bold": False}, "fields": "bold"}})
    p, run = at, None
    for t, k in lines:
        n = u16(t)
        if k == "title":
            req.append({"updateTextStyle": {"range": {"startIndex": p, "endIndex": p + n}, "textStyle": {"bold": True}, "fields": "bold"}})
        if k == "item":
            run = run or p
        elif run is not None:
            req.append({"createParagraphBullets": {"range": {"startIndex": run, "endIndex": p}, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
            run = None
        p += n + 1
    if run is not None:
        req.append({"createParagraphBullets": {"range": {"startIndex": run, "endIndex": p}, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
    Path(a.out).write_text(json.dumps({"revisionId": d["revisionId"], "requests": req}, ensure_ascii=False), encoding="utf-8")
    print(a.out, "insert at", at, "requests", len(req), "chars", len(text))


if __name__ == "__main__":
    main()
