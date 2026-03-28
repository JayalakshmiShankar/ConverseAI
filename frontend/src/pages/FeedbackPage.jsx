import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

function DiffPhonemes({ expected, actual }) {
  const max = Math.max(expected.length, actual.length);
  const rows = [];
  for (let i = 0; i < max; i += 1) {
    const e = expected[i] || "";
    const a = actual[i] || "";
    const ok = e === a && e;
    rows.push(
      <div className={`phonemeRow ${ok ? "" : "phonemeRowBad"}`} key={`${i}-${e}-${a}`}>
        <div className="phonemeCell">{e || "—"}</div>
        <div className="phonemeCell">{a || "—"}</div>
      </div>
    );
  }
  return (
    <div className="phonemeTable">
      <div className="phonemeHead">
        <div>Expected</div>
        <div>Actual</div>
      </div>
      {rows.slice(0, 40)}
      {max > 40 ? <div className="muted">Showing first 40 phoneme steps.</div> : null}
    </div>
  );
}

export function FeedbackPage() {
  const last = useMemo(() => {
    const raw = sessionStorage.getItem("last_session");
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }, []);

  const [session, setSession] = useState(last);
  const [error, setError] = useState("");

  useEffect(() => {
    if (session) return;
    api
      .listSessions()
      .then((r) => {
        if (r?.items?.length) {
          const s = r.items[0];
          setSession({
            session_id: s.session_id,
            transcript: s.transcript,
            phonemes_expected: [],
            phonemes_actual: [],
            score: s.score,
            confidence: s.confidence,
            feedback_text: "",
            created_at: s.created_at,
          });
        }
      })
      .catch((e) => setError(e.message || "Failed to load"));
  }, [session]);

  return (
    <div>
      <div className="pageTitle">Feedback</div>
      {error ? <div className="error">{error}</div> : null}
      {!session ? <div className="muted">No feedback yet. Record a session first.</div> : null}

      {session ? (
        <>
          <div className="grid2">
            <div className="card">
              <div className="cardTitle">Pronunciation Score</div>
              <div className="scoreBig">{session.score}</div>
              <div className="muted">Confidence: {session.confidence}</div>
              <div className="hint">{session.feedback_text || "Open a new session to get detailed tips."}</div>
            </div>

            <div className="card">
              <div className="cardTitle">Transcript</div>
              <div className="transcript">{session.transcript}</div>
              {session.mouth_metrics ? (
                <div className="hint">
                  Mouth openness avg: <strong>{session.mouth_metrics.mouth_openness_avg}</strong> · Out-of-range:{" "}
                  <strong>{Math.round((session.mouth_metrics.mouth_openness_out_of_range_pct || 0) * 100)}%</strong>
                </div>
              ) : (
                <div className="muted">No mouth metrics attached.</div>
              )}
            </div>
          </div>

          <div className="card">
            <div className="cardTitle">Phoneme Breakdown</div>
            {session.phonemes_expected?.length ? (
              <DiffPhonemes expected={session.phonemes_expected} actual={session.phonemes_actual || []} />
            ) : (
              <div className="muted">Phoneme breakdown is generated for new sessions from the Recording page.</div>
            )}
          </div>

          <div className="rowButtons">
            <Link className="primaryBtn" to="/record">
              Take again
            </Link>
          </div>
        </>
      ) : null}
    </div>
  );
}

