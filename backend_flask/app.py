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


def compare_words(expected: str, actual: str) -> list[dict]:
    e = _tokenize_words(expected)
    a = _tokenize_words(actual)
    max_len = max(len(e), len(a))
    out = []
    for i in range(max_len):
        ew = e[i] if i < len(e) else ""
        aw = a[i] if i < len(a) else ""
        out.append({"expected": ew, "actual": aw, "ok": bool(ew and ew == aw)})
    return out


def score_from_words(expected: str, actual: str) -> tuple[float, float]:
    e = _tokenize_words(expected)
    a = _tokenize_words(actual)
    if not e and not a:
        return 0.0, 0.0
    max_len = max(len(e), len(a), 1)
    correct_pos = sum(1 for i in range(min(len(e), len(a))) if e[i] == a[i])
    accuracy = (correct_pos / max_len) * 100.0
    fluency = min(100.0, (len(a) / max(1, len(e))) * 100.0)
    return round(accuracy, 2), round(fluency, 2)


def score_total(accuracy: float, fluency: float, expected_ph: list[str], actual_ph: list[str]) -> float:
    max_len = max(len(expected_ph), len(actual_ph), 1)
    mismatches = sum(1 for i in range(min(len(expected_ph), len(actual_ph))) if expected_ph[i] != actual_ph[i])
    mismatches += abs(len(expected_ph) - len(actual_ph))
    phoneme_score = max(0.0, 1.0 - (mismatches / max_len)) * 100.0
    total = 0.55 * accuracy + 0.2 * fluency + 0.25 * phoneme_score
    return round(max(0.0, min(100.0, total)), 2)


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


def transcribe_audio(audio_path: str, language_id: str) -> tuple[str, bool]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "", True

    try:
        client = OpenAI(api_key=api_key)
        with open(audio_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language=_lang_to_whisper_code(language_id),
                response_format="text",
            )
        if isinstance(result, str):
            return result.strip(), False
        return str(result).strip(), False
    except Exception:
        logger.exception("transcribe_audio failed")
        return "", True


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
                    url TEXT NOT NULL
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

            if db.execute("SELECT COUNT(*) FROM learning_videos WHERE language = 'en-US' AND title LIKE 'Level %'").fetchone()[0] == 0:
                # Remove default en-US video if it exists
                db.execute("DELETE FROM learning_videos WHERE language = 'en-US' AND title = 'English TH sound (guide)'")
                
                vids = [
                    ("en-US", "Level 1 - US Pronunciation", "https://youtube.com/playlist?list=PLKWcPfZiScgDfhVMerPPR2YqOP1XOeBTm&si=4BBfFAn2IFKAoRPy"),
                    ("en-US", "Level 2 - US Pronunciation", "https://youtube.com/playlist?list=PLKWcPfZiScgDf5Wc_Y5JZS17taUi2WWgx&si=CddChK4ALcBpMA7L"),
                    ("en-US", "Level 3 - US Pronunciation", "https://youtube.com/playlist?list=PLKWcPfZiScgDimnOyDv32VnEVFqhAItAy&si=v3ZpJ8iAhMcsYCOg"),
                    ("en-US", "Level 4 - US Pronunciation", "https://youtube.com/playlist?list=PLKWcPfZiScgDJkl2T7xAews-GoJMc4I7j&si=TNLKk8PBKSQTIzqi"),
                    ("en-US", "Level 5 - US Pronunciation", "https://youtube.com/playlist?list=PLKWcPfZiScgBACqEFo5TuhJWAReRNNTc8&si=o0TIHA4sIQVU_xQi"),
                    ("en-US", "Level 6 - US Pronunciation", "https://youtube.com/playlist?list=PLKWcPfZiScgAutnWOSAh2AH026L9w8c18&si=NQgnwgFjUxK8hfqe"),
                ]
                db.executemany("INSERT INTO learning_videos (language, title, url) VALUES (?, ?, ?)", vids)
                db.commit()

            if db.execute("SELECT COUNT(*) FROM learning_videos").fetchone()[0] == 0:
                vids = [
                    ("en-GB", "British English pronunciation basics", "https://www.youtube.com/watch?v=9kQimR4D_s0"),
                    ("ja-JP", "Japanese pronunciation tips", "https://www.youtube.com/watch?v=7Yl1WnO_KtQ"),
                    ("de-DE", "German CH sound explained", "https://www.youtube.com/watch?v=Y1lJxgJ5p0c"),
                    ("es-ES", "Spanish rolled R practice", "https://www.youtube.com/watch?v=3wqO7dLrPQQ"),
                ]
                db.executemany("INSERT INTO learning_videos (language, title, url) VALUES (?, ?, ?)", vids)
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
        sentence = g.db.execute(
            "SELECT id, text FROM sentences WHERE language = ? ORDER BY RANDOM() LIMIT 1",
            (language_id,),
        ).fetchone()
        user = get_user(user_id)
        return render_template("practice.html", user=user, profile=profile_row, language_id=language_id, sentence=sentence)

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
                transcript, demo = transcribe_audio(audio_path, language_id)
                if demo:
                    transcript = expected_text
            accuracy, fluency = score_from_words(expected_text, transcript)
            expected_ph = pseudo_phonemes(expected_text, language_id)
            actual_ph = pseudo_phonemes(transcript, language_id)
            total = score_total(accuracy, fluency, expected_ph, actual_ph)



            word_rows = compare_words(expected_text, transcript)
            phoneme_fb = build_phoneme_feedback(language_id, expected_ph, actual_ph)
            feedback = {
                "demo_stt": demo,
                "accuracy": accuracy,
                "fluency": fluency,
                "confidence": round(min(0.99, max(0.2, float(total) / 100.0)), 2),
                "phonemes_expected": expected_ph[:120],
                "phonemes_actual": actual_ph[:120],
                "word_rows": word_rows[:80],
                "phoneme_feedback": phoneme_fb,
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
                user_text, demo = transcribe_audio(audio_path, language_id)
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
        embed_url = url
        if "youtu.be/" in url:
            vid = url.split("youtu.be/")[-1].split("?")[0]
            embed_url = f"https://www.youtube.com/embed/{vid}"
        if "watch?v=" in url:
            vid = url.split("watch?v=")[-1].split("&")[0]
            embed_url = f"https://www.youtube.com/embed/{vid}"

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

    @app.post("/video-test/analyze")
    @login_required
    def video_test_analyze():
        try:
            user_id = int(session["user_id"])
        except Exception:
            user_id = 0

        def analyze_speech(expected: str, spoken: str):
            exp = [w for w in expected.lower().split(" ") if w]
            usr = [w for w in spoken.lower().split(" ") if w]

            mistakes = []
            correct = 0
            for i, word in enumerate(exp):
                if i >= len(usr) or not usr[i]:
                    mistakes.append({"word": word, "type": "Skipped"})
                elif usr[i] != word:
                    mistakes.append({"word": word, "said": usr[i], "type": "Incorrect"})
                else:
                    correct += 1

            score = int(round((correct / max(1, len(exp))) * 10))
            score = max(0, min(10, score))
            return {"score": score, "mistakes": mistakes, "correct": correct, "total": len(exp)}

        audio = request.files.get("audio")
        expected = (request.form.get("expected") or "").strip()
        if not audio or not audio.filename:
            return {"score": 0, "confidence": 0, "feedback": [], "error": "Analysis unavailable, try again"}

        audio_filename = f"{uuid.uuid4().hex}.webm"
        audio_path = os.path.join(UPLOAD_DIR, audio_filename)
        try:
            audio.save(audio_path)
        except Exception:
            logger.exception("video_test save failed")
            return {"score": 0, "confidence": 0, "feedback": [], "error": "Analysis unavailable, try again"}

        try:
            if demo_mode():
                return {
                    "score": 9,
                    "confidence": 82,
                    "feedback": [
                        "Good clarity",
                        "Improve 'th' pronunciation",
                        "Slight pause needed between words",
                    ],
                }

            profile_row = get_profile(user_id) if user_id else None
            language_id = (profile_row["selected_language"] or "en-US") if profile_row else "en-US"

            transcript, demo = transcribe_audio(audio_path, language_id)
            if demo or not transcript:
                return {
                    "score": 9,
                    "confidence": 80,
                    "feedback": [
                        "Good clarity",
                        "Improve 'th' pronunciation",
                        "Slight pause needed between words",
                    ],
                }

            if expected:
                analysis = analyze_speech(expected, transcript)
                score = int(analysis["score"])
                total = int(analysis["total"]) or 1
                correct = int(analysis["correct"])
                confidence = int(max(25, min(99, round((correct / total) * 100))))
                mistakes = list(analysis["mistakes"])[:3]
                feedback = []
                if not mistakes:
                    feedback = ["Good clarity", "Nice pacing", "Keep your stress on key words consistent"]
                else:
                    for m in mistakes:
                        if m.get("type") == "Skipped":
                            feedback.append(f"Skipped: '{m.get('word', '')}'")
                        else:
                            feedback.append(
                                f"Expected '{m.get('word', '')}', you said '{m.get('said', '')}'"
                            )
                    if len(feedback) < 3:
                        feedback.append("Repeat slowly once, then at normal speed")
                return {
                    "score": score,
                    "confidence": confidence,
                    "feedback": feedback,
                    "mistakes": mistakes,
                    "transcript": transcript,
                }

            base = 6 + secrets.randbelow(4)
            if len(transcript) > 30:
                base = min(10, base + 1)
            confidence = min(95, 55 + base * 4 + secrets.randbelow(10))

            options = [
                "Great clarity and pacing.",
                "Good pronunciation, improve 'th' sound.",
                "Excellent fluency, slight stress issues.",
                "Nice effort. Slow down a little and keep consonants crisp.",
                "Strong delivery. Focus on smoother transitions between sounds.",
            ]
            feedback = [
                options[secrets.randbelow(len(options))],
                "Try repeating the key phrase twice at a slower pace.",
                "Keep the end sounds clear (don’t drop final consonants).",
            ]
            return {"score": int(base), "confidence": int(confidence), "feedback": feedback}
        except Exception:
            logger.exception("video_test analyze failed")
            return {"score": 0, "confidence": 0, "feedback": [], "error": "Analysis unavailable, try again"}

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
            "SELECT id, title, url FROM learning_videos WHERE language = ? ORDER BY id ASC",
            (language_id,),
        ).fetchall()
        
        videos = []
        for r in rows:
            v = dict(r)
            url = v["url"]
            v["is_youtube"] = "youtube.com" in url or "youtu.be" in url
            v["embed_url"] = ""
            if v["is_youtube"]:
                if "list=" in url:
                    # Playlist
                    pid = url.split("list=")[-1].split("&")[0]
                    v["embed_url"] = f"https://www.youtube.com/embed/videoseries?list={pid}"
                elif "watch?v=" in url:
                    # Single video
                    vid = url.split("watch?v=")[-1].split("&")[0]
                    v["embed_url"] = f"https://www.youtube.com/embed/{vid}"
                elif "youtu.be/" in url:
                    # Short link
                    vid = url.split("youtu.be/")[-1].split("?")[0]
                    v["embed_url"] = f"https://www.youtube.com/embed/{vid}"
            videos.append(v)
            
        user = get_user(user_id)
        return render_template("learn.html", user=user, profile=profile_row, language_id=language_id, videos=videos)

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
