import { useEffect, useState } from "react";
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

      <div className="grid2">
        <div className="card">
          <div className="cardTitle">Progress</div>
          {data ? (
            <div className="statsRow">
              <Stat label="Avg score (7d)" value={`${data.avg_score_last_7}`} />
              <Stat label="Daily streak" value={`${data.streak_days} days`} />
            </div>
          ) : (
            <div className="muted">Loading...</div>
          )}
        </div>

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
      </div>
    </div>
  );
}

