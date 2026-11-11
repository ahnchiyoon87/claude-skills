"""연구노트 근거: 두 작성자의 커밋을 날짜(KST)별로 모은다.
사용: python -X utf8 collect_commits.py <출력 폴더>   (기간 · 작성자 · 로컬 저장소는 아래 상수)
출력: <출력 폴더>/commits_<작성자>.json = {날짜: [{repo, time, subject, body}]} — 스킬 폴더에 두지 않는다.
"""
import json, subprocess, time, urllib.request, urllib.parse, datetime, sys, collections
from pathlib import Path

OUT = Path(sys.argv[1])
SINCE, UNTIL = "2026-08-28", "2026-11-11"
KST = datetime.timezone(datetime.timedelta(hours=9))
LOCAL = "D:/work/study/hyd-iot-edu-system"
MONTHS = [("2026-08-28", "2026-09-15"), ("2026-09-16", "2026-09-30"), ("2026-10-01", "2026-10-15"),
          ("2026-10-16", "2026-10-31"), ("2026-11-01", "2026-11-11")]


def gh_search(q):
    items, page = [], 1
    while page <= 10:
        url = "https://api.github.com/search/commits?" + urllib.parse.urlencode(
            {"q": q, "per_page": 100, "page": page, "sort": "committer-date"})
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "research-note-collector"})
        for attempt in range(5):
            try:
                d = json.load(urllib.request.urlopen(req, timeout=60))
                break
            except urllib.error.HTTPError as e:
                if e.code in (403, 429):
                    time.sleep(65)
                    continue
                raise
        else:
            sys.exit(f"GitHub 검색 실패: {q} page {page}")
        items += d["items"]
        print(q, page, len(d["items"]), "/", d["total_count"], file=sys.stderr)
        if len(d["items"]) < 100:
            break
        page += 1
        time.sleep(7)
    time.sleep(7)
    return items


def add(bucket, repo, iso, msg, sha):
    t = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(KST)
    lines = msg.strip().splitlines()
    bucket[t.date().isoformat()][sha] = {"repo": repo, "time": t.strftime("%H:%M"),
                                         "subject": lines[0][:300], "body": "\n".join(lines[1:])[:600]}


def local(bucket, author_re, exclude_re=None):
    fmt = "%H%x1f%aI%x1f%an%x1f%B%x1e"
    out = subprocess.run(["git", "-C", LOCAL, "log", "--all", f"--since={SINCE}", f"--format={fmt}"],
                         capture_output=True, check=True).stdout.decode("utf-8", "replace")
    import re
    for rec in out.split("\x1e"):
        if not rec.strip():
            continue
        sha, iso, an, msg = rec.strip("\n").split("\x1f", 3)
        if re.search(author_re, an) and not (exclude_re and re.search(exclude_re, an)):
            add(bucket, "uengine-oss/hyd-iot-edu", iso, msg, sha)


for name, query, author_re in [("안치윤", "author:ahnchiyoon87", r"ahnchiyoon|Claude"),
                                ("장진영", "author-email:jyjang@uengine.org", r"jinyoung|jyjang")]:
    bucket = collections.defaultdict(dict)
    for a, b in MONTHS:
        for it in gh_search(f"{query} committer-date:{a}..{b}"):
            c = it["commit"]
            add(bucket, it["repository"]["full_name"], c["committer"]["date"], c["message"], it["sha"])
    local(bucket, author_re)
    res = {d: sorted(v.values(), key=lambda x: x["time"]) for d, v in sorted(bucket.items()) if SINCE <= d <= UNTIL}
    (OUT / f"commits_{name}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(name, "days", len(res), "commits", sum(len(v) for v in res.values()), file=sys.stderr)
