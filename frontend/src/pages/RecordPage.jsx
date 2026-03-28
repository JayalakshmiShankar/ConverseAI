import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { getSelectedLanguage } from "../lib/state";
import { AudioRecorder } from "../components/AudioRecorder";
import { MouthTracker } from "../components/MouthTracker";

export function RecordPage() {
  const navigate = useNavigate();
  const language = useMemo(() => getSelectedLanguage(), []);
  const [referenceText, setReferenceText] = useState("Thank you for your time. I look forward to working with you.");
  const [audioBlob, setAudioBlob] = useState(null);
  const [uploadFile, setUploadFile] = useState(null);
  const [mouthMetrics, setMouthMetrics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const onAnalyze = async () => {
    setError("");
    if (!language) {
      setError("Select a language first.");
      return;
    }
    const file = uploadFile || (audioBlob ? new File([audioBlob], "recording.webm", { type: "audio/webm" }) : null);
    if (!file) {
      setError("Record or upload an audio file.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.createSession({ language, referenceText, mouthMetrics, audioFile: file });
      sessionStorage.setItem("last_session", JSON.stringify(res));
      navigate("/feedback");
    } catch (err) {
      setError(err.message || "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="pageTitle">Recording</div>
      <div className="muted">
        Selected language: <span className="chip">{language || "Not selected"}</span>
      </div>

      <div className="grid2">
        <div className="card">
          <div className="cardTitle">Practice Phrase</div>
          <div className="muted">Use a short business phrase. This becomes the pronunciation reference.</div>
          <textarea
            className="textarea"
            value={referenceText}
            onChange={(e) => setReferenceText(e.target.value)}
            rows={4}
          />
        </div>

        <div className="card">
          <div className="cardTitle">Upload</div>
          <div className="muted">You can upload an existing recording instead of using the microphone.</div>
          <input
            className="input"
            type="file"
            accept="audio/*"
            onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
          />
          {uploadFile ? <div className="hint">Selected: {uploadFile.name}</div> : null}
        </div>
      </div>

      <div className="grid2">
        <AudioRecorder onAudioReady={(blob) => setAudioBlob(blob)} />
        <MouthTracker onMetricsChange={(m) => setMouthMetrics(m)} />
      </div>

      {error ? <div className="error">{error}</div> : null}

      <div className="rowButtons">
        <button className="primaryBtn" type="button" disabled={loading} onClick={onAnalyze}>
          {loading ? "Analyzing..." : "Analyze Pronunciation"}
        </button>
      </div>

      <div className="hint">
        Output includes transcript, phoneme breakdown, pronunciation score, and mouth movement metrics.
      </div>
    </div>
  );
}

