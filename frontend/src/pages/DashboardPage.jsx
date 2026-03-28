import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

function Stat({ label, value }) {
  return (
    <div className="stat">
      <div className="statLabel">{label}</div>
      <div className="statValue">{value}</div>
    </div>
  );
}

export function DashboardPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    api
      .dashboard()
      .then((d) => mounted && setData(d))
      .catch((e) => mounted && setError(e.message || "Failed to load dashboard"))
      .finally(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div>
      <div className="pageTitle">Dashboard</div>
      {error ? <div className="error">{error}</div> : null}

      <div className="grid3">
        <div className="card cardBlue">
          <div className="cardTitle">Pronunciation Score</div>
          {data ? (
            <div className="statsRow">
              <Stat label="Avg score (7d)" value={`${data.avg_score_last_7}`} />
              <Stat label="Confidence" value="Auto" />
            </div>
          ) : (
            <div className="muted">Loading...</div>
          )}
          <div className="hint">Track accuracy, fluency, and phoneme consistency over time.</div>
        </div>

        <div className="card cardGreen">
          <div className="cardTitle">Daily Practice</div>
          {data ? <div className="streakBig">{data.streak_days} day streak</div> : <div className="muted">Loading...</div>}
          <div className="hint">Do one short recording per day to keep your streak.</div>
          <div className="rowButtons">
            <Link className="primaryBtn" to="/record">
              Take test
            </Link>
          </div>
        </div>

        <div className="card">
          <div className="cardTitle">AI Conversation Bot</div>
          <div className="muted">Practice with short professional phrases and repeat with feedback.</div>
          <div className="rowButtons">
            <Link className="primaryBtn" to="/chat">
              Start practice
            </Link>
            <Link className="secondaryBtn" to="/languages">
              Change language
            </Link>
          </div>
        </div>
      </div>

      <div className="grid2">
        <div className="card">
          <div className="cardTitle">Recent Sessions</div>
          {data && data.recent_sessions && data.recent_sessions.length ? (
            <div className="table">
              {data.recent_sessions.map((s) => (
                <div className="row" key={s.session_id}>
                  <div className="rowMain">
                    <div className="rowTop">
                      <span className="chip">{s.language}</span>
                      <span className="chip chipBlue">Score {s.score}</span>
                    </div>
                    <div className="rowSub">{s.transcript}</div>
                  </div>
                  <div className="rowMeta">{new Date(s.created_at).toLocaleString()}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="muted">No sessions yet. Go to Record to start.</div>
          )}
        </div>

        <div className="card">
          <div className="cardTitle">Feedback History</div>
          <div className="muted">Open the latest detailed report (score, phonemes, mouth metrics).</div>
          <div className="rowButtons">
            <Link className="primaryBtn" to="/feedback">
              View feedback
            </Link>
          </div>
          <div className="hint">Tip: Focus on one sound per day (e.g., “th”, “r”, “w”).</div>
        </div>
      </div>
    </div>
  );
}
