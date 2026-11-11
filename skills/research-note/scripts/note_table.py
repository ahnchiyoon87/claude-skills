"""연구노트 한 날짜를 Google Docs 맨 위에 「기존 표와 같은 모양」으로 넣는 batchUpdate 요청을 만든다.

표 모양(칸 수 · 합친 칸 · 칸 너비 · 줄 높이)은 그 문서를 docx로 내보낸 파일의 첫 표에서 읽는다.
글꼴 · 크기 · 테두리 · 들여쓰기는 2026 연구노트 양식(Arimo, 파란 실선 1.375pt)을 따른다.
서명 칸은 비워 둔다(서명은 본인이 넣는다).

사용:
  python -X utf8 note_table.py <문서.docx> <작성자> <초안.json> <출력 폴더> [--per 4]
초안.json: [{"date":"2026-08-31","weekday":"월","sections":{"목표","수행내용"[],"세부기록","실험측정","문제해결","산출물"[],"참고근거"[],"익일계획"}}]
출력: 날짜 순서(오래된 것 먼저)로 묶은 batch_NN.json — 차례대로 update_doc에 보내면 최신 날짜가 맨 위에 온다.
"""
import json, re, sys, zipfile, argparse
from pathlib import Path

HEAD = [("연구제목 : ", "마이크로서비스 기반의 스마트공장운영시스템 개발"),
        ("연구목적 : ", "중소기업용 마이크로 서비스 아키텍처 기반의 제조 어플리케이션 및 기업 맞춤형 패키지 지원 기술 개발"),
        ("과제번호 : ", "RS-2022-00141485")]
BLUE = {"color": {"color": {"rgbColor": {"blue": 1}}}, "dashStyle": "SOLID", "width": {"magnitude": 1.375, "unit": "PT"}}
FONT = {"fontFamily": "Arimo"}
SECTIONS = [("1. 금일 연구 목표", "목표"), ("2. 수행 내용", "수행내용"), ("3. 세부 기록", "세부기록"),
            ("4. 실험/측정 결과", "실험측정"), ("5. 문제점 및 해결", "문제해결"), ("6. 산출물", "산출물"),
            ("7. 참고 및 근거", "참고근거"), ("8. 익일 계획", "익일계획")]


def u16(s):
    return len(s.encode("utf-16-le")) // 2


def read_form(docx):
    """docx 첫 표: 칸 너비(pt), 줄마다 (높이pt, [(시작칸, 칸수, 글자)])."""
    x = zipfile.ZipFile(docx).read("word/document.xml").decode("utf-8")
    t = x[x.find("<w:tbl>"):x.find("</w:tbl>")]
    grid = [float(w) / 20 for w in re.findall(r'<w:gridCol w:w="([\d.]+)"', t)]
    rows = []
    for r in re.findall(r"<w:tr[ >].*?</w:tr>", t, re.S):
        h = re.search(r'<w:trHeight w:val="(\d+)"', r)
        col, cells = 0, []
        for c in re.findall(r"<w:tc>.*?</w:tc>", r, re.S):
            span = int(re.search(r'w:gridSpan w:val="(\d+)"', c).group(1)) if "gridSpan" in c else 1
            cells.append((col, span, re.sub(r"<[^>]+>", "", c)))
            col += span
        rows.append((float(h.group(1)) / 20 if h else 14, cells))
    ncol = sum(s for _, s, _ in rows[0][1])
    if len(rows) != 8 or any(sum(s for _, s, _ in cs) != ncol for _, cs in rows):
        sys.exit(f"{docx}: 첫 표가 8줄 · 같은 칸 수가 아님 — 양식이 바뀌었는지 확인")
    # docx의 gridCol은 두 벌로 나올 수 있다(앞 ncol개가 실제 너비)
    return grid[:ncol], rows


def build(form, author, e):
    widths, rows = form
    ncol = len(widths)
    T = 2                                   # 위치 1(맨 위 빈 줄)에 넣으면 표는 2에서 시작한다
    para = lambda r, c: T + 3 + r * (1 + 2 * ncol) + 2 * c   # 새 표 (r,c) 칸 문단 위치

    labels = [c[2] for c in rows[5][1]]     # 작성자 | 작성일자 | 서명 | (확인자서명 …)
    y, m, d = e["date"].split("-")
    texts = {}                               # (r,c) → [(글, 서식키)]
    for r in range(3):
        texts[(r, 0)] = [(HEAD[r][0], "h14"), (HEAD[r][1], "h12")]
    r3 = rows[3][1]
    texts[(3, r3[0][0])] = [("주관연구개발기관 책임자 : ", "h14"), ("황순관 [(주)무른모]", "h12")]
    texts[(3, r3[1][0])] = [("공동연구개발기관 책임자 :", "h14"), (" 장진영", "h12")]
    for (c0, _, _), lab in zip(rows[5][1], labels):
        texts[(5, c0)] = [(lab, "h14")]
    r6 = rows[6][1]
    texts[(6, r6[0][0])] = [(author, "s10")]
    texts[(6, r6[1][0])] = [(f"{y}. {m}. {d} ({e['weekday']})", "s10")]

    s = e["sections"]
    body, lists = [(f"{e['date']} ({e['weekday']}) 연구노트", "title")], []
    for head, key in SECTIONS:
        body.append((head, "sec"))
        v = s[key]
        if isinstance(v, list):
            lists.append((len(body), len(body) + len(v)))
            body += [(x.lstrip("- ").strip(), "item") for x in v]
        else:
            body += [(p.strip(), "text") for p in v.split("\n") if p.strip()]
    texts[(7, 0)] = [("\n".join(t for t, _ in body), "body")]

    req = [{"insertTable": {"rows": 8, "columns": ncol, "location": {"index": 1}}}]
    loc = lambda r, c: {"tableStartLocation": {"index": T}, "rowIndex": r, "columnIndex": c}
    for r, (_, cells) in enumerate(rows):
        for c0, span, _ in cells:
            if span > 1:
                req.append({"mergeTableCells": {"tableRange": {"tableCellLocation": loc(r, c0), "rowSpan": 1, "columnSpan": span}}})
    same = lambda vals: {v: [i for i, x in enumerate(vals) if x == v] for v in dict.fromkeys(vals)}
    for w, idx in same([round(w, 3) for w in widths]).items():
        req.append({"updateTableColumnProperties": {"tableStartLocation": {"index": T}, "columnIndices": idx,
                    "tableColumnProperties": {"widthType": "FIXED_WIDTH", "width": {"magnitude": w, "unit": "PT"}},
                    "fields": "widthType,width"}})
    for h, idx in same([h for h, _ in rows]).items():
        req.append({"updateTableRowStyle": {"tableStartLocation": {"index": T}, "rowIndices": idx,
                    "tableRowStyle": {"minRowHeight": {"magnitude": h, "unit": "PT"}}, "fields": "minRowHeight"}})
    pad = {"magnitude": 2, "unit": "PT"}
    req.append({"updateTableCellStyle": {"tableStartLocation": {"index": T},
                "tableCellStyle": {"borderTop": BLUE, "borderBottom": BLUE, "borderLeft": BLUE, "borderRight": BLUE,
                                   "paddingLeft": pad, "paddingTop": pad, "paddingRight": pad, "paddingBottom": pad,
                                   "contentAlignment": "MIDDLE"},
                "fields": "borderTop,borderBottom,borderLeft,borderRight,paddingLeft,paddingTop,paddingRight,paddingBottom,contentAlignment"}})
    req.append({"updateTableCellStyle": {"tableRange": {"tableCellLocation": loc(7, 0), "rowSpan": 1, "columnSpan": ncol},
                "tableCellStyle": {"contentAlignment": "TOP"}, "fields": "contentAlignment"}})

    order = sorted(texts)                    # 칸 위치 순서
    for key in reversed(order):              # 뒤 칸부터 넣어야 앞 칸 위치가 그대로다
        req.append({"insertText": {"location": {"index": para(*key)}, "text": "".join(t for t, _ in texts[key])}})

    # 글을 넣은 뒤의 실제 위치: 앞 칸들에 넣은 글 길이만큼 밀린다
    shift, final = 0, {}
    for key in order:
        final[key] = para(*key) + shift
        shift += u16("".join(t for t, _ in texts[key]))
    table_end = para(7, ncol - 1) + shift + 1

    def ts(a, b, style, fields):
        if b > a:
            req.append({"updateTextStyle": {"range": {"startIndex": a, "endIndex": b}, "textStyle": style, "fields": fields}})

    def ps(a, b, style, fields):
        req.append({"updateParagraphStyle": {"range": {"startIndex": a, "endIndex": b}, "paragraphStyle": style, "fields": fields}})

    one = {"magnitude": 1, "unit": "PT"}
    pt = lambda v: {"magnitude": v, "unit": "PT"}
    ps(T + 1, table_end, {"indentStart": one, "indentFirstLine": one}, "indentStart,indentFirstLine")
    # 표 전체를 머리 칸 기본(Arimo 12pt 굵게)으로 입히고, 다른 곳만 바꾼다
    ts(T + 1, table_end, {"weightedFontFamily": FONT, "fontSize": pt(12), "bold": True}, "weightedFontFamily,fontSize,bold")
    for key in order:
        if key == (7, 0):
            continue
        p = final[key]
        for t, k in texts[key]:
            n = u16(t)
            if k == "h14":
                ts(p, p + n, {"fontSize": pt(14)}, "fontSize")
            elif k == "s10":
                ts(p, p + n, {"fontSize": pt(10), "bold": False}, "fontSize,bold")
            p += n

    p0 = final[(7, 0)]
    starts, p = [], p0
    for t, k in body:
        starts.append(p)
        p += u16(t) + 1
    body_end = p
    ps(p0, body_end, {"lineSpacing": 145}, "lineSpacing")
    ts(p0, body_end - 1, {"fontSize": pt(10.5), "bold": False}, "fontSize,bold")
    for (t, k), a in zip(body, starts):
        if k == "title":
            ts(a, a + u16(t), {"fontSize": pt(13), "bold": True}, "fontSize,bold")
        elif k == "sec":
            ts(a, a + u16(t), {"fontSize": pt(11), "bold": True}, "fontSize,bold")
            g = {"red": 0.9372549, "green": 0.9372549, "blue": 0.9372549}   # 소제목 줄 회색 바탕
            ps(a, a + 1, {"shading": {"backgroundColor": {"color": {"rgbColor": g}}}}, "shading")
    ps(starts[0], starts[0] + 1, {"alignment": "CENTER"}, "alignment")
    for i, j in lists:
        if j > i:
            req.append({"createParagraphBullets": {"range": {"startIndex": starts[i], "endIndex": starts[j - 1] + 1},
                                                   "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
            ps(starts[i], starts[j - 1] + 1, {"indentStart": {"magnitude": 37, "unit": "PT"},
                                              "indentFirstLine": {"magnitude": 19, "unit": "PT"}}, "indentStart,indentFirstLine")
    return req


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx"); ap.add_argument("author"); ap.add_argument("drafts", nargs="+")
    ap.add_argument("--out", required=True); ap.add_argument("--per", type=int, default=4)
    a = ap.parse_args()
    form = read_form(a.docx)
    entries = sorted((e for f in a.drafts for e in json.loads(Path(f).read_text(encoding="utf-8"))), key=lambda e: e["date"])
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(entries), a.per):
        reqs = [r for e in entries[i:i + a.per] for r in build(form, a.author, e)]
        (out / f"batch_{i // a.per + 1:02d}.json").write_text(json.dumps(reqs, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(out / f"batch_{i // a.per + 1:02d}.json", [e["date"] for e in entries[i:i + a.per]], len(reqs))


if __name__ == "__main__":
    main()
