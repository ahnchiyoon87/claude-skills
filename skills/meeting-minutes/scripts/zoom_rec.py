"""Zoom 클라우드 녹화를 Claude 커넥터 · 크롬 없이 Zoom Server-to-Server OAuth 앱 토큰으로 받는다.

처음 한 번: marketplace.zoom.us → Develop → Build App → Server-to-Server OAuth 앱을 만들고
  권한(scope)에 클라우드 녹화 읽기(cloud_recording:read:list_user_recordings:admin,
  cloud_recording:read:recording:admin 또는 옛 이름 recording:read:admin)를 더해 Activate 한다.
  나온 값 셋을 <claude-skills>/.secrets/zoom_s2s.json 에 둔다:
  {"account_id": "…", "client_id": "…", "client_secret": "…", "user": "녹화한 Zoom 사용자 이메일"}

사용:
  zoom_rec.py list <YYYY-MM-DD>                          그날 녹화 목록(제목 · 시작 · 파일 종류)
  zoom_rec.py get <YYYY-MM-DD> <저장 폴더> [--topic 상시]  제목에 --topic이 든 녹화 하나의
      mp4 · m4a · 받아쓰기(vtt)를 <날짜>_<topic>.mp4/.m4a/.vtt 로 받고 크기를 목록 값과 대조한다.
      받아쓰기가 아직 없으면(녹화 처리 중) 아무것도 받지 않고 종료 코드 3으로 끝난다.
"""
import argparse, base64, json, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]          # claude-skills
CONF = ROOT / ".secrets" / "zoom_s2s.json"
API = "https://api.zoom.us/v2"


def token(conf):
    basic = base64.b64encode(f"{conf['client_id']}:{conf['client_secret']}".encode()).decode()
    q = urllib.parse.urlencode({"grant_type": "account_credentials", "account_id": conf["account_id"]})
    req = urllib.request.Request(f"https://zoom.us/oauth/token?{q}", method="POST",
                                 headers={"Authorization": f"Basic {basic}"})
    return json.load(urllib.request.urlopen(req, timeout=60))["access_token"]


def get_json(tok, path, **q):
    req = urllib.request.Request(f"{API}{path}?{urllib.parse.urlencode(q)}", headers={"Authorization": f"Bearer {tok}"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        sys.exit(f"Zoom {path} 실패 {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")


def meetings(tok, user, day):
    d = get_json(tok, f"/users/{urllib.parse.quote(user)}/recordings", **{"from": day, "to": day, "page_size": 300})
    return d.get("meetings", [])


def download(tok, url, out, size):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=600) as r, open(out, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    got = out.stat().st_size
    if size and got != size:
        sys.exit(f"{out}: 받은 크기 {got} ≠ 목록 크기 {size}")
    print(out, got, "bytes")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("date")
    p = sub.add_parser("get"); p.add_argument("date"); p.add_argument("dir"); p.add_argument("--topic", default="상시")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if not CONF.exists():
        sys.exit(f"Zoom 앱 값 없음: {CONF} — 이 파일 머리말대로 만든다")
    conf = json.loads(CONF.read_text(encoding="utf-8"))
    bad = [k for k in ("account_id", "client_id", "client_secret") if not conf.get(k)]
    if "@" not in conf.get("user", ""):
        bad.append("user(이메일)")
    if bad:
        sys.exit(f"{CONF}: 값이 비었음 — {bad}")
    tok = token(conf)
    ms = meetings(tok, conf["user"], a.date)

    if a.cmd == "list":
        for m in ms:
            print(m["start_time"], m["topic"], [f["file_type"] for f in m.get("recording_files", [])])
        if not ms:
            print(f"{a.date} 녹화 없음")
        return

    hits = [m for m in ms if a.topic in m["topic"]]
    if len(hits) != 1:
        sys.exit(f"{a.date} 제목에 {a.topic!r}이 든 녹화가 {len(hits)}개: {[m['topic'] for m in ms]}")
    files = [f for f in hits[0]["recording_files"] if f.get("status") == "completed"]
    pick = {}
    for kind in ("MP4", "M4A", "TRANSCRIPT"):
        cand = [f for f in files if f["file_type"] == kind]
        if kind == "TRANSCRIPT" and not cand:
            print(f"{a.date} 받아쓰기(TRANSCRIPT)가 아직 없음 — 녹화 처리 중", file=sys.stderr)
            sys.exit(3)
        if not cand:
            sys.exit(f"{a.date} {kind} 파일 없음: {[f['file_type'] for f in files]}")
        pick[kind] = max(cand, key=lambda f: f.get("file_size", 0))   # 화면 · 발표자 보기 여럿이면 가장 큰 것
    out = Path(a.dir); out.mkdir(parents=True, exist_ok=True)
    for kind, ext in (("MP4", "mp4"), ("M4A", "m4a"), ("TRANSCRIPT", "vtt")):
        f = pick[kind]
        download(tok, f["download_url"], out / f"{a.date}_{a.topic}.{ext}", f.get("file_size"))


if __name__ == "__main__":
    main()
