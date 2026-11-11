"""회의 음성 → 발화자와 시각이 붙은 전사본.

문장은 이 PC의 faster-whisper large-v3-turbo(무료, CPU)로 받아 적고,
발화자 이름은 Zoom 클라우드 녹화의 받아쓰기(timeline)에서 시각이 가장 많이 겹치는 사람으로 붙인다.

사용:
  <skills>/.venv-stt/Scripts/python.exe -X utf8 transcribe.py <음성 파일> <출력.txt>
      [--zoom <Zoom get_recording_resource 결과 JSON>] [--glossary <용어집.md>]

출력 한 덩어리:
  <발화자> mm:ss
  <문장>
  (빈 줄)
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]          # claude-skills
MODEL_DIR = ROOT / ".stt-models" / "fw-large-v3-turbo"
MODEL_REPO = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
SR = 16000


def find_ffmpeg():
    hits = glob.glob(os.path.expandvars(
        r"%LOCALAPPDATA%/Microsoft/WinGet/Packages/Gyan.FFmpeg_*/ffmpeg-*/bin/ffmpeg.exe"))
    if hits:
        return hits[0]
    from shutil import which
    exe = which("ffmpeg")
    if not exe:
        sys.exit("ffmpeg 없음: winget install Gyan.FFmpeg 으로 설치한다")
    return exe


def load_audio(path):
    import numpy as np
    pcm = subprocess.run([find_ffmpeg(), "-v", "error", "-i", str(path), "-f", "s16le",
                          "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    if not pcm:
        sys.exit(f"음성을 읽지 못함: {path}")
    return np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0


def ensure_model():
    if not (MODEL_DIR / "model.bin").exists():
        # Windows는 심볼릭 링크 권한이 없어서 HF 캐시 대신 일반 폴더에 받는다.
        from huggingface_hub import snapshot_download
        snapshot_download(MODEL_REPO, local_dir=str(MODEL_DIR))
    return str(MODEL_DIR)


def glossary_prompt(path):
    """용어집 표의 「고친 말」 칸을 모아 모델에 미리 알려 줄 낱말 목록을 만든다."""
    words = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[1] and not set(cells[1]) <= set("-: ") and cells[1] != "고친 말":
            words += [w.strip() for w in re.split(r"[·,]", cells[1]) if w.strip()]
    return ", ".join(dict.fromkeys(words))


def ts(t):
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def load_zoom(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    tl = d["transcripts"][0]["timeline"]
    return [(ts(x["ts"]), ts(x["end_ts"]), x["display_name"]) for x in tl]


def speaker_of(s, e, zoom):
    best, name = 0.0, None
    for zs, ze, who in zoom:
        ov = min(e, ze) - max(s, zs)
        if ov > best:
            best, name = ov, who
    return name


def mmss(sec):
    sec = int(sec)
    return f"{sec // 3600:d}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60:02d}:{sec % 60:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("out")
    ap.add_argument("--zoom")
    ap.add_argument("--glossary")
    a = ap.parse_args()

    from faster_whisper import WhisperModel
    model = WhisperModel(ensure_model(), device="cpu", compute_type="int8", cpu_threads=os.cpu_count())
    prompt = glossary_prompt(a.glossary) if a.glossary else None
    segs, _ = model.transcribe(load_audio(a.audio), language="ko", vad_filter=True,
                               beam_size=5, initial_prompt=prompt)
    zoom = load_zoom(a.zoom) if a.zoom else []

    blocks, cur = [], None          # 같은 사람이 이어 말하면 한 덩어리로 묶는다
    for s in segs:
        who = (speaker_of(s.start, s.end, zoom) if zoom else None) or "Participants ?"
        text = s.text.strip()
        if not text:
            continue
        if cur and cur[0] == who:
            cur[2].append(text)
        else:
            cur = [who, s.start, [text]]
            blocks.append(cur)
        print(f"\r{mmss(s.end)}", end="", file=sys.stderr, flush=True)

    if not blocks:
        sys.exit(f"받아 적은 말이 없음: {a.audio}")
    Path(a.out).write_text("".join(f"{w} {mmss(t)}\n{' '.join(x)}\n\n" for w, t, x in blocks), encoding="utf-8")
    print(f"\n{len(blocks)}덩어리 → {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
