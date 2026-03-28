import { useEffect, useRef, useState } from "react";

export function AudioRecorder({ onAudioReady }) {
  const [supported, setSupported] = useState(true);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const mediaRef = useRef(null);
  const chunksRef = useRef([]);

  useEffect(() => {
    setSupported(Boolean(window.MediaRecorder && navigator.mediaDevices?.getUserMedia));
  }, []);

  const start = async () => {
    setError("");
    if (!supported) return;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });
    chunksRef.current = [];
    mr.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
    };
    mr.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      const url = URL.createObjectURL(blob);
      setAudioUrl(url);
      onAudioReady?.(blob);
      stream.getTracks().forEach((t) => t.stop());
    };
    mediaRef.current = mr;
    mr.start();
    setRecording(true);
  };

  const stop = () => {
    const mr = mediaRef.current;
    if (!mr) return;
    try {
      mr.stop();
    } finally {
      setRecording(false);
    }
  };

  return (
    <div className="card">
      <div className="cardTitle">Audio</div>
      {!supported ? <div className="error">Recording is not supported in this browser.</div> : null}
      {error ? <div className="error">{error}</div> : null}

      <div className="rowButtons">
        <button className="secondaryBtn" type="button" disabled={!supported || recording} onClick={start}>
          Start recording
        </button>
        <button className="secondaryBtn" type="button" disabled={!recording} onClick={stop}>
          Stop
        </button>
      </div>

      {audioUrl ? (
        <div className="audioPreview">
          <audio controls src={audioUrl} />
        </div>
      ) : null}
    </div>
  );
}

