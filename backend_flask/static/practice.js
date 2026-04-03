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
  const overlay = document.getElementById("overlay");
  const camStatusText = document.getElementById("camStatusText");
  const camStatusIcon = document.getElementById("camStatusIcon");
  const micWrap = document.getElementById("micWrap");
  const miniLoad = document.getElementById("miniLoad");
  const miniLoadText = document.getElementById("miniLoadText");
  const spokenTextEl = document.getElementById("spokenText");
  const waveformCanvas = document.getElementById("waveform");
  const waveformContainer = document.getElementById("waveformContainer");
  const silenceWarning = document.getElementById("silenceWarning");
  const sentenceDisplay = document.getElementById("sentenceDisplay");
  const listenBtn = document.getElementById("listenBtn");

  const debug = () => {};

  if (listenBtn) {
    listenBtn.addEventListener("click", () => {
      const text = window.__TARGET_TEXT__ || "";
      const lang = window.__LANG_ID__ || "en-US";
      if (!text) return;
      
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = lang;
      
      // Try to find a high quality native voice
      const voices = window.speechSynthesis.getVoices();
      const nativeVoice = voices.find(v => v.lang === lang && !v.localService);
      if (nativeVoice) utterance.voice = nativeVoice;
      
      window.speechSynthesis.speak(utterance);
    });
  }

  let recorder = null;
  let chunks = [];
  let recordedBlob = null;
  let camStream = null;
  let micStream = null;
  let recTimer = null;
  let recTick = null;
  const MAX_REC_MS = 15000; // Increased max time for natural speech
  let speech = null;
  let speechText = "";
  let speechStarted = false;

  let audioCtx = null;
  let analyser = null;
  let dataArray = null;
  let animationId = null;
  let lastAudioTime = Date.now();
  let silenceTimer = null;
  let wordCount = 0;

  let mouthPollTimer = null;
  let isMouthUpdating = false;
  let mouthAbortController = null;
  const offscreenCanvas = document.createElement("canvas");
  const offscreenCtx = offscreenCanvas.getContext("2d");

  async function updateMouthStatus() {
    if (isMouthUpdating || !cam || !overlay || !camStream) return;
    isMouthUpdating = true;

    const ctx = overlay.getContext("2d");
    if (!ctx) {
      isMouthUpdating = false;
      return;
    }

    const vw = cam.videoWidth;
    const vh = cam.videoHeight;
    if (!vw || !vh) {
      isMouthUpdating = false;
      return;
    }

    overlay.width = vw;
    overlay.height = vh;

    // Capture frame for backend
    offscreenCanvas.width = 320;
    offscreenCanvas.height = Math.round((vh / vw) * 320);
    offscreenCtx.drawImage(cam, 0, 0, offscreenCanvas.width, offscreenCanvas.height);

    const blob = await new Promise((resolve) => {
      offscreenCanvas.toBlob((b) => resolve(b), "image/jpeg", 0.7);
    });
    if (!blob) {
      isMouthUpdating = false;
      return;
    }

    const fd = new FormData();
    fd.append("frame", blob, "frame.jpg");

    if (mouthAbortController) mouthAbortController.abort();
    mouthAbortController = new AbortController();

    try {
      const res = await fetch("/mouth-status", { 
        method: "POST", 
        body: fd,
        signal: mouthAbortController.signal
      });
      const data = await res.json();

      ctx.clearRect(0, 0, vw, vh);

      if (data.mouth === "open" || data.mouth === "closed") {
        if (camStatusText) camStatusText.textContent = "Mouth detected. Tracking active.";
        
        if (data.landmarks) {
          const lm = data.landmarks;
          const lx = lm.left.x * vw;
          const ly = lm.left.y * vh;
          const rx = lm.right.x * vw;
          const ry = lm.right.y * vh;
          const ux = lm.upper.x * vw;
          const uy = lm.upper.y * vh;
          const bx = lm.lower.x * vw;
          const by = lm.lower.y * vh;

          // Draw green highlight around mouth
          ctx.beginPath();
          ctx.moveTo(lx, ly);
          ctx.lineTo(ux, uy);
          ctx.lineTo(rx, ry);
          ctx.lineTo(bx, by);
          ctx.closePath();
          ctx.lineWidth = 4;
          ctx.strokeStyle = "#00ff00"; // Pure green for better visibility
          ctx.fillStyle = "rgba(0, 255, 0, 0.4)";
          ctx.stroke();
          ctx.fill();
        }
      } else {
        if (camStatusText) camStatusText.textContent = "Mouth not visible. Center your face.";
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        debug("Mouth poll failed", e);
      }
    } finally {
      isMouthUpdating = false;
    }
  }

  function startMouthPolling() {
    if (mouthPollTimer) return;
    mouthPollTimer = setInterval(updateMouthStatus, 100);
  }

  function stopMouthPolling() {
    if (mouthPollTimer) {
      clearInterval(mouthPollTimer);
      mouthPollTimer = null;
    }
    if (mouthAbortController) {
      mouthAbortController.abort();
      mouthAbortController = null;
    }
    isMouthUpdating = false;
  }

  function highlightWords(spoken) {
    if (!sentenceDisplay) return;
    const spokenWords = spoken.toLowerCase().split(/\s+/);
    wordCount = spokenWords.length;
    const targetSpans = sentenceDisplay.querySelectorAll(".p-word");
    
    targetSpans.forEach(span => {
      const targetWord = span.dataset.word;
      if (spokenWords.includes(targetWord)) {
        span.classList.add("highlight");
      }
    });
  }

  function drawWaveform() {
    if (!waveformCanvas || !analyser) return;
    const ctx = waveformCanvas.getContext("2d");
    const width = waveformCanvas.width;
    const height = waveformCanvas.height;
    
    analyser.getByteTimeDomainData(dataArray);
    
    ctx.fillStyle = "rgba(255, 255, 255, 0)";
    ctx.clearRect(0, 0, width, height);
    
    ctx.lineWidth = 3;
    ctx.strokeStyle = "#2563eb";
    ctx.beginPath();
    
    const sliceWidth = width / dataArray.length;
    let x = 0;
    
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      const v = dataArray[i] / 128.0;
      const y = (v * height) / 2;
      
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
      
      x += sliceWidth;
      sum += Math.abs(dataArray[i] - 128);
    }
    
    const volume = sum / dataArray.length;
    if (volume > 5) {
      lastAudioTime = Date.now();
      if (silenceWarning) silenceWarning.hidden = true;
    } else if (Date.now() - lastAudioTime > 2000) {
      if (silenceWarning) silenceWarning.hidden = false;
    }
    
    // Smart Stop Logic
    if (Date.now() - lastAudioTime > 1800 && wordCount >= 3) {
      debug("Smart stop triggered");
      stopRecording();
      return;
    }
    
    ctx.lineTo(width, height / 2);
    ctx.stroke();
    
    animationId = requestAnimationFrame(drawWaveform);
  }

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
        highlightWords(speechText);
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
      camStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      cam.srcObject = camStream;
      cam.onloadedmetadata = () => {
        startMouthPolling();
      };
      if (camStatusIcon) camStatusIcon.classList.remove("isWarn");
      if (camStatusText) camStatusText.textContent = "Camera active. Adjust position.";
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
    wordCount = 0;
    lastAudioTime = Date.now();
    if (waveformContainer) waveformContainer.hidden = false;
    if (spokenTextEl) spokenTextEl.value = "";
    
    // Reset highlights
    if (sentenceDisplay) {
      sentenceDisplay.querySelectorAll(".p-word").forEach(s => s.classList.remove("highlight"));
    }

    statusEl.textContent = "Requesting microphone…";
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      debug(e);
      statusEl.textContent = "Microphone permission denied";
      return;
    }

    // Audio context for visualizer
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioCtx.createAnalyser();
      const source = audioCtx.createMediaStreamSource(micStream);
      source.connect(analyser);
      analyser.fftSize = 2048;
      dataArray = new Uint8Array(analyser.frequencyBinCount);
      drawWaveform();
    } catch (e) {
      debug("Audio visualizer failed", e);
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
      if (waveformContainer) waveformContainer.hidden = true;
      if (animationId) cancelAnimationFrame(animationId);
      if (audioCtx) audioCtx.close();
      
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
    stopMouthPolling();
    if (camStream) camStream.getTracks().forEach((t) => t.stop());
    if (micStream) micStream.getTracks().forEach((t) => t.stop());
  });
})();
