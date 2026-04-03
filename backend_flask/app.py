import os
import json
import sqlite3
import uuid
import sys
import logging
from typing import Any
from datetime import date, datetime, timedelta
from functools import wraps
from email.message import EmailMessage
import smtplib
import secrets

import bcrypt
from dotenv import load_dotenv
from flask import Flask, Response, flash, g, redirect, render_template, request, session, url_for
from authlib.integrations.flask_client import OAuth
from openai import OpenAI
from werkzeug.utils import secure_filename
import subprocess
import whisper

from modules.mouth_detection import mouth_bp
from modules.phoneme_scoring import scorer


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "app.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")


load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"), override=False)
load_dotenv(override=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("converseai")


LANGUAGES = [
    {"id": "en-US", "label": "English (US)"},
    {"id": "en-GB", "label": "English (UK)"},
    {"id": "de-DE", "label": "German"},
    {"id": "es-ES", "label": "Spanish"},
]

UI_STRINGS = {
    "en-US": {
        "practice": "Practice",
        "target_sentence": "Target Sentence",
        "visual_capture": "Visual Capture",
        "instructions": "Instructions",
        "start_recording": "Start Recording",
        "stop": "Stop",
        "analyzing": "Analyzing...",
        "listen_native": "Listen to Native",
        "ipa_guide": "Pronunciation Guide",
    },
    "en-GB": {
        "practice": "Practice",
        "target_sentence": "Target Sentence",
        "visual_capture": "Visual Capture",
        "instructions": "Instructions",
        "start_recording": "Start Recording",
        "stop": "Stop",
        "analyzing": "Analyzing...",
        "listen_native": "Listen to Native",
        "ipa_guide": "Pronunciation Guide",
    },
    "de-DE": {
        "practice": "Üben",
        "target_sentence": "Zielsatz",
        "visual_capture": "Visuelle Erfassung",
        "instructions": "Anweisungen",
        "start_recording": "Aufnahme starten",
        "stop": "Stoppen",
        "analyzing": "Analysieren...",
        "listen_native": "Original anhören",
        "ipa_guide": "Aussprache-Leitfaden",
    }
}


def _get_ui_strings(language_id: str) -> dict:
    return UI_STRINGS.get(language_id, UI_STRINGS["en-US"])


def _get_youtube_embed_url(url: str) -> str:
    if not ("youtube.com" in url or "youtu.be" in url):
        return ""
    if "list=" in url:
        pid = url.split("list=")[-1].split("&")[0]
        return f"https://www.youtube.com/embed/videoseries?list={pid}"
    if "watch?v=" in url:
        vid = url.split("watch?v=")[-1].split("&")[0]
        return f"https://www.youtube.com/embed/{vid}"
    if "youtu.be/" in url:
        vid = url.split("youtu.be/")[-1].split("?")[0]
        return f"https://www.youtube.com/embed/{vid}"
    return ""


def _lang_to_whisper_code(language_id: str) -> str:
    if language_id in {"en-US", "en-GB"}:
        return "en"
    if language_id == "ja-JP":
        return "ja"
    if language_id == "de-DE":
        return "de"
    if language_id == "es-ES":
        return "es"
    return "en"


def _tokenize_words(text: str) -> list[str]:
    text = (text or "").lower().strip()
    out = []
    word = []
    for ch in text:
        if ch.isalnum() or ch in {"'", "’"}:
            word.append(ch)
        else:
            if word:
                out.append("".join(word))
                word = []
    if word:
        out.append("".join(word))
    return out


EN_DIGRAPHS = ["tch", "ch", "sh", "th", "ph", "ng", "qu", "ck", "wh"]
DE_DIGRAPHS = ["sch", "ch", "ei", "ie", "eu", "äu", "sp", "st"]
ES_DIGRAPHS = ["ll", "rr", "ch", "qu", "gu"]


def _digraph_phonemes(word: str, digraphs: list[str]) -> list[str]:
    i = 0
    out: list[str] = []
    while i < len(word):
        matched = None
        for d in digraphs:
            if word.startswith(d, i):
                matched = d
                break
        if matched:
            out.append(matched)
            i += len(matched)
        else:
            out.append(word[i])
            i += 1
    return [p for p in out if p.strip()]


def pseudo_phonemes(text: str, language_id: str) -> list[str]:
    words = _tokenize_words(text)
    if not words:
        return []

    phonemes: list[str] = []
    if language_id in {"en-US", "en-GB"}:
        for w in words:
            phonemes.extend(_digraph_phonemes(w, EN_DIGRAPHS))
    elif language_id == "de-DE":
        for w in words:
            phonemes.extend(_digraph_phonemes(w, DE_DIGRAPHS))
    elif language_id == "es-ES":
        for w in words:
            phonemes.extend(_digraph_phonemes(w, ES_DIGRAPHS))
    elif language_id == "ja-JP":
        joined = "".join(words)
        phonemes.extend(list(joined))
    else:
        for w in words:
            phonemes.extend(list(w))

    return [p for p in phonemes if p and p != " "]


def compare_words(expected: str, actual: str, whisper_words: list[dict], confidence_proxy: float) -> list[dict]:
    e = _tokenize_words(expected)
    a = _tokenize_words(actual)
    max_len = max(len(e), len(a))
    out = []
    
    # Map whisper_words to segments for better matching
    # whisper_words: list of dicts {"word": "...", "start": 0, "end": 1, "probability": 0.9}
    
    for i in range(max_len):
        ew = e[i] if i < len(e) else ""
        aw = a[i] if i < len(a) else ""
        
        # Determine status
        # ok=True (Green), ok=False (Red), weak=True (Yellow)
        status = {"expected": ew, "actual": aw, "ok": False, "weak": False}
        
        if ew and ew == aw:
            # Text matched. Now check confidence.
            # Find corresponding whisper word data
            # Use index as simple matching (usually Whisper is in sync with tokens)
            word_conf = 1.0
            if i < len(whisper_words):
                word_conf = whisper_words[i].get("probability", 1.0)
            
            # Combine word-level and segment-level confidence
            final_conf = word_conf * confidence_proxy
            
            if final_conf < 0.55: # Stricter: Low confidence -> Mispronounced
                status["ok"] = False
                status["weak"] = False
            elif final_conf < 0.80: # Stricter: Moderate confidence -> Weak
                status["ok"] = True
                status["weak"] = True
            else:
                status["ok"] = True
                status["weak"] = False
        else:
            # Text didn't match
            status["ok"] = False
            status["weak"] = False
            
        out.append(status)
    return out


def score_from_words(expected: str, actual: str, word_rows: list[dict]) -> tuple[float, float]:
    e = _tokenize_words(expected)
    a = _tokenize_words(actual)
    if not e and not a:
        return 0.0, 0.0
    
    max_len = max(len(e), len(a), 1)
    
    # Accuracy score based on word-level pronunciation quality
    # Perfect word = 1.0, Weak word = 0.5, Incorrect word = 0.0
    quality_sum = 0.0
    for w in word_rows:
        if w["ok"] and not w["weak"]:
            quality_sum += 1.0
        elif w["weak"]:
            quality_sum += 0.5
        else:
            quality_sum += 0.0
            
    accuracy = (quality_sum / max_len) * 100.0
    fluency = min(100.0, (len(a) / max(1, len(e))) * 100.0)
    return round(accuracy, 2), round(fluency, 2)


def score_total(accuracy: float, fluency: float, expected_ph: list[str], actual_ph: list[str], whisper_words: list[dict], confidence_proxy: float) -> dict:
    # Phoneme score (20%)
    max_ph = max(len(expected_ph), len(actual_ph), 1)
    mismatches = sum(1 for i in range(min(len(expected_ph), len(actual_ph))) if expected_ph[i] != actual_ph[i])
    mismatches += abs(len(expected_ph) - len(actual_ph))
    phoneme_score = max(0.0, 1.0 - (mismatches / max_ph)) * 100.0

    # Rhythm Score (based on word timing regularity and pauses)
    pause_penalty = 0.0
    timing_variance = 0.0
    if len(whisper_words) > 1:
        gaps = []
        for i in range(len(whisper_words) - 1):
            gap = whisper_words[i+1]["start"] - whisper_words[i]["end"]
            gaps.append(gap)
            if gap > 0.6: 
                pause_penalty += 8.0
        
        if gaps:
            timing_variance = float(np.var(gaps))
    
    rhythm_score = max(0.0, 100.0 - pause_penalty - (timing_variance * 50))

    # Overall Total
    total = (0.45 * accuracy) + (0.20 * phoneme_score) + (0.20 * fluency) + (0.15 * rhythm_score)
    
    return {
        "overall": round(max(0.0, min(100.0, total)), 2),
        "phoneme": round(phoneme_score, 2),
        "fluency": round(fluency, 2),
        "rhythm": round(rhythm_score, 2)
    }


def build_phoneme_feedback(language_id: str, expected_ph: list[str], actual_ph: list[str]) -> dict:
    missing = []
    for p in expected_ph:
        if p not in actual_ph:
            missing.append(p)
    missing = missing[:8]

    tips_map = {
        "th": "Place your tongue lightly between your teeth and push air out for 'th'.",
        "r": "Keep your tongue bunched and avoid tapping the roof of your mouth for 'r'.",
        "l": "Touch your tongue tip behind upper teeth for 'l'.",
        "w": "Round your lips and start smoothly for 'w'.",
        "rr": "Try quick repeated 't' sounds to build the trill for Spanish 'rr'.",
        "ch": "Keep airflow unvoiced and tongue high for German 'ch'.",
        "sch": "German 'sch' is like 'sh' with rounded lips.",
    }
    tips = []
    for p in missing:
        if p in tips_map:
            tips.append({"phoneme": p, "tip": tips_map[p]})
    return {"missing": missing, "tips": tips}


def transcribe_audio(audio_path: str, language_id: str) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"text": "", "demo": True, "words": []}

    try:
        client = OpenAI(api_key=api_key)
        with open(audio_path, "rb") as f:
            # Using verbose_json to get word-level timestamps and confidence
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language=_lang_to_whisper_code(language_id),
                response_format="verbose_json",
                timestamp_granularities=["word"]
            )
        
        text = getattr(response, "text", "").strip()
        words = getattr(response, "words", [])
        
        # avg_logprob is a proxy for transcription confidence
        # It's usually a negative value; higher (closer to 0) is better.
        avg_logprob = getattr(response, "avg_logprob", -1.0)
        # Convert to 0-1 scale (roughly)
        confidence_proxy = min(1.0, max(0.0, (avg_logprob + 3.0) / 3.0))

        # Convert words objects to dictionaries for JSON serialization
        formatted_words = []
        for w in words:
            # Check if probability is available (Whisper API sometimes provides it in tokens/logprobs)
            # but in verbose_json it's not always per word. We'll capture it if it is.
            prob = getattr(w, "probability", 1.0) # Default to 1.0 if not found
            
            formatted_words.append({
                "word": w.word,
                "start": w.start,
                "end": w.end,
                "probability": prob
            })
            
        return {
            "text": text, 
            "demo": False, 
            "words": formatted_words,
            "confidence_proxy": confidence_proxy
        }
    except Exception:
        logger.exception("transcribe_audio failed")
        return {"text": "", "demo": True, "words": []}


def get_ai_feedback(expected: str, transcript: str, accuracy: float, fluency: float, pause_score: float, confidence_score: float, language_id: str = "en-US") -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "Great effort! Focus on matching the expected sentence more closely."

    lang_name = "English"
    if language_id == "de-DE": lang_name = "German"
    elif language_id == "es-ES": lang_name = "Spanish"

    try:
        client = OpenAI(api_key=api_key)
        prompt = f"""
        You are a professional pronunciation coach for {lang_name}. 
        User tried to say: "{expected}"
        Actually said: "{transcript}"
        Accuracy: {accuracy}% (matching words)
        Fluency: {fluency}% (pacing/completion)
        Pause Score: {pause_score}% (100 is no awkward pauses)
        Confidence/Clarity: {confidence_score}%

        Provide 2-3 specific sentences of feedback in {lang_name}. 
        - If the pause score is low, mention specific gaps. 
        - Mention any mispronounced phonemes or words. 
        - Be honest: if it was poor, say why so they can improve.
        - Do not give generic praise if the scores are low.
        """
        result = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": f"You are a friendly but firm {lang_name} pronunciation coach."},
                      {"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return (result.choices[0].message.content or "").strip()
    except Exception:
        return "Good job! Keep practicing to improve your clarity and pace."


def smtp_configured() -> bool:
    load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"), override=True)
    host = os.environ.get("SMTP_HOST") or ""
    from_email = os.environ.get("SMTP_FROM") or ""
    user = os.environ.get("SMTP_USER") or ""
    return bool(host and (from_email or user))


def smtp_missing_fields() -> list[str]:
    load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"), override=True)
    missing: list[str] = []
    if not (os.environ.get("SMTP_HOST") or "").strip():
        missing.append("SMTP_HOST")
    if not (os.environ.get("SMTP_PORT") or "").strip():
        missing.append("SMTP_PORT")
    if not (os.environ.get("SMTP_USER") or "").strip():
        missing.append("SMTP_USER")
    if not (os.environ.get("SMTP_PASS") or "").strip():
        missing.append("SMTP_PASS")
    return missing


def send_email(to_email: str, subject: str, body_text: str) -> bool:
    load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"), override=True)
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT") or "587")
    user = os.environ.get("SMTP_USER") or ""
    password = os.environ.get("SMTP_PASS") or ""
    from_email = os.environ.get("SMTP_FROM") or user
    use_tls = (os.environ.get("SMTP_TLS") or "true").lower() in {"1", "true", "yes"}

    if not host or not from_email:
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(body_text)

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            if use_tls:
                server.starttls()
            if user and password:
                server.login(user, password)
            server.send_message(msg)
        return True
    except Exception:
        return False


def login_alerts_enabled() -> bool:
    if not smtp_configured():
        return False
    flag = (os.environ.get("LOGIN_ALERT_EMAILS") or "true").strip().lower()
    return flag in {"1", "true", "yes"}


def _client_ip() -> str:
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return forwarded or (request.remote_addr or "unknown")


def send_login_alert_email(to_email: str) -> bool:
    when = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    ip = _client_ip()
    ua = (request.headers.get("User-Agent") or "").strip()
    ua_short = ua[:220] + ("…" if len(ua) > 220 else "")

    subject = "New login to your ConverseAI account"
    body = (
        "A new login was detected for your ConverseAI account.\n\n"
        f"Time: {when}\n"
        f"IP: {ip}\n"
        f"Device: {ua_short or 'unknown'}\n\n"
        "If this was you, no action is required.\n"
        "If you do not recognize this activity, please change your password immediately (feature coming soon) "
        "and contact the administrator.\n"
    )
    return send_email(to_email, subject, body)


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.register_blueprint(mouth_bp)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me")
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = False
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    oauth = OAuth(app)

    def demo_mode() -> bool:
        load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"), override=True)
        return (os.environ.get("DEMO_MODE") or "").strip().lower() in {"1", "true", "yes"}

    def db_safe(fn, fallback):
        try:
            if not getattr(g, "db", None):
                return fallback
            return fn()
        except Exception:
            logger.exception("db operation failed")
            return fallback

    def google_config() -> tuple[str, str]:
        load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"), override=True)
        cid = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
        csec = (os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip()
        return cid, csec

    def ensure_google_oauth_registered() -> bool:
        cid, csec = google_config()
        if not (cid and csec):
            return False

        public_base = (os.environ.get("PUBLIC_BASE_URL") or "").strip()
        app_env = (os.environ.get("APP_ENV") or "").strip().lower()
        if app_env != "production" and (public_base.startswith("http://") or not public_base):
            os.environ.setdefault("AUTHLIB_INSECURE_TRANSPORT", "1")

        if getattr(oauth, "google", None) is None:
            oauth.register(
                name="google",
                client_id=cid,
                client_secret=csec,
                server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                client_kwargs={"scope": "openid email profile"},
            )
        return True

    @app.before_request
    def before_request() -> None:
        try:
            g.db = sqlite3.connect(DB_PATH)
            g.db.row_factory = sqlite3.Row
        except Exception:
            logger.exception("db connect failed")
            g.db = None

    @app.get("/@vite/client")
    def vite_client_stub():
        return Response("", mimetype="application/javascript")

    @app.get("/@react-refresh")
    def react_refresh_stub():
        return Response("", mimetype="application/javascript")

    @app.get("/favicon.ico")
    def favicon_stub():
        return Response("", status=204)

    @app.teardown_request
    def teardown_request(_exc) -> None:
        db = getattr(g, "db", None)
        if db is not None:
            try:
                db.close()
            except Exception:
                logger.exception("db close failed")

    @app.errorhandler(413)
    def too_large(_e):
        flash("Upload too large. Please upload a smaller file (max 2MB).", "error")
        return redirect(url_for("practice"))

    @app.errorhandler(Exception)
    def unhandled_error(e):
        logger.exception("unhandled error")
        try:
            user_id = int(session.get("user_id") or 0)
        except Exception:
            user_id = 0

        if user_id:
            try:
                user = g.db.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,)).fetchone() if g.db else None
                profile = (
                    g.db.execute(
                        "SELECT user_id, photo_filename, selected_language FROM profiles WHERE user_id = ?",
                        (user_id,),
                    ).fetchone()
                    if g.db
                    else None
                )
                return (
                    render_template(
                        "error.html",
                        user=user,
                        profile=profile,
                        message="Something went wrong. Please try again.",
                    ),
                    200,
                )
            except Exception:
                logger.exception("error handler render failed")
                return redirect(url_for("dashboard"))

        return (
            render_template("error.html", user=None, profile=None, message="Something went wrong. Please try again."),
            200,
        )

    def init_db() -> None:
        with sqlite3.connect(DB_PATH) as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash BLOB NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS practice_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    sentence TEXT NOT NULL,
                    score REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS streaks (
                    user_id INTEGER PRIMARY KEY,
                    current_streak INTEGER NOT NULL,
                    last_practice_date TEXT,
                    points INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id INTEGER PRIMARY KEY,
                    photo_filename TEXT,
                    selected_language TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS video_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    sentences TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS sentences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    language TEXT NOT NULL,
                    text TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    language TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    sample_phrase TEXT
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS email_verifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    used_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS language_access (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    language_id TEXT NOT NULL,
                    price_inr INTEGER NOT NULL,
                    purchased_at TEXT NOT NULL,
                    UNIQUE(user_id, language_id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )

            def add_column_if_missing(table: str, column: str, column_def: str) -> None:
                cols = [r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()]
                if column not in cols:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")

            add_column_if_missing("learning_videos", "sample_phrase", "TEXT")
            add_column_if_missing("users", "is_email_verified", "INTEGER NOT NULL DEFAULT 0")
            add_column_if_missing("users", "email_verified_at", "TEXT")
            add_column_if_missing("practice_sessions", "language", "TEXT")
            add_column_if_missing("practice_sessions", "transcript", "TEXT")
            add_column_if_missing("practice_sessions", "feedback_json", "TEXT")
            add_column_if_missing("practice_sessions", "points", "INTEGER DEFAULT 0")
            add_column_if_missing("streaks", "points", "INTEGER NOT NULL DEFAULT 0")

            if db.execute("SELECT COUNT(*) FROM sentences").fetchone()[0] == 0:
                seed = [
                    ("en-US", "Thank you for your time. I look forward to working with you."),
                    ("en-GB", "Could you please confirm the meeting schedule for next week?"),
                    ("ja-JP", "はじめまして。どうぞよろしくお願いします。"),
                    ("de-DE", "Vielen Dank. Ich freue mich auf die Zusammenarbeit."),
                    ("es-ES", "Muchas gracias. Espero trabajar contigo pronto."),
                ]
                db.executemany("INSERT INTO sentences (language, text) VALUES (?, ?)", seed)

            if db.execute("SELECT COUNT(*) FROM learning_videos WHERE language = 'en-US' AND sample_phrase IS NULL").fetchone()[0] > 0:
                # Update existing US English levels with phrases
                phrases = {
                    "Level 1 - US Pronunciation": "Thank you for your time. I look forward to working with you.",
                    "Level 2 - US Pronunciation": "Could you please confirm the meeting schedule for next week?",
                    "Level 3 - US Pronunciation": "Proper pronunciation prevents poor performance in professional settings.",
                    "Level 4 - US Pronunciation": "The innovative technology simplifies the complex manufacturing process.",
                    "Level 5 - US Pronunciation": "Extraordinary achievements require consistent effort and unwavering dedication.",
                    "Level 6 - US Pronunciation": "Understanding subtle nuances in intonation helps master the American accent."
                }
                for title, phrase in phrases.items():
                    db.execute("UPDATE learning_videos SET sample_phrase = ? WHERE title = ?", (phrase, title))
                db.commit()

            if db.execute("SELECT COUNT(*) FROM learning_videos WHERE language = 'en-US' AND title LIKE 'Level %'").fetchone()[0] == 0:
                # Remove default en-US video if it exists
                db.execute("DELETE FROM learning_videos WHERE language = 'en-US' AND title = 'English TH sound (guide)'")
                
                vids = [
                    ("en-US", "Level 1 - US Pronunciation", "https://youtube.com/playlist?list=PLKWcPfZiScgDfhVMerPPR2YqOP1XOeBTm&si=4BBfFAn2IFKAoRPy", "Thank you for your time. I look forward to working with you."),
                    ("en-US", "Level 2 - US Pronunciation", "https://youtube.com/playlist?list=PLKWcPfZiScgDf5Wc_Y5JZS17taUi2WWgx&si=CddChK4ALcBpMA7L", "Could you please confirm the meeting schedule for next week?"),
                    ("en-US", "Level 3 - US Pronunciation", "https://youtube.com/playlist?list=PLKWcPfZiScgDimnOyDv32VnEVFqhAItAy&si=v3ZpJ8iAhMcsYCOg", "Proper pronunciation prevents poor performance in professional settings."),
                    ("en-US", "Level 4 - US Pronunciation", "https://youtube.com/playlist?list=PLKWcPfZiScgDJkl2T7xAews-GoJMc4I7j&si=TNLKk8PBKSQTIzqi", "The innovative technology simplifies the complex manufacturing process."),
                    ("en-US", "Level 5 - US Pronunciation", "https://youtube.com/playlist?list=PLKWcPfZiScgBACqEFo5TuhJWAReRNNTc8&si=o0TIHA4sIQVU_xQi", "Extraordinary achievements require consistent effort and unwavering dedication."),
                    ("en-US", "Level 6 - US Pronunciation", "https://youtube.com/playlist?list=PLKWcPfZiScgAutnWOSAh2AH026L9w8c18&si=NQgnwgFjUxK8hfqe", "Understanding subtle nuances in intonation helps master the American accent."),
                ]
                db.executemany("INSERT INTO learning_videos (language, title, url, sample_phrase) VALUES (?, ?, ?, ?)", vids)
                db.commit()

            if db.execute("SELECT COUNT(*) FROM learning_videos WHERE language = 'en-GB'").fetchone()[0] <= 10:
                # Add more videos from the British English Pronunciation playlist
                more_vids = [
                    ("en-GB", "Level 11 - Sentence Stress & Rhythm", "https://www.youtube.com/watch?v=0S_Z_Y_S_S_&list=PLzMXToX8KzqgABZmT_LcYdED98Ixuc2Fx&index=11", "The rhythm of English depends on the stressed syllables."),
                    ("en-GB", "Level 12 - Connected Speech: Linking", "https://www.youtube.com/watch?v=0S_Z_Y_S_S_&list=PLzMXToX8KzqgABZmT_LcYdED98Ixuc2Fx&index=12", "I'm going to eat an orange for my lunch."),
                    ("en-GB", "Level 13 - Intonation: Rising & Falling", "https://www.youtube.com/watch?v=0S_Z_Y_S_S_&list=PLzMXToX8KzqgABZmT_LcYdED98Ixuc2Fx&index=13", "Are you coming to the party tonight?"),
                    ("en-GB", "Level 14 - Pronouncing 'ED' endings", "https://www.youtube.com/watch?v=0S_Z_Y_S_S_&list=PLzMXToX8KzqgABZmT_LcYdED98Ixuc2Fx&index=14", "He walked to the park and played with his friends."),
                    ("en-GB", "Level 15 - Silent Letters in English", "https://www.youtube.com/watch?v=0S_Z_Y_S_S_&list=PLzMXToX8KzqgABZmT_LcYdED98Ixuc2Fx&index=15", "The knight knew how to write a long psalm."),
                ]
                for v in more_vids:
                    exists = db.execute("SELECT 1 FROM learning_videos WHERE title = ?", (v[1],)).fetchone()
                    if not exists:
                        db.execute("INSERT INTO learning_videos (language, title, url, sample_phrase) VALUES (?, ?, ?, ?)", v)
                db.commit()

            if db.execute("SELECT COUNT(*) FROM learning_videos WHERE language = 'de-DE' AND title LIKE 'Level %'").fetchone()[0] == 0:
                # Remove default de-DE video if it exists
                db.execute("DELETE FROM learning_videos WHERE language = 'de-DE' AND title = 'German CH sound explained'")
                
                vids = [
                    ("de-DE", "Level 1 - German Basics", "https://youtu.be/MOtqMNKs0Jw?si=pgXYlVUqrC2l5N1k", "Guten Tag, wie geht es Ihnen heute?", "[ˈɡuːtn̩ taːk viː ɡeːt ɛs iːnən ˈhɔʏtə]"),
                    ("de-DE", "Level 2 - Essential Phrases", "https://youtu.be/iB_sassbnOw?si=AIPZgVcU-8AMri0L", "Ich möchte gerne ein Glas Wasser bestellen.", "[ɪç ˈmœçtə ˈɡɛrnə aɪn ɡlaːs ˈvasɐ bəˈʃtɛlən]"),
                    ("de-DE", "Level 3 - Pronunciation Tips", "https://youtu.be/5aNdCmSruYA?si=mshqlRgeyz9lllxt", "Die Aussprache ist der Schlüssel zum Erfolg.", "[diː ˈaʊsˌpʁaːxə ɪst deːɐ ˈʃlʏsl̩ t͡sʊm ɛɐ̯ˈfɔlk]"),
                    ("de-DE", "Level 4 - Advanced Grammar", "https://youtu.be/-WHUtw33SQU?si=rFnCe7tOyoau8y2Z", "Könnten Sie mir bitte den Weg zum Bahnhof zeigen?", "[ˈkœntn̩ ziː miːɐ̯ ˈbɪtə deːn veːk t͡sʊm ˈbaːnˌhoːf ˈt͡saɪɡn̩]"),
                    ("de-DE", "Level 5 - Common Mistakes", "https://youtu.be/u1gsES1gIr8?si=yByu2fzUpWZPsNBC", "Es ist wichtig, aus seinen Fehlern zu lernen.", "[ɛs ɪst ˈvɪçtɪç aʊs ˈzaɪnən ˈfeːlɐn t͡suː ˈlɛrnən]"),
                    ("de-DE", "Level 6 - Conversational German", "https://youtu.be/y51_ftySlQo?si=kscR3TrnBc5rxgDk", "Wir haben uns lange nicht mehr gesehen.", "[viːɐ̯ ˈhaːbn̩ ʊns ˈlaŋə nɪçt meːɐ̯ ɡəˈzeːən]"),
                    ("de-DE", "Level 7 - Fluent Speaking", "https://youtu.be/fWrCYzpXWfQ?si=YxNlwPzxa0Ltcnci", "Ich freue mich sehr auf unser nächstes Treffen.", "[ɪç ˈfʁɔʏə mɪç zeːɐ̯ aʊf ˈʊnzɐ ˈnɛːçstəs ˈtʁɛfn̩]"),
                    ("de-DE", "Level 8 - Master the Accent", "https://youtu.be/T09k-gSi76k?si=BjHssX_dzmknKtJ7", "Übung macht den Meister beim Sprachenlernen.", "[ˈyːbʊŋ maxt deːn ˈmaɪstɐ baɪm ˈʃpʁaːxn̩ˌlɛrnən]"),
                    ("de-DE", "Level 9 - Word: Eichhörnchen", "https://www.youtube.com/watch?v=0S_Z_Y_S_S_", "Eichhörnchen", "[ˈaɪçˌhœrnçən]"),
                    ("de-DE", "Level 10 - Word: Streichholzschächtelchen", "https://www.youtube.com/watch?v=0S_Z_Y_S_S_", "Streichholzschächtelchen", "[ˈʃtʁaɪçhɔlt͡sˌʃɛçtl̩çən]"),
                ]
                db.executemany("INSERT INTO learning_videos (language, title, url, sample_phrase, ipa_guide) VALUES (?, ?, ?, ?, ?)", vids)
                db.commit()

            if db.execute("SELECT COUNT(*) FROM learning_videos").fetchone()[0] == 0:
                vids = [
                    ("en-US", "English TH sound (guide)", "https://www.youtube.com/watch?v=J6JcK8qC6xk", "The quick brown fox jumps over the lazy dog."),
                    ("ja-JP", "Japanese pronunciation tips", "https://www.youtube.com/watch?v=7Yl1WnO_KtQ", "はじめまして。どうぞよろしくお願いします。"),
                    ("es-ES", "Spanish rolled R practice", "https://www.youtube.com/watch?v=3wqO7dLrPQQ", "Muchas_gracias._Espero_trabajar_contigo_pronto."),
                ]
                db.executemany("INSERT INTO learning_videos (language, title, url, sample_phrase) VALUES (?, ?, ?, ?)", vids)
                db.commit()

    init_db()

    def login_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login"))
            return fn(*args, **kwargs)

        return wrapper

    def get_user(user_id: int):
        return g.db.execute(
            "SELECT id, name, email, is_email_verified FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    def get_user_by_email(email: str):
        return g.db.execute(
            "SELECT id, name, email, password_hash, is_email_verified FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    def get_google_user(email: str):
        return g.db.execute(
            "SELECT id, name, email, is_email_verified FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    def upsert_google_user(name: str, email: str) -> int:
        existing = get_google_user(email)
        now = datetime.utcnow().isoformat()
        if existing is None:
            cur = g.db.execute(
                "INSERT INTO users (name, email, password_hash, created_at, is_email_verified, email_verified_at) VALUES (?, ?, ?, ?, ?, ?)",
                (name, email, bcrypt.hashpw(secrets.token_bytes(24), bcrypt.gensalt()), now, 1, now),
            )
            g.db.commit()
            user_id = int(cur.lastrowid)
            ensure_streak_row(user_id)
            return user_id

        if int(existing["is_email_verified"] or 0) != 1:
            g.db.execute(
                "UPDATE users SET is_email_verified = 1, email_verified_at = ? WHERE id = ?",
                (now, int(existing["id"])),
            )
            g.db.commit()
        return int(existing["id"])

    def create_email_verification(user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        expires = now + timedelta(hours=24)
        g.db.execute(
            "INSERT INTO email_verifications (user_id, token, expires_at, used_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, token, expires.isoformat(), None, now.isoformat()),
        )
        g.db.commit()
        return token

    def send_verification_email(to_email: str, token: str) -> bool:
        base = os.environ.get("PUBLIC_BASE_URL") or request.url_root.rstrip("/")
        link = f"{base}{url_for('verify_email')}?token={token}"
        subject = "Verify your ConverseAI account"
        body = (
            "Welcome to ConverseAI.\n\n"
            "Please verify your email address to activate your account:\n"
            f"{link}\n\n"
            "This link expires in 24 hours.\n"
        )
        return send_email(to_email, subject, body)

    def ensure_streak_row(user_id: int) -> None:
        row = g.db.execute("SELECT user_id FROM streaks WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            g.db.execute(
                "INSERT INTO streaks (user_id, current_streak, last_practice_date, points) VALUES (?, ?, ?, ?)",
                (user_id, 0, None, 0),
            )
            g.db.commit()

    def get_profile(user_id: int):
        return g.db.execute("SELECT user_id, photo_filename, selected_language FROM profiles WHERE user_id = ?", (user_id,)).fetchone()

    def ensure_onboarding(user_id: int):
        profile = get_profile(user_id)
        if profile is None:
            return redirect(url_for("profile"))
        return None

    def ensure_language_selected(user_id: int):
        profile = get_profile(user_id)
        if profile is None:
            return redirect(url_for("profile"))
        selected = (profile["selected_language"] or "").strip()
        allowed = {l["id"] for l in LANGUAGES}
        if selected and selected not in allowed:
            try:
                g.db.execute(
                    "UPDATE profiles SET selected_language = ? WHERE user_id = ?",
                    ("", user_id),
                )
                g.db.commit()
            except Exception:
                pass
            flash("Your previous language is no longer available. Please choose another language.", "error")
            return redirect(url_for("dashboard"))
        if not selected:
            flash("Select a language to start practice.", "error")
            return redirect(url_for("dashboard"))
        return None

    def update_streak_after_practice(user_id: int) -> int:
        ensure_streak_row(user_id)
        row = g.db.execute("SELECT current_streak, last_practice_date FROM streaks WHERE user_id = ?", (user_id,)).fetchone()
        today = date.today()
        last_str = row["last_practice_date"]
        last_date = date.fromisoformat(last_str) if last_str else None

        if last_date == today:
            new_streak = int(row["current_streak"])
        elif last_date == today - timedelta(days=1):
            new_streak = int(row["current_streak"]) + 1
        else:
            new_streak = 1

        g.db.execute(
            "UPDATE streaks SET current_streak = ?, last_practice_date = ? WHERE user_id = ?",
            (new_streak, today.isoformat(), user_id),
        )
        g.db.commit()
        return new_streak

    @app.get("/")
    def login():
        if session.get("user_id"):
            return redirect(url_for("dashboard"))
        google_enabled = ensure_google_oauth_registered()
        return render_template("login.html", google_enabled=google_enabled)

    @app.post("/login")
    def login_post():
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not email or not password:
            flash("Please enter email and password.", "error")
            return redirect(url_for("login"))

        row = get_user_by_email(email)
        if row is None:
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        if not bcrypt.checkpw(password.encode("utf-8"), row["password_hash"]):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        if int(row["is_email_verified"] or 0) != 1:
            token = create_email_verification(int(row["id"]))
            if smtp_configured():
                ok = send_verification_email(email, token)
                if ok:
                    flash("Check your email for a verification link to activate your account.", "success")
                else:
                    flash("Email service failed. Configure SMTP settings and try again.", "error")
            else:
                flash("Email verification is enabled but SMTP is not configured.", "error")
            return redirect(url_for("resend_verification", email=email))

        session["user_id"] = int(row["id"])
        ensure_streak_row(session["user_id"])
        onboarding = ensure_onboarding(session["user_id"])

        if login_alerts_enabled():
            try:
                send_login_alert_email(email)
            except Exception:
                pass

        return onboarding or redirect(url_for("dashboard"))

    @app.get("/signup")
    def signup():
        if session.get("user_id"):
            return redirect(url_for("dashboard"))
        google_enabled = ensure_google_oauth_registered()
        return render_template("signup.html", google_enabled=google_enabled)

    @app.get("/auth/google")
    def auth_google():
        if not ensure_google_oauth_registered():
            flash("Google sign-in is not configured.", "error")
            return redirect(url_for("login"))
        redirect_uri = request.url_root.rstrip("/") + url_for("auth_google_callback")
        try:
            return oauth.google.authorize_redirect(redirect_uri)
        except Exception:
            flash("Google sign-in could not start. Check GOOGLE_CLIENT_ID/SECRET and redirect URL.", "error")
            return redirect(url_for("login"))

    @app.get("/auth/google/callback")
    def auth_google_callback():
        if not ensure_google_oauth_registered():
            flash("Google sign-in is not configured.", "error")
            return redirect(url_for("login"))
        try:
            token = oauth.google.authorize_access_token()
        except Exception:
            exc = sys.exc_info()[1]
            exc_name = exc.__class__.__name__ if exc else ""
            if exc_name == "MismatchingStateError":
                flash(
                    "Google sign-in failed (session mismatch). Use one host only (localhost OR 127.0.0.1) and open the site in a normal browser tab (not an embedded preview). Then try again.",
                    "error",
                )
                return redirect(url_for("login"))
            flash(
                "Google sign-in failed. Use the same host (localhost or 127.0.0.1) for login and callback, and ensure the redirect URI matches.",
                "error",
            )
            return redirect(url_for("login"))
        userinfo = token.get("userinfo") or {}
        email = (userinfo.get("email") or "").strip().lower()
        name = (userinfo.get("name") or "").strip() or "User"
        if not email:
            flash("Google sign-in failed. Missing email.", "error")
            return redirect(url_for("login"))

        user_id = upsert_google_user(name=name, email=email)
        session["user_id"] = user_id
        onboarding = ensure_onboarding(user_id)
        return onboarding or redirect(url_for("dashboard"))

    @app.post("/signup")
    def signup_post():
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not name or not email or len(password) < 8:
            flash("Enter name, valid email, and a password (min 8 chars).", "error")
            return redirect(url_for("signup"))

        existing = g.db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing is not None:
            flash("Email already registered. Please login.", "error")
            return redirect(url_for("login"))

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        now = datetime.utcnow().isoformat()
        cur = g.db.execute(
            "INSERT INTO users (name, email, password_hash, created_at, is_email_verified) VALUES (?, ?, ?, ?, ?)",
            (name, email, password_hash, now, 0),
        )
        g.db.commit()
        user_id = int(cur.lastrowid)
        ensure_streak_row(user_id)
        token = create_email_verification(user_id)
        if smtp_configured():
            ok = send_verification_email(email, token)
            if ok:
                flash("Account created. Check your email to verify and login.", "success")
            else:
                flash("Account created, but email sending failed. Configure SMTP and resend verification.", "error")
        else:
            missing = ", ".join(smtp_missing_fields())
            flash(f"Account created. SMTP not configured ({missing}). Verification email was not sent.", "error")
        return redirect(url_for("resend_verification", email=email))

    @app.get("/verify-email")
    def verify_email():
        token = (request.args.get("token") or "").strip()
        if not token:
            flash("Invalid verification link.", "error")
            return redirect(url_for("login"))

        row = g.db.execute(
            "SELECT id, user_id, expires_at, used_at FROM email_verifications WHERE token = ?",
            (token,),
        ).fetchone()
        if row is None:
            flash("Invalid verification link.", "error")
            return redirect(url_for("login"))

        if row["used_at"]:
            flash("Email already verified. Please login.", "success")
            return redirect(url_for("login"))

        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.utcnow() > expires_at:
            flash("Verification link expired. Please request a new one.", "error")
            return redirect(url_for("resend_verification"))

        now = datetime.utcnow().isoformat()
        g.db.execute("UPDATE email_verifications SET used_at = ? WHERE id = ?", (now, int(row["id"])))
        g.db.execute(
            "UPDATE users SET is_email_verified = 1, email_verified_at = ? WHERE id = ?",
            (now, int(row["user_id"])),
        )
        g.db.commit()
        flash("Email verified. You can login now.", "success")
        return redirect(url_for("login"))

    @app.get("/resend-verification")
    def resend_verification():
        email = (request.args.get("email") or "").strip().lower()
        return render_template("resend_verification.html", email=email)

    @app.post("/resend-verification")
    def resend_verification_post():
        email = (request.form.get("email") or "").strip().lower()
        if not email:
            flash("Enter your email.", "error")
            return redirect(url_for("resend_verification"))

        row = get_user_by_email(email)
        if row is None:
            flash("If the email exists, a verification link will be sent.", "success")
            return redirect(url_for("resend_verification"))

        if int(row["is_email_verified"] or 0) == 1:
            flash("Email already verified. Please login.", "success")
            return redirect(url_for("login"))

        token = create_email_verification(int(row["id"]))
        if smtp_configured():
            ok = send_verification_email(email, token)
            if ok:
                flash("Verification email sent. Please check your inbox.", "success")
            else:
                flash("Email service failed. Configure SMTP settings and try again.", "error")
        else:
            missing = ", ".join(smtp_missing_fields())
            flash(f"SMTP not configured ({missing}). Set SMTP settings to send verification email.", "error")
        return redirect(url_for("resend_verification"))

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        user = get_user(int(session["user_id"]))
        onboarding = ensure_onboarding(int(session["user_id"]))
        if onboarding:
            return onboarding
        user_id = int(session["user_id"])
        profile_row = get_profile(user_id)
        streak = g.db.execute(
            "SELECT current_streak, last_practice_date, points FROM streaks WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        last = g.db.execute(
            "SELECT score, created_at FROM practice_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()

        streak_days = int(streak["current_streak"]) if streak else 0
        points = int(streak["points"]) if streak else 0
        last_score = float(last["score"]) if last else None

        msg = "Start your first practice today." if streak_days == 0 else f"You're on a {streak_days}-day streak!"
        return render_template(
            "dashboard.html",
            user=user,
            profile=profile_row,
            languages=LANGUAGES,
            streak_days=streak_days,
            points=points,
            last_score=last_score,
            motivational=msg,
        )

    @app.get("/profile")
    @login_required
    def profile():
        user = get_user(int(session["user_id"]))
        profile_row = get_profile(int(session["user_id"]))
        return render_template("profile.html", user=user, profile=profile_row)

    @app.post("/profile")
    @login_required
    def profile_post():
        user_id = int(session["user_id"])
        photo = request.files.get("photo")
        photo_filename = None
        if photo and photo.filename:
            name = secure_filename(photo.filename)
            ext = os.path.splitext(name)[1].lower()
            if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
                flash("Upload a PNG/JPG/WEBP image.", "error")
                return redirect(url_for("profile"))
            photo_filename = f"{uuid.uuid4().hex}{ext}"
            photo.save(os.path.join(UPLOAD_DIR, photo_filename))

        existing = get_profile(user_id)
        updated_at = datetime.utcnow().isoformat()
        if existing is None:
            g.db.execute(
                "INSERT INTO profiles (user_id, photo_filename, selected_language, updated_at) VALUES (?, ?, ?, ?)",
                (user_id, photo_filename, "", updated_at),
            )
        else:
            if photo_filename:
                g.db.execute(
                    "UPDATE profiles SET photo_filename = ?, updated_at = ? WHERE user_id = ?",
                    (photo_filename, updated_at, user_id),
                )
        g.db.commit()
        selected = (existing["selected_language"] if existing else "") or ""
        return redirect(url_for("profile" if selected else "language"))

    @app.post("/profile/remove-photo")
    @login_required
    def profile_remove_photo():
        user_id = int(session["user_id"])
        row = g.db.execute("SELECT photo_filename FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
        if row and row["photo_filename"]:
            old_name = str(row["photo_filename"])
            g.db.execute(
                "UPDATE profiles SET photo_filename = ?, updated_at = ? WHERE user_id = ?",
                (None, datetime.utcnow().isoformat(), user_id),
            )
            g.db.commit()
            old_path = os.path.join(UPLOAD_DIR, old_name)
            try:
                if os.path.exists(old_path):
                    os.remove(old_path)
            except Exception:
                pass
        flash("Profile photo removed.", "success")
        return redirect(url_for("profile"))

    @app.get("/language")
    @login_required
    def language():
        user_id = int(session["user_id"])
        profile_row = get_profile(user_id)
        selected = profile_row["selected_language"] if profile_row else ""
        return render_template("language.html", languages=LANGUAGES, selected_language=selected)

    @app.post("/language")
    @login_required
    def language_post():
        user_id = int(session["user_id"])
        language_id = (request.form.get("language") or "").strip()
        if language_id not in {l["id"] for l in LANGUAGES}:
            flash("Select a valid language.", "error")
            return redirect(url_for("language"))

        updated_at = datetime.utcnow().isoformat()
        if get_profile(user_id) is None:
            g.db.execute(
                "INSERT INTO profiles (user_id, photo_filename, selected_language, updated_at) VALUES (?, ?, ?, ?)",
                (user_id, None, language_id, updated_at),
            )
        else:
            g.db.execute(
                "UPDATE profiles SET selected_language = ?, updated_at = ? WHERE user_id = ?",
                (language_id, updated_at, user_id),
            )
        g.db.commit()
        if language_id == "de-DE":
            return redirect(url_for("german_coach"))
        return redirect(url_for("dashboard"))

    @app.post("/set-language")
    @login_required
    def set_language():
        user_id = int(session["user_id"])
        language_id = (request.form.get("language") or "").strip()
        if language_id not in {l["id"] for l in LANGUAGES}:
            flash("Select a valid language.", "error")
            return redirect(url_for("dashboard"))

        updated_at = datetime.utcnow().isoformat()
        if get_profile(user_id) is None:
            g.db.execute(
                "INSERT INTO profiles (user_id, photo_filename, selected_language, updated_at) VALUES (?, ?, ?, ?)",
                (user_id, None, language_id, updated_at),
            )
        else:
            g.db.execute(
                "UPDATE profiles SET selected_language = ?, updated_at = ? WHERE user_id = ?",
                (language_id, updated_at, user_id),
            )
        g.db.commit()
        if language_id == "de-DE":
            return redirect(url_for("german_coach"))
        return redirect(url_for("learn"))

    @app.get("/practice")
    @login_required
    def practice():
        user_id = int(session["user_id"])
        gate = ensure_language_selected(user_id)
        if gate:
            return gate

        profile_row = get_profile(user_id)
        language_id = profile_row["selected_language"]
        
        # Pick a random sample phrase from learning_videos for the selected language
        row = g.db.execute(
            "SELECT sample_phrase, ipa_guide FROM learning_videos WHERE language = ? AND sample_phrase IS NOT NULL ORDER BY RANDOM() LIMIT 1",
            (language_id,),
        ).fetchone()
        
        # Fallback to sentences table if no video-based phrases found
        if not row:
            row = g.db.execute(
                "SELECT text as sample_phrase, NULL as ipa_guide FROM sentences WHERE language = ? ORDER BY RANDOM() LIMIT 1",
                (language_id,),
            ).fetchone()
            
        sentence = {
            "text": row["sample_phrase"] if row else "Welcome to ConverseAI. Let's practice!",
            "ipa": row["ipa_guide"] if row else ""
        }
        user = get_user(user_id)
        ui = _get_ui_strings(language_id)
        return render_template("practice.html", user=user, profile=profile_row, language_id=language_id, sentence=sentence, ui=ui)

    @app.post("/upload_audio")
    @login_required
    def upload_audio():
        try:
            user_id = int(session["user_id"])
            gate = ensure_language_selected(user_id)
            if gate:
                return gate

            profile_row = get_profile(user_id)
            language_id = profile_row["selected_language"]
            custom_text = (request.form.get("custom_text") or "").strip()
            expected_text = ""
            if custom_text:
                if len(custom_text) < 3 or len(custom_text) > 300:
                    flash("Type a short sentence (3–300 characters).", "error")
                    return redirect(url_for("practice"))
                expected_text = custom_text
            else:
                sentence_id = int(request.form.get("sentence_id") or "0")
                expected_row = db_safe(
                    lambda: g.db.execute("SELECT id, text FROM sentences WHERE id = ?", (sentence_id,)).fetchone(),
                    None,
                )
                if expected_row is None:
                    flash("Sentence not found. Try again.", "error")
                    return redirect(url_for("practice"))
                expected_text = str(expected_row["text"] or "").strip()
                if not expected_text:
                    flash("Sentence not found. Try again.", "error")
                    return redirect(url_for("practice"))

            spoken_text = (request.form.get("spoken_text") or "").strip()
            audio = request.files.get("audio")
            transcript = ""
            demo = False
            if spoken_text:
                transcript = spoken_text
            else:
                if not audio or not audio.filename:
                    flash("Please record or upload an audio file.", "error")
                    return redirect(url_for("practice"))
                audio_filename = f"{uuid.uuid4().hex}.webm"
                audio_path = os.path.join(UPLOAD_DIR, audio_filename)
                audio.save(audio_path)
                
                # 0. Advanced Phoneme-Level Scoring (torchaudio + wav2vec2)
                adv_result = scorer.get_phoneme_scores(audio_path, expected_text, language_id)
                adv_score = adv_result["final_score"]
                word_feedback = adv_result["word_feedback"]
                
                result = transcribe_audio(audio_path, language_id)
                transcript = result["text"]
                demo = result["demo"]
                whisper_words = result["words"]
                confidence_proxy = result.get("confidence_proxy", 0.5)
                if demo:
                    transcript = expected_text
            
            # 1. Compare words first to get pronunciation quality flags
            word_rows = compare_words(expected_text, transcript, whisper_words, confidence_proxy)
            
            # 2. Calculate accuracy and fluency based on those flags
            accuracy, fluency = score_from_words(expected_text, transcript, word_rows)
            
            # Adjust accuracy to favor the advanced phoneme score if available
            if not demo:
                # adv_score is 0-10, accuracy is 0-100
                accuracy = (accuracy * 0.4) + (adv_score * 10 * 0.6)
            
            expected_ph = pseudo_phonemes(expected_text, language_id)
            actual_ph = pseudo_phonemes(transcript, language_id)
            
            # 3. Detailed Scoring
            scores = score_total(accuracy, fluency, expected_ph, actual_ph, whisper_words, confidence_proxy)
            total = scores["overall"]

            ai_text = get_ai_feedback(expected_text, transcript, accuracy, fluency, scores["rhythm"], scores["phoneme"], language_id)

            phoneme_fb = build_phoneme_feedback(language_id, expected_ph, actual_ph)
            feedback = {
                "demo_stt": demo,
                "accuracy": accuracy,
                "fluency": scores["fluency"],
                "rhythm_score": scores["rhythm"],
                "phoneme_score": scores["phoneme"],
                "confidence": round(total / 100.0, 2), # Used for the ring display
                "ai_feedback": ai_text,
                "phonemes_expected": expected_ph[:120],
                "phonemes_actual": actual_ph[:120],
                "word_rows": word_rows[:80],
                "phoneme_feedback": phoneme_fb,
                "whisper_words": whisper_words,
                "advanced_feedback": word_feedback if not demo else [],
            }

            points_earned = 10
            streak_days = update_streak_after_practice(user_id)
            if streak_days >= 2:
                points_earned += 5

            now = datetime.utcnow().isoformat()
            cur = db_safe(
                lambda: g.db.execute(
                    """
                    INSERT INTO practice_sessions (user_id, sentence, score, created_at, language, transcript, feedback_json, points)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        expected_text,
                        total,
                        now,
                        language_id,
                        transcript,
                        json.dumps(feedback, ensure_ascii=False),
                        points_earned,
                    ),
                ),
                None,
            )
            db_safe(lambda: g.db.commit(), None)
            db_safe(lambda: g.db.execute("UPDATE streaks SET points = points + ? WHERE user_id = ?", (points_earned, user_id)), None)
            db_safe(lambda: g.db.commit(), None)

            session_id = int(cur.lastrowid) if cur is not None else 0
            if not session_id:
                flash("Saved with limited details. Please try again.", "error")
                return redirect(url_for("dashboard"))
            return redirect(url_for("feedback", session_id=session_id))
        except Exception:
            logger.exception("upload_audio failed")
            flash("Upload failed. Please try again.", "error")
            return redirect(url_for("practice"))

    @app.get("/ai-conversation")
    @login_required
    def ai_conversation():
        user_id = int(session["user_id"])
        onboarding = ensure_onboarding(user_id)
        if onboarding:
            return onboarding
        profile_row = get_profile(user_id)
        user = get_user(user_id)
        return render_template("ai_conversation.html", user=user, profile=profile_row, demo=demo_mode())

    @app.post("/ai-conversation/upload")
    @login_required
    def ai_conversation_upload():
        user_id = int(session["user_id"])
        onboarding = ensure_onboarding(user_id)
        if onboarding:
            return onboarding
        profile_row = get_profile(user_id)
        language_id = (profile_row["selected_language"] or "en-US") if profile_row else "en-US"

        audio = request.files.get("audio")
        if not audio or not audio.filename:
            return {"user": "", "ai": "Please try again."}

        audio_filename = f"{uuid.uuid4().hex}.webm"
        audio_path = os.path.join(UPLOAD_DIR, audio_filename)
        try:
            audio.save(audio_path)
        except Exception:
            logger.exception("ai audio save failed")
            return {"user": "", "ai": "Please try again."}

        try:
            if demo_mode():
                user_text = "How are you?"
            else:
                result = transcribe_audio(audio_path, language_id)
                user_text = result["text"]
                demo = result["demo"]
                if demo or not user_text:
                    user_text = "How are you?"
        except Exception:
            logger.exception("ai stt failed")
            user_text = "How are you?"

        replies = [
            "Great! Try speaking a bit slower.",
            "Nice pronunciation! Repeat: 'Thank you for your time.'",
            "Focus on the 'th' sound. Repeat: 'Thanks for the update.'",
            "I'm doing great! Let's practice your pronunciation.",
        ]

        ai_text = replies[0]
        try:
            if not demo_mode() and os.environ.get("OPENAI_API_KEY"):
                client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                result = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a friendly pronunciation coach. Reply in 1-2 sentences and ask the user to repeat a short phrase.",
                        },
                        {"role": "user", "content": user_text},
                    ],
                    temperature=0.7,
                )
                ai_text = (result.choices[0].message.content or "").strip() or ai_text
            else:
                ai_text = replies[secrets.randbelow(len(replies))]
        except Exception:
            logger.exception("ai reply failed")
            ai_text = replies[secrets.randbelow(len(replies))]

        return {"user": user_text, "ai": ai_text}

    @app.post("/ai-conversation/text")
    @login_required
    def ai_conversation_text():
        user_id = int(session["user_id"])
        onboarding = ensure_onboarding(user_id)
        if onboarding:
            return onboarding

        payload = request.get_json(silent=True) or {}
        user_text = str(payload.get("text") or "").strip()
        if not user_text:
            return {"user": "", "ai": "Please try again."}

        replies = [
            "Great! Try speaking a bit slower.",
            "Nice pronunciation! Repeat: 'Thank you for your time.'",
            "Focus on 'th' sound. Repeat: 'Thanks for the update.'",
            "I'm doing great! Let's practice your pronunciation.",
        ]

        ai_text = replies[0]
        try:
            if not demo_mode() and os.environ.get("OPENAI_API_KEY"):
                client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                result = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a friendly pronunciation coach. Reply in 1-2 sentences and ask the user to repeat a short phrase.",
                        },
                        {"role": "user", "content": user_text},
                    ],
                    temperature=0.7,
                )
                ai_text = (result.choices[0].message.content or "").strip() or ai_text
            else:
                ai_text = replies[secrets.randbelow(len(replies))]
        except Exception:
            logger.exception("ai reply failed")
            ai_text = replies[secrets.randbelow(len(replies))]

        return {"user": user_text, "ai": ai_text}

    @app.get("/streaks")
    @login_required
    def streaks():
        user_id = int(session["user_id"])
        onboarding = ensure_onboarding(user_id)
        if onboarding:
            return onboarding
        user = get_user(user_id)
        profile_row = get_profile(user_id)

        daily_scores: list[dict[str, Any]] = []
        if demo_mode():
            streak_days = 3
            points = 120
            today = date.today()
            daily_scores = []
            for i in range(7):
                d = today - timedelta(days=i)
                base = 62 + (i * 3)
                daily_scores.append(
                    {
                        "date": d.isoformat(),
                        "avg_score": min(92, base),
                        "best_score": min(96, base + 5),
                        "tests": 1 if i in {0, 1, 2, 4, 6} else 0,
                    }
                )
            daily_scores = list(reversed(daily_scores))
        else:
            row = db_safe(
                lambda: g.db.execute("SELECT current_streak, points FROM streaks WHERE user_id = ?", (user_id,)).fetchone(),
                None,
            )
            streak_days = int(row["current_streak"]) if row else 0
            points = int(row["points"]) if row else 0
            daily_rows = db_safe(
                lambda: g.db.execute(
                    """
                    SELECT
                      substr(created_at, 1, 10) AS d,
                      AVG(score) AS avg_score,
                      MAX(score) AS best_score,
                      COUNT(*) AS tests
                    FROM practice_sessions
                    WHERE user_id = ?
                    GROUP BY substr(created_at, 1, 10)
                    ORDER BY d DESC
                    LIMIT 7
                    """,
                    (user_id,),
                ).fetchall(),
                [],
            )
            daily_scores = []
            for r in list(reversed(daily_rows or [])):
                daily_scores.append(
                    {
                        "date": str(r["d"] or ""),
                        "avg_score": float(r["avg_score"] or 0),
                        "best_score": float(r["best_score"] or 0),
                        "tests": int(r["tests"] or 0),
                    }
                )

        circles = [i < min(5, streak_days) for i in range(5)]
        words = [
            "You're improving every day!",
            "Consistency beats perfection!",
            "Small steps make big progress.",
            "Your confidence is growing.",
        ]
        return render_template(
            "streaks.html",
            user=user,
            profile=profile_row,
            streak_days=streak_days,
            points=points,
            circles=circles,
            daily_scores=daily_scores,
            motivational=words[secrets.randbelow(len(words))],
            demo=demo_mode(),
        )

    @app.get("/video-test")
    @login_required
    def video_test():
        user_id = int(session["user_id"])
        onboarding = ensure_onboarding(user_id)
        if onboarding:
            return onboarding
        user = get_user(user_id)
        profile_row = get_profile(user_id)

        video_id = request.args.get("video_id") or ""
        expected_phrase = (request.args.get("phrase") or "").strip()
        if not expected_phrase:
            expected_phrase = "The quick brown fox jumps over the lazy dog"
        url = ""
        title = ""
        if video_id:
            row = db_safe(
                lambda: g.db.execute("SELECT title, url FROM learning_videos WHERE id = ?", (int(video_id),)).fetchone(),
                None,
            )
            if row:
                title = row["title"]
                url = row["url"]

        if not url:
            url = ""

        is_youtube = "youtube.com" in url or "youtu.be" in url
        embed_url = _get_youtube_embed_url(url) or url

        return render_template(
            "video_test.html",
            user=user,
            profile=profile_row,
            video_url=url,
            is_youtube=is_youtube,
            embed_url=embed_url,
            title=title,
            expected_phrase=expected_phrase,
            demo=demo_mode(),
        )

    @app.post("/api/sentences")
    @login_required
    def api_sentences():
        data = request.get_json()
        video_url = data.get("video_url")
        if not video_url:
            return {"error": "video_url required"}, 400

        # Check cache
        existing = g.db.execute("SELECT sentences FROM video_cache WHERE url = ?", (video_url,)).fetchone()
        if existing:
            return {"sentences": json.loads(existing["sentences"])}

        # Process video (ffmpeg + whisper)
        temp_audio = os.path.join(UPLOAD_DIR, f"temp_{uuid.uuid4().hex}.wav")
        try:
            # Step 1: Extract audio
            subprocess.run([
                "ffmpeg", "-i", video_url,
                "-vn", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1", temp_audio
            ], check=True, capture_output=True)

            # Step 2: Transcribe with Whisper
            model = whisper.load_model("base")
            result = model.transcribe(temp_audio)
            transcript = result["text"]

            # Step 3: Select sentences with AI
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            prompt = f"""
            You are a pronunciation coach for a language learning app.
            Given a video transcript, select or rewrite exactly 5 sentences that:
            1. Are natural, complete sentences (8–14 words each)
            2. Cover a variety of phoneme patterns from the transcript
            3. Are ordered easy → hard in pronunciation difficulty
            4. Match the accent and topic of the video
            Respond ONLY with a valid JSON array of 5 strings. No extra text.
            
            Transcript: {transcript[:4000]}
            """
            
            ai_res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            sentences_json = json.loads(ai_res.choices[0].message.content)
            sentences = sentences_json.get("sentences", [])
            if not sentences and isinstance(sentences_json, list):
                sentences = sentences_json
            
            if not sentences or len(sentences) < 5:
                # Fallback if AI fails
                sentences = [
                    "This is a great day to practice English.",
                    "The weather is absolutely wonderful for a walk.",
                    "Could you please repeat that more slowly?",
                    "Understanding native speakers takes consistent daily practice.",
                    "Communication is about more than just matching words perfectly."
                ]

            # Cache in DB
            now = datetime.utcnow().isoformat()
            g.db.execute("INSERT INTO video_cache (url, sentences, created_at) VALUES (?, ?, ?)", 
                         (video_url, json.dumps(sentences), now))
            g.db.commit()

            return {"sentences": sentences}
        except Exception as e:
            logger.exception("api_sentences failed")
            # Fallback sentences
            return {"sentences": [
                "Practice makes progress when learning a new language.",
                "Listen closely to the native pronunciation patterns.",
                "Try to match the rhythm and intonation of the speaker.",
                "Repeat each sentence multiple times until it feels natural.",
                "Consistency is the key to mastering any difficult accent."
            ]}
        finally:
            if os.path.exists(temp_audio):
                os.remove(temp_audio)

    @app.get("/feedback/<int:session_id>")
    @login_required
    def feedback(session_id: int):
        user_id = int(session["user_id"])
        row = g.db.execute(
            "SELECT id, sentence, transcript, score, language, created_at, feedback_json, points FROM practice_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if row is None:
            return redirect(url_for("dashboard"))

        user = get_user(user_id)
        profile_row = get_profile(user_id)
        data = json.loads(row["feedback_json"] or "{}")
        return render_template(
            "feedback.html",
            user=user,
            profile=profile_row,
            session=row,
            feedback=data,
            score_10=round(float(row["score"]) / 10.0, 1),
        )

    @app.get("/learn")
    @login_required
    def learn():
        user_id = int(session["user_id"])
        gate = ensure_language_selected(user_id)
        if gate:
            return gate
        profile_row = get_profile(user_id)
        language_id = profile_row["selected_language"]
        rows = g.db.execute(
            "SELECT id, title, url, sample_phrase FROM learning_videos WHERE language = ? ORDER BY id ASC",
            (language_id,),
        ).fetchall()
        
        videos = []
        for r in rows:
            v = dict(r)
            url = v["url"]
            v["embed_url"] = _get_youtube_embed_url(url)
            v["is_youtube"] = bool(v["embed_url"])
            videos.append(v)
            
        user = get_user(user_id)
        return render_template("learn.html", user=user, profile=profile_row, language_id=language_id, videos=videos)

    @app.post("/video-test/analyze")
    @login_required
    def video_test_analyze():
        user_id = int(session["user_id"])
        audio = request.files.get("audio")
        expected_text = request.form.get("expected", "").strip()
        
        if not audio or not expected_text:
            return {"error": "audio and expected text required"}, 400

        audio_filename = f"{uuid.uuid4().hex}.webm"
        audio_path = os.path.join(UPLOAD_DIR, audio_filename)
        audio.save(audio_path)
        
        profile_row = get_profile(user_id)
        language_id = profile_row["selected_language"] if profile_row else "en-US"

        # Advanced Scoring
        adv_result = scorer.get_phoneme_scores(audio_path, expected_text, language_id)
        
        result = transcribe_audio(audio_path, language_id)
        transcript = result["text"]
        whisper_words = result["words"]
        confidence_proxy = result.get("confidence_proxy", 0.5)

        word_rows = compare_words(expected_text, transcript, whisper_words, confidence_proxy)
        accuracy, fluency = score_from_words(expected_text, transcript, word_rows)
        
        expected_ph = pseudo_phonemes(expected_text, language_id)
        actual_ph = pseudo_phonemes(transcript, language_id)
        
        scores = score_total(accuracy, fluency, expected_ph, actual_ph, whisper_words, confidence_proxy)
        
        ai_text = get_ai_feedback(expected_text, transcript, accuracy, fluency, scores["rhythm"], scores["phoneme"], language_id)

        return {
            "score": round(scores["overall"] / 10, 1),
            "confidence": round(scores["overall"], 0),
            "feedback": [ai_text],
            "transcript": transcript,
            "scores": scores
        }

    @app.get("/german-coach")
    @login_required
    def german_coach():
        user_id = int(session["user_id"])
        onboarding = ensure_onboarding(user_id)
        if onboarding:
            return onboarding
        user = get_user(user_id)
        profile_row = get_profile(user_id)
        return render_template("german_coach.html", user=user, profile=profile_row)

    @app.get("/history")
    @login_required
    def history():
        user_id = int(session["user_id"])
        rows = g.db.execute(
            "SELECT id, score, created_at, language FROM practice_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
            (user_id,),
        ).fetchall()
        user = get_user(user_id)
        profile_row = get_profile(user_id)
        return render_template("history.html", user=user, profile=profile_row, sessions=rows)

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)
