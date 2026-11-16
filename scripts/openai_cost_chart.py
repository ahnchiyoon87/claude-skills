"""OpenAI 조직 지출(달러)을 API 키별 · 날짜별 막대그래프 그림으로 만든다. 로그인 없이 관리자 키로 한다.

처음 한 번: platform.openai.com → Settings → Admin keys → 새 관리자 키(Permissions: Read only)를 만들고
  <claude-skills>/.secrets/openai_admin.json 에 {"admin_key": "sk-admin-…"} 로 둔다.

사용:
  python -X utf8 openai_cost_chart.py <YYYY-MM> <출력.png>      그 달 1일부터 말일(이번 달이면 오늘)까지
출력: 날짜마다 API 키 이름별로 쌓은 막대그래프와 범례, 제목에 기간과 합계. 표준 출력에 키 이름별 합계.
- 키 이름은 프로젝트 API 키 목록에서 읽는다. 이름이 같은 키(같은 사람이 다시 만든 키)는 한 이름으로 합친다.
- 목록에 없는 키(지운 키)는 API가 이름을 주지 않으므로 「삭제된 키」로 합친다.
- 반올림해 US$0.00인 키는 그림에서 뺀다.
"""
import argparse, calendar, collections, datetime, json, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # claude-skills
KEY = ROOT / ".secrets" / "openai_admin.json"
KST = datetime.timezone(datetime.timedelta(hours=9))


def get(path, key, **q):
    url = f"https://api.openai.com/v1{path}?{urllib.parse.urlencode(q, doseq=True)}"
    try:
        return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"}), timeout=60))
    except urllib.error.HTTPError as e:
        sys.exit(f"OpenAI {path} 실패 {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")


def key_names(key):
    names = {}
    for p in get("/organization/projects", key, limit=100, include_archived="true")["data"]:
        after = None
        while True:
            q = {"limit": 100} | ({"after": after} if after else {})
            d = get(f"/organization/projects/{p['id']}/api_keys", key, **q)
            names.update({k["id"]: k["name"] for k in d["data"]})
            if not d.get("has_more"):
                break
            after = d["last_id"]
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("month"); ap.add_argument("out")
    a = ap.parse_args()
    if not KEY.exists():
        sys.exit(f"관리자 키 없음: {KEY} — 이 파일 머리말대로 만든다")
    key = json.loads(KEY.read_text(encoding="utf-8"))["admin_key"]
    y, m = map(int, a.month.split("-"))
    first = datetime.date(y, m, 1)
    last = min(datetime.date(y, m, calendar.monthrange(y, m)[1]), datetime.datetime.now(datetime.timezone.utc).date())
    start = int(datetime.datetime(y, m, 1, tzinfo=datetime.timezone.utc).timestamp())
    end = int(datetime.datetime.combine(last + datetime.timedelta(days=1), datetime.time(), datetime.timezone.utc).timestamp())

    names = key_names(key)
    days = [first + datetime.timedelta(days=i) for i in range((last - first).days + 1)]
    cost = collections.defaultdict(lambda: collections.defaultdict(float))   # 이름 → 날짜 → 달러
    page = None
    while True:
        q = {"start_time": start, "end_time": end, "group_by": "api_key_id", "limit": 31} | ({"page": page} if page else {})
        d = get("/organization/costs", key, **q)
        for b in d["data"]:
            day = datetime.datetime.fromtimestamp(b["start_time"], datetime.timezone.utc).date()
            for r in b["results"]:
                who = names.get(r["api_key_id"], "삭제된 키") if r["api_key_id"] else "키 없음"
                cost[who][day] += float(r["amount"]["value"])
        if not d.get("has_more"):
            break
        page = d["next_page"]

    totals = {w: sum(v.values()) for w, v in cost.items()}
    order = [w for w, t in sorted(totals.items(), key=lambda x: -x[1]) if round(t, 2) > 0]
    total = sum(totals.values())
    if not order:
        sys.exit(f"{a.month}: 지출이 없음")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "Malgun Gothic"
    fig, ax = plt.subplots(figsize=(10, 5), dpi=200)
    bottom = [0.0] * len(days)
    for w in order:
        vals = [cost[w].get(dd, 0.0) for dd in days]
        ax.bar([dd.day for dd in days], vals, bottom=bottom, label=f"{w}  US${totals[w]:.2f}", width=0.7)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_title(f"OpenAI API 키별 지출 · {first:%Y-%m-%d} ~ {last:%Y-%m-%d} · 합계 US${total:.2f}", fontsize=13, loc="left")
    ax.set_xlabel("날짜(UTC, 일)"); ax.set_ylabel("US$")
    ax.set_xticks([dd.day for dd in days])
    ax.grid(axis="y", alpha=0.3); ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(a.out)
    for w in order:
        print(f"{w}\tUS${totals[w]:.2f}")
    print(f"합계\tUS${total:.2f}\t→ {a.out}")


if __name__ == "__main__":
    main()
