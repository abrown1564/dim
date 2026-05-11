"""
ingest_youtube.py — Download captions/transcripts from YouTube URLs.

Falls back to audio download + Whisper transcription when no captions exist.

Requirements:
    pip install yt-dlp faster-whisper

Usage:
    python ingest_youtube.py "https://youtube.com/watch?v=..." [url2 ...]

Output:
    app/data/queue/[video_title]_extracted_txt.txt
"""

import argparse
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import yt_dlp

HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")

_SCRIPTS_DIR = Path(__file__).resolve().parent
_FALLBACK_HELPER_DIRS = [
    _SCRIPTS_DIR,
    Path("/Users/Ali/Documents/SellerSpace/sellerspace-app/app/scripts"),
]


def _add_helper_paths() -> Path:
    for candidate in _FALLBACK_HELPER_DIRS:
        if (candidate / "source_profiles.py").exists() and (
            candidate / "transcribe_audio.py"
        ).exists():
            if str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
            return candidate
    raise FileNotFoundError(
        "Could not locate source_profiles.py and transcribe_audio.py in any known helper directory."
    )


HELPER_DIR = _add_helper_paths()

from source_profiles import build_canonical_source_key, get_profile, suggest_source_code  # noqa: E402
from transcribe_audio import (
    SOURCE_INGEST_DB,
    infer_content_form,
    init_source_ingest_db,
    log_transcript_source,
    normalize_content_form as normalize_legacy_content_form,
)  # noqa: E402

FFMPEG_PATH = os.environ.get("FFMPEG_PATH", "/opt/homebrew/bin")
QUEUE_DIR = Path("/Users/Ali/Documents/SellerSpace/To-chunk/New/_quarantine/_approved")

CONTENT_FORM_CHOICES = [
    "video essay",
    "interview",
    "podcast conversation",
    "debate clip",
    "panel discussion",
    "speech",
    "article",
    "thread",
    "video",
    "unknown",
]

DISCOURSE_MODE_CHOICES = [
    "monologic",
    "dialogic",
    "multi_party",
    "unknown",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def strip_playlist_context(url: str) -> str:
    """
    For normal watch URLs, strip playlist params so yt-dlp treats them as
    single videos by default instead of expanding playlist context.
    """
    parsed = urlparse(url)
    if "youtube.com" not in parsed.netloc and "youtu.be" not in parsed.netloc:
        return url

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))

    # If this is a single-watch URL, preserve only the direct video-related params.
    if parsed.path == "/watch" and "v" in query:
        keep = {}
        for key in ["v", "t", "start", "si"]:
            if key in query:
                keep[key] = query[key]
        return urlunparse(parsed._replace(query=urlencode(keep)))

    return url

def safe_filename(title: str) -> str:
    """Strip characters that are unsafe in filenames."""
    keepchars = " ._-"
    return "".join(c for c in title if c.isalnum() or c in keepchars).strip()


def build_header(
    info: dict,
    url: str,
    source: str,
    content_form: str | None = None,
    discourse_mode: str | None = None,
    date_status: str | None = None,
) -> str:
    upload_raw  = info.get("upload_date", "")          # YYYYMMDD
    upload_fmt  = (
        f"{upload_raw[:4]}-{upload_raw[4:6]}-{upload_raw[6:]}"
        if len(upload_raw) == 8 else "unknown"
    )
    year = int(upload_raw[:4]) if len(upload_raw) == 8 else None

    channel      = info.get("uploader")      or "Unknown"
    channel_id   = info.get("uploader_id")   or ""
    channel_url  = info.get("uploader_url")  or url
    title        = info.get("title")         or "Unknown"
    description  = info.get("description")  or ""

    profile = get_profile(url=channel_url, filename="")
    # Override name with channel if profile didn't resolve a real name
    if profile.get("name", "").lower() in ("", "unknown"):
        profile = dict(profile, name=channel)

    header = (
        f"SOURCE FILE   : {title}\n"
        f"SOURCE NAME   : {channel}\n"
        f"CHANNEL ID    : {channel_id}\n"
        f"CHANNEL URL   : {channel_url}\n"
        f"VIDEO TITLE   : {title}\n"
        f"VIDEO URL     : {url}\n"
        f"SOURCE PREFIX : {profile['source_prefix']} ({profile.get('type', 'unknown')})\n"
        f"RELIABILITY   : {profile.get('default_reliability', 'U')}\n"
        f"PUBLISHED DATE: {upload_fmt}\n"
        f"DATE STATUS   : {date_status or ('confirmed' if upload_fmt != 'unknown' else 'unknown')}\n"
        f"CONTENT FORM  : {content_form or 'video'}\n"
        f"DISCOURSE MODE: {discourse_mode or 'unknown'}\n"
        f"SUGGESTED CODE: {suggest_source_code(profile, year=year, url=url, title=title)}\n"
        f"TRANSCRIPT    : {source}\n"
        f"EXTRACTED     : {date.today().isoformat()}\n"
    )
    hints = profile.get("chunking_hints", [])
    if hints:
        header += f"CHUNKING HINTS: {' | '.join(hints[:2])}\n"
    if description:
        # Truncate long descriptions to first 300 chars
        desc_preview = description[:300].replace("\n", " ").strip()
        if len(description) > 300:
            desc_preview += "…"
        header += f"DESCRIPTION   : {desc_preview}\n"
    header += "=" * 60 + "\n\n"
    return header


def normalize_discourse_mode(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "mono": "monologic",
        "monologue": "monologic",
        "dialogue": "dialogic",
        "dialogic": "dialogic",
        "dialog": "dialogic",
        "multi": "multi_party",
        "multi_party": "multi_party",
        "multi-party": "multi_party",
        "panel": "multi_party",
        "unknown": "unknown",
    }
    return aliases.get(cleaned, cleaned)


def normalize_content_form(value: str | None) -> str | None:
    if not value:
        return None
    raw = " ".join(value.strip().lower().split())
    if raw in {"", "infer", "dunno", "dont know", "don't know", "na", "n/a"}:
        return None
    aliases = {
        "video": "video",
        "video essay": "video essay",
        "essay": "video essay",
        "interview": "interview",
        "podcast": "podcast conversation",
        "podcast conversation": "podcast conversation",
        "podcast episode": "podcast conversation",
        "episode": "podcast conversation",
        "debate": "debate clip",
        "debate clip": "debate clip",
        "panel": "panel discussion",
        "panel discussion": "panel discussion",
        "speech": "speech",
        "talk": "speech",
        "article": "article",
        "thread": "thread",
        "unknown": "unknown",
    }
    return aliases.get(raw, normalize_legacy_content_form(raw) or raw)


def choose_option(label: str, choices: list[str], current: str | None = None) -> str:
    if current in choices:
        return current

    print(f"  {label}:")
    for idx, choice in enumerate(choices, start=1):
        print(f"    {idx}. {choice}")

    while True:
        raw = input(f"  Choose {label.lower()} [1-{len(choices)}] (default {choices[-1]}): ").strip()
        if not raw:
            return choices[-1]
        if raw.isdigit():
            selected = int(raw)
            if 1 <= selected <= len(choices):
                return choices[selected - 1]
        if raw in choices:
            return raw
        print("  Invalid choice. Please try again.")


# ---------------------------------------------------------------------------
# Caption extraction
# ---------------------------------------------------------------------------

def fetch_info(url: str) -> dict:
    """Fetch video metadata without downloading anything."""
    url = strip_playlist_context(url)
    opts = {
        "quiet": True,
        "skip_download": True,
        "noplaylist": True,
        "ffmpeg_location": FFMPEG_PATH,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def try_captions(
    url: str,
    info: dict,
    out_path: Path,
    content_form: str | None = None,
    discourse_mode: str | None = None,
) -> bool:
    """
    Attempt to download auto-generated or manual captions.
    Returns True if captions were successfully saved.
    """
    subtitles     = info.get("subtitles") or {}
    auto_captions = info.get("automatic_captions") or {}

    has_manual = bool(subtitles.get("en"))
    has_auto   = bool(auto_captions.get("en"))

    if not has_manual and not has_auto:
        return False

    source = "manual captions" if has_manual else "auto-generated captions"
    label = "MANUAL CAPTIONS" if has_manual else "AUTO-GENERATED CAPTIONS"
    print(f"  ✅  {label} FOUND — downloading...")

    with tempfile.TemporaryDirectory() as tmp:
        opts = {
            "skip_download": True,
            "writesubtitles": has_manual,
            "writeautomaticsub": has_auto,
            "subtitleslangs": ["en"],
            "subtitlesformat": "vtt",
            "outtmpl": str(Path(tmp) / "caption.%(ext)s"),
            "quiet": True,
            "ffmpeg_location": FFMPEG_PATH,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([strip_playlist_context(url)])

        # Find the downloaded VTT file
        vtt_files = list(Path(tmp).glob("*.vtt"))
        if not vtt_files:
            return False

        raw = vtt_files[0].read_text(encoding="utf-8")

    # Parse VTT: strip header, timestamps, and blank lines
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if (
            not line
            or line.startswith("WEBVTT")
            or line.startswith("Kind:")
            or line.startswith("Language:")
            or "-->" in line
            or line.isdigit()
        ):
            continue
        # Strip inline VTT tags like <00:00:01.000><c>text</c>
        import re
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line:
            lines.append(line)

    # Deduplicate consecutive identical lines (common in auto-captions)
    deduped = [lines[0]] if lines else []
    for line in lines[1:]:
        if line != deduped[-1]:
            deduped.append(line)

    text = "\n".join(deduped)
    header = build_header(
        info,
        url,
        source,
        content_form=content_form,
        discourse_mode=discourse_mode,
        date_status="confirmed" if info.get("upload_date") else "unknown",
    )
    out_path.write_text(header + text, encoding="utf-8")
    init_source_ingest_db(SOURCE_INGEST_DB)
    upload_raw = info.get("upload_date", "")
    published_date = f"{upload_raw[:4]}-{upload_raw[4:6]}-{upload_raw[6:]}" if len(upload_raw) == 8 else None
    profile = get_profile(url=url, filename=(info.get("title") or "youtube-video"))
    log_transcript_source(
        db_path=SOURCE_INGEST_DB,
        source_url=url,
        source_type="youtube",
        content_form=content_form or "video",
        canonical_source_key=build_canonical_source_key(
            profile,
            year=int(published_date[:4]) if published_date and published_date[:4].isdigit() else None,
            url=url,
            title=info.get("title"),
        ),
        original_filename=(info.get("title") or "youtube-video"),
        extracted_txt_path=str(out_path),
        published_date=published_date,
        date_source="youtube_upload" if published_date else None,
        date_status="confirmed" if published_date else "unknown",
        manual_date=None,
        content_type="youtube/captions",
        file_size_bytes=out_path.stat().st_size if out_path.exists() else None,
        status="captioned",
    )
    print(f"  ✓  Saved → {out_path}")
    return True


# ---------------------------------------------------------------------------
# Audio fallback
# ---------------------------------------------------------------------------

def fallback_audio(
    url: str,
    info: dict,
    out_path: Path,
    content_form: str | None = None,
    discourse_mode: str | None = None,
) -> None:
    """Download audio as MP3 to a temp dir, then call transcribe_audio.py."""
    print("  ℹ  No captions available — falling back to audio transcription...")

    transcribe_script = HELPER_DIR / "transcribe_audio.py"
    if not transcribe_script.exists():
        raise FileNotFoundError(
            f"transcribe_audio.py not found at {transcribe_script}. "
            "It must be available in a known helper directory."
        )

    with tempfile.TemporaryDirectory() as tmp:
        audio_path = Path(tmp) / "audio.%(ext)s"
        opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": str(audio_path),
            "ffmpeg_location": FFMPEG_PATH,
            "noplaylist": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": False,
        }
        print("  ⬇  Downloading audio...")
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([strip_playlist_context(url)])

        mp3_files = list(Path(tmp).glob("*.mp3"))
        if not mp3_files:
            raise RuntimeError("Audio download produced no MP3 file.")

        mp3 = mp3_files[0]
        print(f"  🎙  Running transcribe_audio.py on {mp3.name}...")

        upload_raw = info.get("upload_date", "")
        cmd = [sys.executable, str(transcribe_script), str(mp3)]
        if url:
            cmd += ["--url", url]
        if len(upload_raw) == 8:
            cmd += ["--date", f"{upload_raw[:4]}-{upload_raw[4:6]}-{upload_raw[6:]}"]
            cmd += ["--date-status", "confirmed"]
        cmd += ["--source-type", "youtube", "--content-form", content_form or "video"]
        result = subprocess.run(cmd, check=True)

        approved_dir = Path("/Users/Ali/Documents/SellerSpace/To-chunk/New/_quarantine/_approved")
        transcript_path = approved_dir / (mp3.stem + "_extracted_txt.txt")
        if not transcript_path.exists():
            raise RuntimeError("transcribe_audio.py did not produce a transcript.")
        srt_path = approved_dir / (mp3.stem + ".srt")

        # Prepend our YouTube metadata header then move to the queue
        whisper_text = transcript_path.read_text(encoding="utf-8")
        if "\n============================================================\n\n" in whisper_text:
            whisper_text = whisper_text.split("\n============================================================\n\n", 1)[1]
        header = build_header(
            info,
            url,
            "Whisper (faster-whisper small, audio fallback)",
            content_form=content_form,
            discourse_mode=discourse_mode,
            date_status="confirmed" if len(upload_raw) == 8 else "unknown",
        )
        out_path.write_text(header + whisper_text, encoding="utf-8")
        published_date = f"{upload_raw[:4]}-{upload_raw[4:6]}-{upload_raw[6:]}" if len(upload_raw) == 8 else None
        init_source_ingest_db(SOURCE_INGEST_DB)
        log_transcript_source(
            db_path=SOURCE_INGEST_DB,
            source_url=url,
            source_type="youtube",
            content_form=content_form or "video",
            canonical_source_key=build_canonical_source_key(
                get_profile(url=url, filename=(info.get("title") or "youtube-video")),
                year=int(published_date[:4]) if published_date and published_date[:4].isdigit() else None,
                url=url,
                title=info.get("title"),
            ),
            original_filename=(info.get("title") or "youtube-video"),
            extracted_txt_path=str(out_path),
            published_date=published_date,
            date_source="youtube_upload" if published_date else None,
            date_status="confirmed" if published_date else "unknown",
            manual_date=None,
            content_type="youtube/audio-transcript",
            file_size_bytes=out_path.stat().st_size if out_path.exists() else None,
            status="transcribed",
        )
        transcript_path.unlink(missing_ok=True)
        srt_path.unlink(missing_ok=True)

    print(f"  ✓  Saved → {out_path}")


# ---------------------------------------------------------------------------
# Diarised audio fallback (dialogic / multi_party)
# ---------------------------------------------------------------------------

def _check_diarisation_deps() -> str:
    """Verify pyannote.audio is importable and HF_TOKEN is set. Returns token."""
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if not token:
        raise EnvironmentError(
            "HF_TOKEN not set. Required for pyannote.audio diarisation.\n"
            "  Get a token at https://huggingface.co/settings/tokens\n"
            "  then: export HF_TOKEN=hf_..."
        )
    try:
        import pyannote.audio  # noqa: F401
    except ImportError:
        raise ImportError("pyannote.audio not installed. Run: pip install pyannote.audio")
    try:
        from faster_whisper import WhisperModel  # noqa: F401
    except ImportError:
        raise ImportError("faster-whisper not installed. Run: pip install faster-whisper")
    return token


def _assign_speakers(diarisation, whisper_segments: list) -> list[tuple[str, str]]:
    """Map each Whisper segment to the speaker with most temporal overlap."""
    turns = [
        (turn.start, turn.end, speaker)
        for turn, _, speaker in diarisation.itertracks(yield_label=True)
    ]
    result = []
    for seg in whisper_segments:
        best_speaker = "SPEAKER_00"
        best_overlap = -1.0
        for t_start, t_end, speaker in turns:
            overlap = max(0.0, min(seg.end, t_end) - max(seg.start, t_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = speaker
        result.append((best_speaker, seg.text.strip()))
    return result


def _format_diarised_transcript(attributed: list[tuple[str, str]]) -> str:
    """Merge consecutive same-speaker segments into labelled paragraphs."""
    lines = []
    current_speaker: str | None = None
    buffer: list[str] = []
    for speaker, text in attributed:
        if not text:
            continue
        if speaker != current_speaker:
            if buffer:
                lines.append(f"{current_speaker}: {' '.join(buffer)}")
            current_speaker = speaker
            buffer = [text]
        else:
            buffer.append(text)
    if buffer and current_speaker:
        lines.append(f"{current_speaker}: {' '.join(buffer)}")
    return "\n".join(lines)


def fallback_audio_diarised(
    url: str,
    info: dict,
    out_path: Path,
    content_form: str | None = None,
    discourse_mode: str | None = None,
) -> None:
    """Download audio and produce a speaker-diarised transcript via pyannote + Whisper."""
    print("  ℹ  Dialogic/multi-party content — running pyannote.audio diarisation...")

    try:
        hf_token = _check_diarisation_deps()
    except (EnvironmentError, ImportError) as exc:
        print(f"  ⚠  Diarisation unavailable: {exc}", file=sys.stderr)
        print("  ↩  Falling back to plain Whisper (no speaker attribution).", file=sys.stderr)
        fallback_audio(url, info, out_path, content_form=content_form, discourse_mode=discourse_mode)
        return

    from pyannote.audio import Pipeline as PyannotePipeline
    from faster_whisper import WhisperModel

    with tempfile.TemporaryDirectory() as tmp:
        audio_path = Path(tmp) / "audio.%(ext)s"
        opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": str(audio_path),
            "ffmpeg_location": FFMPEG_PATH,
            "noplaylist": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }],
            "quiet": False,
        }
        print("  ⬇  Downloading audio...")
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([strip_playlist_context(url)])

        wav_files = list(Path(tmp).glob("*.wav"))
        if not wav_files:
            raise RuntimeError("Audio download produced no WAV file.")
        raw_wav = wav_files[0]

        # Resample to 16kHz mono — pyannote requires this and MP3/WAV sample
        # count mismatches cause "expected N samples" errors with compressed audio.
        wav_16k = Path(tmp) / "audio_16k.wav"
        ffmpeg_bin = str(Path(FFMPEG_PATH) / "ffmpeg") if Path(FFMPEG_PATH).is_dir() else FFMPEG_PATH
        subprocess.run(
            [ffmpeg_bin, "-y", "-i", str(raw_wav),
             "-ar", "16000", "-ac", "1", str(wav_16k)],
            check=True, capture_output=True,
        )

        print("  🔊  Running pyannote.audio diarisation (this may take a minute)...")
        diarisation_pipeline = PyannotePipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=hf_token,
        )
        raw_output = diarisation_pipeline(str(wav_16k))
        # pyannote 4.x returns DiarizeOutput dataclass; 3.x returned Annotation directly
        diarisation = getattr(raw_output, "speaker_diarization", raw_output)

        print("  🎙  Transcribing with Whisper...")
        whisper = WhisperModel("small", device="cpu", compute_type="int8")
        segments_iter, _ = whisper.transcribe(str(wav_16k), beam_size=5)
        whisper_segments = list(segments_iter)

        attributed = _assign_speakers(diarisation, whisper_segments)
        transcript_text = _format_diarised_transcript(attributed)

    n_speakers = len({sp for sp, _ in attributed if sp})
    transcript_source = (
        f"pyannote.audio diarisation + Whisper ({n_speakers} speaker(s) detected)"
    )
    header = build_header(
        info,
        url,
        transcript_source,
        content_form=content_form,
        discourse_mode=discourse_mode,
        date_status="confirmed" if info.get("upload_date") else "unknown",
    )
    out_path.write_text(header + transcript_text, encoding="utf-8")

    upload_raw = info.get("upload_date", "")
    published_date = (
        f"{upload_raw[:4]}-{upload_raw[4:6]}-{upload_raw[6:]}"
        if len(upload_raw) == 8 else None
    )
    init_source_ingest_db(SOURCE_INGEST_DB)
    log_transcript_source(
        db_path=SOURCE_INGEST_DB,
        source_url=url,
        source_type="youtube",
        content_form=content_form or "video",
        canonical_source_key=build_canonical_source_key(
            get_profile(url=url, filename=(info.get("title") or "youtube-video")),
            year=int(published_date[:4]) if published_date and published_date[:4].isdigit() else None,
            url=url,
            title=info.get("title"),
        ),
        original_filename=(info.get("title") or "youtube-video"),
        extracted_txt_path=str(out_path),
        published_date=published_date,
        date_source="youtube_upload" if published_date else None,
        date_status="confirmed" if published_date else "unknown",
        manual_date=None,
        content_type="youtube/audio-diarised",
        file_size_bytes=out_path.stat().st_size if out_path.exists() else None,
        status="diarised",
    )
    print(f"  ✓  Saved → {out_path}  ({n_speakers} speaker(s))")


# ---------------------------------------------------------------------------
# Per-video entry point
# ---------------------------------------------------------------------------

def process_video(
    url: str,
    info: dict,
    content_form_override: str | None = None,
    discourse_mode_override: str | None = None,
    interactive: bool = False,
    force_diarise: bool = False,
) -> None:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    title    = info.get("title", "unknown")
    filename = safe_filename(title) + "_extracted_txt.txt"
    out_path = QUEUE_DIR / filename
    content_form = content_form_override or infer_content_form(
        audio_path=Path(filename),
        source_type="youtube",
        source_url=url,
    )
    discourse_mode = discourse_mode_override

    if interactive:
        guessed_form = normalize_content_form(content_form) or "unknown"
        content_form = choose_option("Content form", CONTENT_FORM_CHOICES, guessed_form)
        discourse_mode = choose_option(
            "Discourse mode",
            DISCOURSE_MODE_CHOICES,
            discourse_mode,
        )
    else:
        content_form = normalize_content_form(content_form) or "unknown"
        discourse_mode = discourse_mode or "unknown"

    print(f"  Title   : {title}")
    print(f"  Channel : {info.get('uploader', 'Unknown')}")
    print(f"  Form    : {content_form}")
    print(f"  Mode    : {discourse_mode}")
    print(f"  Output  : {out_path}")

    needs_diarisation = force_diarise or discourse_mode in ("dialogic", "multi_party")

    if not needs_diarisation and discourse_mode == "monologic" and interactive:
        ans = input("  Diarise for speaker separation? [y/N]: ").strip().lower()
        needs_diarisation = ans in ("y", "yes")

    if needs_diarisation:
        # Captions have no speaker attribution — analytically incomplete for multi-speaker content.
        fallback_audio_diarised(
            url, info, out_path,
            content_form=content_form,
            discourse_mode=discourse_mode,
        )
    elif not try_captions(
        url, info, out_path,
        content_form=content_form,
        discourse_mode=discourse_mode,
    ):
        fallback_audio(
            url, info, out_path,
            content_form=content_form,
            discourse_mode=discourse_mode,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download YouTube captions/transcripts to app/data/queue/."
    )
    parser.add_argument("urls", nargs="*", metavar="URL",
                        help="YouTube URL(s) — videos or playlists")
    parser.add_argument("--content-form",
                        help="Content form override")
    parser.add_argument("--discourse-mode",
                        help="Discourse mode override (monologic, dialogic, multi_party)")
    parser.add_argument("--no-prompt", action="store_true",
                        help="Do not prompt for content form and discourse mode; use overrides or defaults")
    parser.add_argument("--diarise", action="store_true",
                        help="Force speaker diarisation regardless of discourse mode")
    args = parser.parse_args()
    args.content_form = normalize_content_form(args.content_form)
    args.discourse_mode = normalize_discourse_mode(args.discourse_mode)

    if not args.urls:
        print("Enter YouTube URL(s), one per line. Leave blank and press Enter when done.")
        urls = []
        while True:
            val = input("URL: ").strip()
            if not val:
                break
            urls.append(val)
        args.urls = urls

    if not args.urls:
        print("No URLs provided — exiting.")
        return

    total_ok = 0
    total_failed = 0

    for url in args.urls:
        print(f"\nFetching info: {url}")
        try:
            info = fetch_info(url)
        except Exception as exc:
            print(f"  ✗  Could not fetch info: {exc}")
            total_failed += 1
            continue

        # Flatten playlists into individual entries
        entries = info.get("entries") or [info]

        for entry in entries:
            video_url = entry.get("webpage_url") or url
            print(f"\nProcessing: {entry.get('title', video_url)}")
            try:
                process_video(
                    video_url,
                    entry,
                    content_form_override=args.content_form,
                    discourse_mode_override=args.discourse_mode,
                    interactive=not args.no_prompt,
                    force_diarise=args.diarise,
                )
                total_ok += 1
            except Exception as exc:
                print(f"  ✗  Failed: {exc}")
                total_failed += 1

    print("\n" + "=" * 60)
    print("Summary")
    print(f"  Videos processed : {total_ok}")
    if total_failed:
        print(f"  Videos failed    : {total_failed}")
    print(f"  Output folder    : {QUEUE_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
