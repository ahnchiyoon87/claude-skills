"""연구노트 근거: 작성자별 커밋을 날짜(KST)별로 모으되, 과제 범위(스마트공장 운영 시스템 개발)에 드는 커밋만 남긴다.
사용: python -X utf8 collect_commits.py <출력 폴더> <시작 YYYY-MM-DD> <끝 YYYY-MM-DD>
출력: <출력 폴더>/commits_<작성자>.json = {날짜: [{repo, time, subject, body}]}, 그리고 뺀 저장소 목록을 표준 오류로 알린다.
- 원격 저장소는 SYSTEM_REPOS에 맞는 것만 넣는다(강의 · 교육 · 작업 규칙 저장소는 뺀다).
- 로컬 hyd-iot-edu는 커밋이 바꾼 파일 경로로 가른다: 시스템 경로(SYSTEM_PATHS)를 하나라도 바꾼 커밋만 넣고, 강의 제작(workspace/강의제작/)만 바꾼 커밋은 뺀다.
"""
import json, re, subprocess, time, urllib.request, urllib.parse, datetime, sys, collections
from pathlib import Path

OUT, SINCE, UNTIL = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
KST = datetime.timezone(datetime.timedelta(hours=9))
LOCAL, LOCAL_REPO = "D:/work/study/hyd-iot-edu-system", "uengine-oss/hyd-iot-edu"
SYSTEM_REPOS = re.compile(r"/(ceco_demo|robo-[\w-]+|antlr-code-parser|process-gpt[\w-]*|uengine-erp|ontolog[\w-]*)$")
SYSTEM_PATHS = re.compile(r"^(it/|ot/|dmz/|common/|compose[^/]*$|setup/|scripts/|workspace/개발/|\.env\.example$)")
AUTHORS = [("안치윤", "author:ahnchiyoon87", r"ahnchiyoon|^Claude$"),
           ("장진영", "author-email:jyjang@uengine.org", r"jinyoung|jyjang")]


def halves(a, b):
    d, end = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    while d <= end:
        e = min(d + datetime.timedelta(days=14), end)
        yield d.isoformat(), e.isoformat()
        d = e + datetime.timedelta(days=1)


def gh_search(q):
    items, page = [], 1
    while page <= 10:
        url = "https://api.github.com/search/commits?" + urllib.parse.urlencode(
            {"q": q, "per_page": 100, "page": page, "sort": "committer-date"})
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "research-note-collector"})
        for _ in range(5):
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


def local(bucket, author_re):
    out = subprocess.run(["git", "-C", LOCAL, "-c", "diff.renameLimit=0", "log", "--all", f"--since={SINCE}",
                          "--format=%x1e%H%x1f%aI%x1f%an%x1f%B%x1f", "--name-only"],
                         capture_output=True, check=True).stdout.decode("utf-8", "replace")
    kept = dropped = 0
    for rec in out.split("\x1e")[1:]:
        sha, iso, an, msg, files = rec.split("\x1f", 4)
        if not re.search(author_re, an):
            continue
        if any(SYSTEM_PATHS.match(f.strip()) for f in files.splitlines() if f.strip()):
            add(bucket, LOCAL_REPO, iso, msg, sha)
            kept += 1
        else:
            dropped += 1
    return kept, dropped


for name, query, author_re in AUTHORS:
    bucket, skipped = collections.defaultdict(dict), collections.Counter()
    for a, b in halves(SINCE, UNTIL):
        for it in gh_search(f"{query} committer-date:{a}..{b}"):
            repo = it["repository"]["full_name"]
            if repo == LOCAL_REPO:
                continue                      # 로컬 경로 판정으로만 넣는다
            if not SYSTEM_REPOS.search(repo):
                skipped[repo] += 1
                continue
            c = it["commit"]
            add(bucket, repo, c["committer"]["date"], c["message"], it["sha"])
    kept, dropped = local(bucket, author_re)
    res = {d: sorted(v.values(), key=lambda x: x["time"]) for d, v in sorted(bucket.items()) if SINCE <= d <= UNTIL}
    (OUT / f"commits_{name}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{name}: 날짜 {len(res)} · 커밋 {sum(len(v) for v in res.values())} | 로컬 넣음 {kept} 뺌 {dropped} | 뺀 원격 {dict(skipped)}", file=sys.stderr)
