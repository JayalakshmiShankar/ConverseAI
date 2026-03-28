(() => {
  const form = document.getElementById("uploadForm");
  const startBtn = document.getElementById("startRec");
  const stopBtn = document.getElementById("stopRec");
  const statusEl = document.getElementById("recStatus");
  const audioPreview = document.getElementById("audioPreview");
  const audioPlayer = document.getElementById("audioPlayer");
  const fileInput = document.getElementById("audioFile");
  const analyzeBtn = document.getElementById("analyzeBtn");
  const hint = document.getElementById("analyzeHint");
  const cam = document.getElementById("cam");

  let recorder = null;
  let chunks = [];
  let recordedBlob = null;
  let camStream = null;
  let micStream = null;

  async function setupCamera() {
    if (!cam) return;
    try {
      camStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      cam.srcObject = camStream;
    } catch {}
  }

  async function startRecording() {
    recordedBlob = null;
    audioPreview.hidden = true;
    chunks = [];
    statusEl.textContent = "Requesting microphone…";
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorder = new MediaRecorder(micStream, { mimeType: "audio/webm" });
    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data);
    };
    recorder.onstop = () => {
      recordedBlob = new Blob(chunks, { type: "audio/webm" });
      audioPlayer.src = URL.createObjectURL(recordedBlob);
      audioPreview.hidden = false;
      statusEl.textContent = "Recorded";
      if (micStream) micStream.getTracks().forEach((t) => t.stop());
      micStream = null;
    };
    recorder.start();
    statusEl.textContent = "Recording…";
    startBtn.disabled = true;
    stopBtn.disabled = false;
  }

  function stopRecording() {
    if (!recorder) return;
    recorder.stop();
    recorder = null;
    startBtn.disabled = false;
    stopBtn.disabled = true;
  }

  async function submitForm(e) {
    e.preventDefault();
    analyzeBtn.disabled = true;
    analyzeBtn.querySelector("span").textContent = "Analyzing…";
    hint.textContent = "Uploading audio and generating feedback…";

    const fd = new FormData(form);
    const file = fileInput?.files?.[0];
    if (file) {
      fd.set("audio", file);
    } else if (recordedBlob) {
      fd.set("audio", new File([recordedBlob], "recording.webm", { type: "audio/webm" }));
    }

    try {
      const res = await fetch(form.action, { method: "POST", body: fd, redirect: "follow" });
      window.location.href = res.url;
    } catch {
      window.location.reload();
    }
  }

  if (startBtn) startBtn.addEventListener("click", () => startRecording());
  if (stopBtn) stopBtn.addEventListener("click", () => stopRecording());
  if (form) form.addEventListener("submit", submitForm);

  setupCamera();
  window.addEventListener("beforeunload", () => {
    if (camStream) camStream.getTracks().forEach((t) => t.stop());
    if (micStream) micStream.getTracks().forEach((t) => t.stop());
  });
})();

