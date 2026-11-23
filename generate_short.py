"""Crea y sube un Short de curiosidades a YouTube, todo con herramientas gratuitas.

Flujo: tema (Gemini gratis o banco de datos propio) -> voz (edge-tts) ->
fondos (Pexels) -> montaje con subtitulos (ffmpeg) -> subida (YouTube Data API).
"""
import asyncio
import json
import os
import pathlib
import random
import re
import subprocess
import sys

import requests

ROOT = pathlib.Path(__file__).resolve().parent
WORK = ROOT / "work"
USED_FILE = ROOT / "used_topics.json"
BANK_FILE = ROOT / "facts_bank.json"

VOICE = os.getenv("TTS_VOICE", "es-ES-AlvaroNeural")
PRIVACY = os.getenv("PRIVACY_STATUS", "public")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- tema y guion
def load_used():
    if USED_FILE.exists():
        return json.loads(USED_FILE.read_text(encoding="utf-8"))
    return []


def gemini_script(used):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    prompt = (
        "Eres guionista de un canal de YouTube Shorts en espanol de curiosidades. "
        "Elige UN dato curioso real, verificable y poco conocido (ciencia, historia, cuerpo humano, "
        "espacio, animales o historia de objetos cotidianos). No inventes nada. "
        "No repitas estos temas ya publicados: " + (" | ".join(used) or "ninguno") + ". "
        "Responde SOLO con JSON con estas claves: "
        '"topic" (el dato en una frase), '
        '"title" (maximo 70 caracteres, termina con #Shorts), '
        '"description" (2 o 3 frases y hashtags #Shorts #curiosidades), '
        '"tags" (lista de 5 a 8 palabras clave), '
        '"narration" (texto de voz en off en espanol, 75 a 100 palabras: gancho inicial, el dato, un giro sorprendente y cierre), '
        '"keywords" (lista de 4 busquedas en INGLES para encontrar videos de fondo, por ejemplo "ocean waves").'
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    try:
        r = requests.post(
            url,
            params={"key": key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.9},
            },
            timeout=90,
        )
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(text)
        for k in ("topic", "title", "description", "tags", "narration", "keywords"):
            if k not in data:
                raise ValueError(f"falta la clave {k}")
        if data["topic"] in used:
            return None
        return data
    except Exception as exc:  # si Gemini falla usamos el banco de datos
        log(f"Gemini no disponible ({exc}); se usa el banco de datos.")
        return None


def bank_script(used):
    bank = json.loads(BANK_FILE.read_text(encoding="utf-8"))
    pending = [f for f in bank if f["topic"] not in used]
    if not pending:
        raise SystemExit("No quedan temas en facts_bank.json. Anade mas o configura GEMINI_API_KEY.")
    return pending[0]


# ----------------------------------------------------------------------- voz
async def _tts(text, path):
    import edge_tts

    await edge_tts.Communicate(text, VOICE).save(str(path))


def make_voice(text, path):
    asyncio.run(_tts(text, path))


def media_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


# ----------------------------------------------------------------- subtitulos
def fmt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def make_srt(text, duration, words_per_chunk=4):
    words = text.split()
    chunks = [" ".join(words[i:i + words_per_chunk]) for i in range(0, len(words), words_per_chunk)]
    weights = [max(len(c), 1) for c in chunks]
    total = sum(weights)
    t = 0.0
    lines = []
    for i, (chunk, w) in enumerate(zip(chunks, weights), start=1):
        d = duration * w / total
        lines.append(f"{i}\n{fmt_time(t)} --> {fmt_time(t + d)}\n{chunk}\n")
        t += d
    return "\n".join(lines)


# ---------------------------------------------------------------------- Pexels
def _pexels_get(path, params):
    headers = {"Authorization": os.environ["PEXELS_API_KEY"]}
    for base in ("https://api.pexels.com/v1/videos", "https://api.pexels.com/videos"):
        r = requests.get(f"{base}/{path}", headers=headers, params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
    r.raise_for_status()


def pick_file(video):
    files = [f for f in video["video_files"] if f.get("file_type") == "video/mp4" and f.get("width")]
    good = [f for f in files if f["width"] >= 720 and f["height"] >= 1280]
    pool = good or files
    return min(pool, key=lambda f: f["width"]) if pool else None


def fetch_clips(keywords, needed_seconds):
    clips, seen, total = [], set(), 0.0
    queries = list(keywords) + ["nature", "abstract light"]
    for kw in queries:
        data = _pexels_get("search", {"query": kw, "orientation": "portrait", "per_page": 15})
        videos = data.get("videos", [])
        random.shuffle(videos)
        for v in videos:
            if v["id"] in seen or v.get("duration", 0) < 4:
                continue
            f = pick_file(v)
            if not f:
                continue
            seen.add(v["id"])
            clips.append(f["link"])
            total += min(v["duration"], 9)
            break
        if total >= needed_seconds and len(clips) >= 3:
            break
    if len(clips) < 2:
        raise SystemExit("No se encontraron suficientes videos de fondo en Pexels.")
    return clips


def download(url, path):
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(path, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)


# --------------------------------------------------------------------- montaje
def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def build_video(clip_paths, audio_path, srt_path, out_path, duration):
    seg = (duration + 0.6) / len(clip_paths)
    parts = []
    for i, cp in enumerate(clip_paths):
        part = WORK / f"part{i}.mp4"
        run([
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(cp), "-t", f"{seg:.3f}", "-an",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", str(part),
        ])
        parts.append(part)
    listfile = WORK / "list.txt"
    listfile.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    joined = WORK / "joined.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(joined)])
    style = (
        "FontName=DejaVu Sans,Bold=1,FontSize=15,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=0,Alignment=2,MarginV=60"
    )
    run([
        "ffmpeg", "-y", "-i", str(joined), "-i", str(audio_path),
        "-vf", f"subtitles={srt_path}:force_style='{style}'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out_path),
    ])


# --------------------------------------------------------------------- YouTube
def upload(video_path, data):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    yt = build("youtube", "v3", credentials=creds)
    title = data["title"][:100]
    if "#shorts" not in title.lower():
        title = (title[:90] + " #Shorts").strip()
    description = data["description"].rstrip() + "\n\nVideos de fondo: Pexels (pexels.com)."
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": data["tags"] if isinstance(data["tags"], list) else [t.strip() for t in str(data["tags"]).split(",")],
            "categoryId": "27",
            "defaultLanguage": "es",
            "defaultAudioLanguage": "es",
        },
        "status": {"privacyStatus": PRIVACY, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]


# ------------------------------------------------------------------------ main
def main():
    WORK.mkdir(exist_ok=True)
    used = load_used()
    data = gemini_script(used) or bank_script(used)
    log(f"Tema: {data['topic']}")

    voice_path = WORK / "voz.mp3"
    make_voice(data["narration"], voice_path)
    duration = media_duration(voice_path)
    log(f"Duracion de la voz: {duration:.1f}s")

    srt_path = WORK / "subs.srt"
    srt_path.write_text(make_srt(data["narration"], duration), encoding="utf-8")

    urls = fetch_clips(data["keywords"], duration + 1)
    clip_paths = []
    for i, u in enumerate(urls):
        p = WORK / f"clip{i}.mp4"
        download(u, p)
        clip_paths.append(p)

    out_path = WORK / "short.mp4"
    build_video(clip_paths, voice_path, srt_path, out_path, duration)
    log(f"Video listo: {out_path}")

    if DRY_RUN:
        log("Modo prueba: no se sube a YouTube.")
        return
    video_id = upload(out_path, data)
    log(f"Subido: https://youtube.com/shorts/{video_id}")
    used.append(data["topic"])
    USED_FILE.write_text(json.dumps(used, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
