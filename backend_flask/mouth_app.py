import os

from flask import flash, g, redirect, render_template, session, url_for

from app import LANGUAGES, create_app
from modules.mouth_detection import mouth_bp


app = create_app()
app.register_blueprint(mouth_bp)


@app.get("/mouth-tracker")
def mouth_tracker():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))
    user_id = int(user_id)

    profile_row = g.db.execute("SELECT user_id, photo_filename, selected_language, updated_at FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    selected = (profile_row["selected_language"] or "").strip() if profile_row else ""
    allowed = {l["id"] for l in LANGUAGES}
    if not selected:
        flash("Choose a language first.", "error")
        return redirect(url_for("dashboard"))
    if selected not in allowed:
        flash("This language is no longer available. Please choose another language.", "error")
        return redirect(url_for("dashboard"))

    language_id = str(selected)
    sentence = g.db.execute(
        "SELECT id, text FROM sentences WHERE language = ? ORDER BY RANDOM() LIMIT 1",
        (language_id,),
    ).fetchone()
    if sentence is None:
        flash("No sentence available. Please try again.", "error")
        return redirect(url_for("practice"))

    user = g.db.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        return redirect(url_for("logout"))

    return render_template("mouth_tracker.html", user=user, profile=profile_row, sentence=sentence)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)
