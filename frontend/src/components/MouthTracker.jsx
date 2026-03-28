import { useEffect, useMemo, useRef, useState } from "react";
import { FaceLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";

function dist(a, b) {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return Math.sqrt(dx * dx + dy * dy);
}

export function MouthTracker({ onMetricsChange }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const rafRef = useRef(0);
  const landmarkerRef = useRef(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const metricsRef = useRef({ openSamples: [] });

  const targetRange = useMemo(() => ({ min: 0.02, max: 0.08 }), []);

  useEffect(() => {
    let mounted = true;
    let localStream = null;

    async function setup() {
      setError("");
      setStatus("loading");
      try {
        const vision = await FilesetResolver.forVisionTasks(
          "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/wasm"
        );
        const landmarker = await FaceLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath:
              "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
          },
          runningMode: "VIDEO",
          numFaces: 1,
        });
        if (!mounted) return;
        landmarkerRef.current = landmarker;

        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
        if (!mounted) return;
        localStream = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        setStatus("running");
      } catch (e) {
        setError(e.message || "Webcam/Face tracking failed");
        setStatus("error");
      }
    }

    setup();
    return () => {
      mounted = false;
      cancelAnimationFrame(rafRef.current);
      if (localStream) localStream.getTracks().forEach((t) => t.stop());
    };
  }, []);

  useEffect(() => {
    if (status !== "running") return;
    const landmarker = landmarkerRef.current;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!landmarker || !video || !canvas) return;

    const ctx = canvas.getContext("2d");
    let lastEmit = performance.now();

    const tick = () => {
      rafRef.current = requestAnimationFrame(tick);
      if (video.readyState < 2) return;

      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const res = landmarker.detectForVideo(video, performance.now());
      const face = res.faceLandmarks?.[0];
      if (!face) return;

      const upper = face[13];
      const lower = face[14];
      const openness = dist(upper, lower);
      metricsRef.current.openSamples.push(openness);
      if (metricsRef.current.openSamples.length > 300) metricsRef.current.openSamples.shift();

      const inRange = openness >= targetRange.min && openness <= targetRange.max;
      ctx.strokeStyle = inRange ? "rgba(37,99,235,0.9)" : "rgba(239,68,68,0.9)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(upper.x * canvas.width, upper.y * canvas.height, 6, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(lower.x * canvas.width, lower.y * canvas.height, 6, 0, Math.PI * 2);
      ctx.stroke();

      const now = performance.now();
      if (now - lastEmit > 800) {
        lastEmit = now;
        const samples = metricsRef.current.openSamples.slice(-60);
        const avg = samples.reduce((a, b) => a + b, 0) / Math.max(1, samples.length);
        const outOfRangePct = samples.filter((x) => x < targetRange.min || x > targetRange.max).length / Math.max(1, samples.length);
        onMetricsChange?.({
          mouth_openness_avg: Number(avg.toFixed(4)),
          mouth_openness_out_of_range_pct: Number(outOfRangePct.toFixed(3)),
          target_range: targetRange,
        });
      }
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [onMetricsChange, status, targetRange]);

  return (
    <div className="card">
      <div className="cardTitle">Mouth Movement (Webcam)</div>
      {error ? <div className="error">{error}</div> : null}
      <div className="mouthWrap">
        <div className="mouthVideo">
          <video ref={videoRef} className="video" playsInline muted />
          <canvas ref={canvasRef} className="overlay" />
        </div>
        <div className="mouthRef">
          <div className="refTitle">Reference</div>
          <div className="refBox">
            <div className="refRow">
              <span>Target openness</span>
              <span className="chip chipBlue">
                {targetRange.min.toFixed(2)}–{targetRange.max.toFixed(2)}
              </span>
            </div>
            <div className="muted">
              The overlay turns red when your lip opening is outside the expected range for clear articulation.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
