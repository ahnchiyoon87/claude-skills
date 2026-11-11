"""회의 녹화 영상을 YouTube에 비공개로 올리고 재생목록에 넣는다.

처음 한 번: Google Cloud에서 만든 OAuth 클라이언트(데스크톱 앱) JSON을
  <claude-skills>/.secrets/youtube_client.json 에 둔다. 첫 실행 때 브라우저가 열리면
  회의록 채널 계정으로 「허용」한다. 그 뒤 토큰은 .secrets/youtube_token.json 에 남아 다시 묻지 않는다.

사용:
  python -X utf8 youtube_upload.py <영상.mp4> "<제목>" [--playlist "내부 회의록"]
출력: 마지막 줄에 https://youtu.be/<id>

uengine.org 공유(비공개 공유 대상)는 API로 바꿀 수 없어서 Studio 화면에서 따로 한다.
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SECRETS = ROOT / ".secrets"
CLIENT, TOKEN = SECRETS / "youtube_client.json", SECRETS / "youtube_token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]


def creds():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    c = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if c and c.expired and c.refresh_token:
        c.refresh(Request())
    if not c or not c.valid:
        if not CLIENT.exists():
            sys.exit(f"OAuth 클라이언트 파일 없음: {CLIENT}")
        # 허용 주소를 표준 오류로 바로 내보낸다(기본 브라우저가 다른 크롬 프로필일 수 있어 열 창을 고르게 한다)
        c = InstalledAppFlow.from_client_secrets_file(str(CLIENT), SCOPES).run_local_server(
            port=8765, open_browser=False, authorization_prompt_message="허용 주소: {url}")
    SECRETS.mkdir(exist_ok=True)
    TOKEN.write_text(c.to_json(), encoding="utf-8")
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("title"); ap.add_argument("--playlist", default="내부 회의록")
    a = ap.parse_args()
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    yt = build("youtube", "v3", credentials=creds())

    pl = None
    if a.playlist:
        items = yt.playlists().list(part="snippet", mine=True, maxResults=50).execute().get("items", [])
        pl = next((p["id"] for p in items if p["snippet"]["title"] == a.playlist), None)
        if not pl:
            sys.exit(f"재생목록 없음: {a.playlist!r} — 있는 것: {[p['snippet']['title'] for p in items]}")

    body = {"snippet": {"title": a.title, "categoryId": "22"},
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False}}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(a.video, chunksize=8 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        st, resp = req.next_chunk()
        if st:
            print(f"\r{int(st.progress() * 100)}%", end="", file=sys.stderr, flush=True)
    vid = resp["id"]
    if pl:
        yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pl,
                                  "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
    print(f"\nhttps://youtu.be/{vid}")


if __name__ == "__main__":
    main()
