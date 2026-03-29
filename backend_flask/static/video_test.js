(() => {
  const takeBtn = document.getElementById("takeTestBtn");
  const stopBtn = document.getElementById("stopTestBtn");
  const againBtn = document.getElementById("takeAgainBtn");
  const status = document.getElementById("testStatus");
  const statusText = document.getElementById("statusText");
  const testMic = document.getElementById("testMic");
  const testWave = document.getElementById("testWave");
  const resultCard = document.getElementById("resultCard");
  const improveList = document.getElementById("improveList");
  const scoreVal = document.getElementById("scoreVal");
  const confVal = document.getElementById("confVal");
  const scoreBadge = document.getElementById("scoreBadge");
  const errorBox = document.getElementById("testError");
  const expectedEl = document.getElementById("expectedText");
  const spinner = document.getElementById("testSpinner");

  const DEMO_MODE = Boolean(window.__DEMO_MODE__);
  const debug = () => {};

  let recording = false;
  let loading = false;
  let timers = [];

  const feedbackSets = [
    ["Good clarity", "Improve 'th' sound", "Better pacing needed"],
    ["Nice pronunciation", "Keep your mouth relaxed", "Stress key words clearly"],
    ["Great effort", "Slow down slightly", "Crisp consonants help confidence"],
  ];

  let recorder = null;
  let chunks = [];
  let micStream = null;

  function analyzeSpeech(expected, spoken) {
    const exp = expected.toLowerCase().split(" ");
    const usr = spoken.toLowerCase().split(" ");

    let mistakes = [];
    let correct = 0;

    exp.forEach((word, i) => {
      if (!usr[i]) {
        mistakes.push({ word, type: "Skipped" });
      } else if (usr[i] !== word) {
        mistakes.push({ word, said: usr[i], type: "Incorrect" });
      } else {
        correct++;
      }
    });

    const score = Math.round((correct / exp.length) * 10);

    return { score, mistakes };
  }

  function getExpectedPhrase() {
    const expected = String(expectedEl?.dataset?.expected || "").trim();
    return expected || "the quick brown fox jumps over the lazy dog";
  }

  function reset() {
    timers.forEach((t) => clearTimeout(t));
    timers = [];
    recording = false;
    loading = false;
    if (status) {
      status.classList.add("testStatusHidden");
      status.setAttribute("aria-hidden", "true");
    }
    if (resultCard) {
      resultCard.classList.add("resultCardHidden");
      resultCard.setAttribute("aria-hidden", "true");
      resultCard.classList.remove("fadeIn");
    }
    if (againBtn) againBtn.hidden = true;
    if (stopBtn) stopBtn.hidden = true;
    if (stopBtn) {
      stopBtn.disabled = false;
      stopBtn.textContent = "Stop";
    }
    if (takeBtn) takeBtn.disabled = false;
    if (scoreVal) scoreVal.textContent = "0";
    if (confVal) confVal.textContent = "0";
    if (improveList) improveList.innerHTML = "";
    if (errorBox) {
      errorBox.classList.add("testErrorHidden");
      errorBox.setAttribute("aria-hidden", "true");
    }
    if (testMic) testMic.classList.remove("micActive");
    if (testWave) testWave.classList.remove("waveActive");
    if (spinner) spinner.hidden = true;
    chunks = [];
    recorder = null;
    if (micStream) micStream.getTracks().forEach((t) => t.stop());
    micStream = null;
  }

  function showStatus(text) {
    if (!statusText) return;
    statusText.textContent = text;
  }

  function applyBadge(score) {
    if (!scoreBadge) return;
    scoreBadge.classList.remove("scoreBadgeGreen", "scoreBadgeYellow", "scoreBadgeRed");
    const score100 = Math.round((score / 10) * 100);
    if (score100 >= 80) scoreBadge.classList.add("scoreBadgeGreen");
    else if (score100 >= 60) scoreBadge.classList.add("scoreBadgeYellow");
    else scoreBadge.classList.add("scoreBadgeRed");
  }

  function setResult(data) {
    const score = Number(data?.score ?? 9);
    const confidence = Number(data?.confidence ?? 80);
    let feedback =
      Array.isArray(data?.feedback) && data.feedback.length
        ? data.feedback
        : [];
    if (!feedback.length && data?.transcript) {
      const expected = getExpectedPhrase();
      const res = analyzeSpeech(expected, String(data.transcript || ""));
      if (Array.isArray(res?.mistakes) && res.mistakes.length) {
        feedback = res.mistakes.slice(0, 3).map((m) => {
          if (m.type === "Skipped") return `Skipped: '${m.word}'`;
          return `Expected '${m.word}', you said '${m.said}'`;
        });
      }
    }
    if (!feedback.length) feedback = feedbackSets[Math.floor(Math.random() * feedbackSets.length)];
    if (improveList) {
      improveList.innerHTML = "";
      feedback.forEach((f) => {
        const li = document.createElement("li");
        li.textContent = f;
        improveList.appendChild(li);
      });
    }

    if (resultCard) {
      resultCard.classList.remove("resultCardHidden");
      resultCard.setAttribute("aria-hidden", "false");
      resultCard.classList.remove("fadeIn");
      void resultCard.offsetWidth;
      resultCard.classList.add("fadeIn");
    }
    if (againBtn) againBtn.hidden = false;
    applyBadge(score);
    const start = performance.now();
    const duration = 900;
    function tick(now) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const current = Math.max(0, Math.round(score * eased));
      if (scoreVal) scoreVal.textContent = String(current);
      const currentConf = Math.max(0, Math.round(confidence * eased));
      if (confVal) confVal.textContent = String(currentConf);
      if (t < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  function showError(msg) {
    if (errorBox) {
      errorBox.textContent = msg || "Analysis unavailable, try again";
      errorBox.classList.remove("testErrorHidden");
      errorBox.setAttribute("aria-hidden", "false");
    }
    if (againBtn) againBtn.hidden = false;
    if (takeBtn) takeBtn.disabled = false;
  }

  function stageMessages() {
    showStatus("Analyzing audio...");
    timers.push(
      setTimeout(() => {
        showStatus("Detecting pronunciation...");
      }, 700)
    );
    timers.push(
      setTimeout(() => {
        showStatus("Generating feedback...");
      }, 1500)
    );
  }

  async function analyze(blob) {
    loading = true;
    stageMessages();
    try {
      if (spinner) spinner.hidden = false;
      if (DEMO_MODE) {
        return {
          score: 9,
          confidence: 82,
          feedback: ["Good clarity", "Improve 'th' pronunciation", "Slight pause needed between words"],
        };
      }
      const fd = new FormData();
      fd.append("expected", getExpectedPhrase());
      fd.append("audio", new File([blob], "test.webm", { type: blob.type || "audio/webm" }));
      const res = await fetch("/video-test/analyze", { method: "POST", body: fd });
      if (!res.ok) return null;
      const data = await res.json().catch(() => null);
      return data;
    } catch (e) {
      debug(e);
      return null;
    } finally {
      loading = false;
      if (spinner) spinner.hidden = true;
    }
  }

  async function startTest() {
    if (recording || loading) return;
    reset();
    recording = true;
    if (status) {
      status.classList.remove("testStatusHidden");
      status.setAttribute("aria-hidden", "false");
    }
    showStatus("Recording…");
    if (stopBtn) stopBtn.hidden = false;
    if (takeBtn) takeBtn.disabled = true;
    if (testMic) testMic.classList.add("micActive");
    if (testWave) testWave.classList.add("waveActive");

    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      debug(e);
      recording = false;
      if (status) {
        status.classList.add("testStatusHidden");
        status.setAttribute("aria-hidden", "true");
      }
      showError("Analysis unavailable, try again");
      return;
    }

    try {
      const candidates = ["audio/webm;codecs=opus", "audio/webm"];
      const supported = candidates.find((t) => (window.MediaRecorder?.isTypeSupported ? MediaRecorder.isTypeSupported(t) : false));
      recorder = supported ? new MediaRecorder(micStream, { mimeType: supported }) : new MediaRecorder(micStream);
    } catch (e) {
      debug(e);
      recording = false;
      if (status) {
        status.classList.add("testStatusHidden");
        status.setAttribute("aria-hidden", "true");
      }
      showError("Analysis unavailable, try again");
      if (micStream) micStream.getTracks().forEach((t) => t.stop());
      micStream = null;
      return;
    }

    chunks = [];
    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data);
    };
    recorder.onstop = async () => {
      if (micStream) micStream.getTracks().forEach((t) => t.stop());
      micStream = null;
      if (testMic) testMic.classList.remove("micActive");
      if (testWave) testWave.classList.remove("waveActive");

      const blob = new Blob(chunks, { type: "audio/webm" });
      const data = await analyze(blob);
      if (status) {
        status.classList.add("testStatusHidden");
        status.setAttribute("aria-hidden", "true");
      }
      if (!data || data.error) {
        showError("Analysis unavailable, try again");
        return;
      }
      setResult(data);
    };

    recorder.start();
    timers.push(
      setTimeout(() => {
        if (recording) stopTest();
      }, 3500)
    );
  }

  function stopTest() {
    if (!recording) return;
    recording = false;
    if (stopBtn) {
      stopBtn.disabled = true;
      stopBtn.textContent = "Stopping…";
    }
    try {
      recorder.stop();
    } catch (e) {
      debug(e);
      if (micStream) micStream.getTracks().forEach((t) => t.stop());
      micStream = null;
      if (status) {
        status.classList.add("testStatusHidden");
        status.setAttribute("aria-hidden", "true");
      }
      showError("Analysis unavailable, try again");
    }
  }

  if (takeBtn) takeBtn.addEventListener("click", startTest);
  if (stopBtn) stopBtn.addEventListener("click", stopTest);
  if (againBtn) againBtn.addEventListener("click", reset);

  reset();
})();
