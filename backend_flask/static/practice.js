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
  const camStatusText = document.getElementById("camStatusText");
  const camStatusIcon = document.getElementById("camStatusIcon");
  const micWrap = document.getElementById("micWrap");
  const miniLoad = document.getElementById("miniLoad");
  const miniLoadText = document.getElementById("miniLoadText");
  const spokenTextEl = document.getElementById("spokenText");

  const debug = () => {};

  let recorder = null;
  let chunks = [];
  let recordedBlob = null;
  let camStream = null;
  let micStream = null;
  let recTimer = null;
  let recTick = null;
  const MAX_REC_MS = 6000;
  let speech = null;
  let speechText = "";
  let speechStarted = false;

  function setupSpeech() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return null;
    try {
      const r = new SR();
      r.continuous = true;
      r.interimResults = true;
      r.maxAlternatives = 1;
      r.onresult = (e) => {
        let out = "";
        for (let i = 0; i < e.results.length; i++) {
          out += (e.results[i][0] && e.results[i][0].transcript ? e.results[i][0].transcript : "") + " ";
        }
        speechText = out.trim();
        if (spokenTextEl) spokenTextEl.value = speechText;
      };
      r.onerror = () => {};
      r.onend = () => {
        speechStarted = false;
      };
      return r;
    } catch {
      return null;
    }
  }

  async function setupCamera() {
    if (!cam) return;
    try {
      camStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      cam.srcObject = camStream;
      if (camStatusText) camStatusText.textContent = "Face tracking active. Keep your mouth visible.";
      if (camStatusIcon) {
        camStatusIcon.textContent = "✓";
        camStatusIcon.classList.remove("isWarn");
      }
    } catch (e) {
      debug(e);
      if (camStatusText) camStatusText.textContent = "Camera not available. Please allow camera permission.";
      if (camStatusIcon) {
        camStatusIcon.textContent = "!";
        camStatusIcon.classList.add("isWarn");
      }
    }
  }

  async function startRecording() {
    recordedBlob = null;
    audioPreview.hidden = true;
    chunks = [];
    speechText = "";
    if (spokenTextEl) spokenTextEl.value = "";
    statusEl.textContent = "Requesting microphone…";
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      debug(e);
      statusEl.textContent = "Microphone permission denied";
      return;
    }
    try {
      const candidates = ["audio/webm;codecs=opus", "audio/webm"];
      const supported = candidates.find((t) =>
        window.MediaRecorder?.isTypeSupported ? MediaRecorder.isTypeSupported(t) : false
      );
      recorder = supported ? new MediaRecorder(micStream, { mimeType: supported }) : new MediaRecorder(micStream);
    } catch (e) {
      debug(e);
      statusEl.textContent = "Recording not supported";
      if (micStream) micStream.getTracks().forEach((t) => t.stop());
      micStream = null;
      return;
    }
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
      if (speech && speechStarted) {
        try {
          speech.stop();
        } catch {}
      }
      if (recTimer) clearTimeout(recTimer);
      recTimer = null;
      if (recTick) clearInterval(recTick);
      recTick = null;
    };
    recorder.start();
    if (!speech) speech = setupSpeech();
    if (speech && !speechStarted) {
      try {
        speech.lang = document.documentElement.lang || "en-US";
        speech.start();
        speechStarted = true;
      } catch {}
    }
    const startedAt = Date.now();
    statusEl.textContent = "Recording… 0.0s";
    if (recTick) clearInterval(recTick);
    recTick = setInterval(() => {
      const ms = Date.now() - startedAt;
      statusEl.textContent = `Recording… ${(ms / 1000).toFixed(1)}s`;
    }, 120);
    if (recTimer) clearTimeout(recTimer);
    recTimer = setTimeout(() => {
      stopRecording();
    }, MAX_REC_MS);
    startBtn.disabled = true;
    stopBtn.disabled = false;
    if (micWrap) micWrap.classList.add("micActive");
  }

  function stopRecording() {
    if (!recorder) return;
    recorder.stop();
    recorder = null;
    startBtn.disabled = false;
    stopBtn.disabled = true;
    if (micWrap) micWrap.classList.remove("micActive");
    if (speech && speechStarted) {
      try {
        speech.stop();
      } catch {}
    }
    if (recTimer) clearTimeout(recTimer);
    recTimer = null;
    if (recTick) clearInterval(recTick);
    recTick = null;
  }

  async function submitForm(e) {
    e.preventDefault();
    analyzeBtn.disabled = true;
    analyzeBtn.querySelector("span").textContent = "Analyzing…";
    hint.textContent = "Analyzing pronunciation…";

    const fd = new FormData(form);
    const file = fileInput?.files?.[0];
    if (file) {
      fd.set("audio", file);
    } else if (recordedBlob) {
      fd.set("audio", new File([recordedBlob], "recording.webm", { type: "audio/webm" }));
    }
    if (speechText) fd.set("spoken_text", speechText);

    if (miniLoad) miniLoad.hidden = false;
    if (miniLoadText) miniLoadText.textContent = "Analyzing…";

    const startedAt = Date.now();
    try {
      const res = await fetch(form.action, { method: "POST", body: fd, redirect: "follow" });
      const url = res.url;
      const elapsed = Date.now() - startedAt;
      const minMs = 150;
      const wait = Math.max(0, minMs - elapsed);
      if (wait) setTimeout(() => (window.location.href = url), wait);
      else window.location.href = url;
    } catch (e) {
      debug(e);
      if (miniLoad) miniLoad.hidden = true;
      analyzeBtn.disabled = false;
      analyzeBtn.querySelector("span").textContent = "Analyze pronunciation";
      hint.textContent = "Upload failed. Please try again.";
      statusEl.textContent = "Ready";
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
