"""Google 문서를 Claude 커넥터 없이 이 PC의 OAuth 토큰으로 읽고 쓴다(회의록 · 연구노트 공용).

처음 한 번: `gdocs.py auth` → 표준 오류에 찍힌 「허용 주소」를 세 문서(2026 회의록, 연구노트 둘)를
  모두 편집할 수 있는 Google 계정이 로그인된 크롬 창에서 열고 「허용」한다.
  토큰은 <claude-skills>/.secrets/google_docs_token.json 에 남고 스스로 갱신된다.
  OAuth 클라이언트는 유튜브 업로드와 같은 .secrets/youtube_client.json 을 쓴다.

사용:
  gdocs.py auth
  gdocs.py head <문서ID> [--chars 3000]        문서 앞부분을 글자로 찍는다(이미 쓴 날짜 확인용)
  gdocs.py read <문서ID> <출력.json>            Docs API documents.get(탭 포함) 결과 — minutes_insert.py 입력
  gdocs.py docx <문서ID> <출력.docx>            docx로 내보낸다 — note_table.py 입력
  gdocs.py update <문서ID> <요청.json>          {"requests":[…], "revisionId"?: …} 를 batchUpdate로 보낸다.
                                                 revisionId가 있으면 그 판일 때만 쓴다(그사이 바뀌었으면 실패).
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]          # claude-skills
SECRETS = ROOT / ".secrets"
CLIENT, TOKEN = SECRETS / "youtube_client.json", SECRETS / "google_docs_token.json"
SCOPES = ["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive.readonly"]
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def creds(interactive=False):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    c = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if c and c.expired and c.refresh_token:
        c.refresh(Request())
    if not c or not c.valid:
        if not interactive:
            sys.exit(f"Google 문서 토큰 없음 또는 만료: {TOKEN} — `gdocs.py auth`로 한 번 허용한다")
        if not CLIENT.exists():
            sys.exit(f"OAuth 클라이언트 파일 없음: {CLIENT}")
        from google_auth_oauthlib.flow import InstalledAppFlow
        c = InstalledAppFlow.from_client_secrets_file(str(CLIENT), SCOPES).run_local_server(
            port=8766, open_browser=False, authorization_prompt_message="허용 주소: {url}")
    SECRETS.mkdir(exist_ok=True)
    TOKEN.write_text(c.to_json(), encoding="utf-8")
    return c


def export(doc_id, mime):
    """files.export는 10MB에서 막히므로(연구노트 문서는 수십 MB) 파일의 exportLinks로 받는다."""
    from google.auth.transport.requests import AuthorizedSession
    from googleapiclient.discovery import build
    c = creds()
    links = build("drive", "v3", credentials=c).files().get(fileId=doc_id, fields="exportLinks", supportsAllDrives=True).execute().get("exportLinks", {})
    if mime not in links:
        sys.exit(f"{doc_id}: {mime} 내보내기 주소 없음 — 있는 것: {list(links)}")
    r = AuthorizedSession(c).get(links[mime], timeout=600)
    r.raise_for_status()
    return r.content


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth")
    p = sub.add_parser("head"); p.add_argument("doc"); p.add_argument("--chars", type=int, default=3000)
    p = sub.add_parser("read"); p.add_argument("doc"); p.add_argument("out")
    p = sub.add_parser("docx"); p.add_argument("doc"); p.add_argument("out")
    p = sub.add_parser("update"); p.add_argument("doc"); p.add_argument("req")
    a = ap.parse_args()

    if a.cmd == "auth":
        c = creds(interactive=True)
        from googleapiclient.discovery import build
        about = build("drive", "v3", credentials=c).about().get(fields="user(emailAddress)").execute()
        print("허용된 계정:", about["user"]["emailAddress"])
    elif a.cmd == "head":
        sys.stdout.reconfigure(encoding="utf-8")
        print(export(a.doc, "text/plain").decode("utf-8-sig")[:a.chars])
    elif a.cmd == "docx":
        Path(a.out).write_bytes(export(a.doc, DOCX))
        print(a.out, Path(a.out).stat().st_size, "bytes")
    elif a.cmd == "read":
        from googleapiclient.discovery import build
        d = build("docs", "v1", credentials=creds()).documents().get(documentId=a.doc, includeTabsContent=True).execute()
        Path(a.out).write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        print(a.out, "revisionId", d["revisionId"])
    elif a.cmd == "update":
        from googleapiclient.discovery import build
        r = json.loads(Path(a.req).read_text(encoding="utf-8"))
        if not isinstance(r, dict) or not r.get("requests"):
            sys.exit(f"{a.req}: {{\"requests\": […]}} 모양이 아니거나 요청이 비어 있음")
        body = {"requests": r["requests"]}
        if r.get("revisionId"):
            body["writeControl"] = {"requiredRevisionId": r["revisionId"]}
        out = build("docs", "v1", credentials=creds()).documents().batchUpdate(documentId=a.doc, body=body).execute()
        print("보냄", len(r["requests"]), "요청 → 새 revisionId", out["writeControl"]["requiredRevisionId"])


if __name__ == "__main__":
    main()
