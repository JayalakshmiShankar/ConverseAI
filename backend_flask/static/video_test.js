(() => {
  const takeBtn = document.getElementById("takeTestBtn");
  const stopBtn = document.getElementById("stopTestBtn");
  const nextBtn = document.getElementById("nextSentenceBtn");
  const quizSection = document.getElementById("quizSection");
  const videoSection = document.getElementById("videoSection");
  const lessonVideo = document.getElementById("lessonVideo");
  const quizProgress = document.getElementById("quizProgress");
  const targetSentenceText = document.getElementById("targetSentenceText");
  const expectedEl = document.getElementById("expectedText");
  const quizResult = document.getElementById("quizResult");
  const statusText = document.getElementById("statusText");
  const status = document.getElementById("testStatus");
  const waveformCanvas = document.getElementById("waveform");
  const waveformContainer = document.getElementById("waveformContainer");
  const silenceWarning = document.getElementById("silenceWarning");
  const wordChips = document.getElementById("wordChips");
  const aiFeedbackText = document.getElementById("aiFeedbackText");
  const finalSummary = document.getElementById("finalSummary");
  const totalSessionScore = document.getElementById("totalSessionScore");

  // Score display elements
  const overallScoreVal = document.getElementById("overallScoreVal");
  const overallFill = document.getElementById("overallFill");
  const phonemeScoreVal = document.getElementById("phonemeScoreVal");
  const phonemeFill = document.getElementById("phonemeFill");
  const fluencyScoreVal = document.getElementById("fluencyScoreVal");
  const fluencyFill = document.getElementById("fluencyFill");
  const rhythmScoreVal = document.getElementById("rhythmScoreVal");
  const rhythmFill = document.getElementById("rhythmFill");

  let sentences = [];
  let currentIdx = 0;
  let sessionScores = [];
  let recorder = null;
  let chunks = [];
  let micStream = null;
  let audioCtx = null;
  let analyser = null;
  let dataArray = null;
  let animationId = null;
  let lastAudioTime = Date.now();
  let wordCount = 0;
  let recording = false;

  const DEMO_MODE = Boolean(window.__DEMO_MODE__);
  const VIDEO_URL = window.__VIDEO_URL__;

  // 1. Detect Video Completion
  function initVideoDetection() {
    if (!lessonVideo) return;

    // Handle HTML5 Video
    if (lessonVideo.tagName === 'VIDEO') {
      lessonVideo.addEventListener('ended', onVideoEnd);
    } 
    // Handle YouTube (using API if available)
    else if (lessonVideo.tagName === 'IFRAME') {
      // The script in template handles YT API loading
      window.onYouTubeIframeAPIReady = () => {
        new YT.Player('lessonVideo', {
          events: {
            'onStateChange': (event) => {
              if (event.data === YT.PlayerState.ENDED) onVideoEnd();
            }
          }
        });
      };
    }
  }

  async function onVideoEnd() {
    console.log("Video ended, fetching sentences...");
    videoSection.classList.add("fadeOut");
    setTimeout(() => {
      videoSection.hidden = true;
      quizSection.hidden = false;
      quizSection.classList.add("fadeIn");
    }, 500);

    try {
      const res = await fetch('/api/sentences', {
        method: 'POST',
        body: JSON.stringify({ video_url: VIDEO_URL }),
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      sentences = data.sentences;
      startQuiz();
    } catch (e) {
      console.error("Failed to load sentences", e);
    }
  }

  // 2. Quiz Flow
  function startQuiz() {
    currentIdx = 0;
    sessionScores = [];
    showSentence();
  }

  function showSentence() {
    if (currentIdx >= sentences.length) {
      showFinalSummary();
      return;
    }

    quizProgress.textContent = `Sentence ${currentIdx + 1} of ${sentences.length}`;
    const sentence = sentences[currentIdx];
    targetSentenceText.textContent = `“${sentence}”`;
    expectedEl.dataset.expected = sentence;
    
    quizResult.hidden = true;
    takeBtn.hidden = false;
    takeBtn.disabled = false;
    takeBtn.textContent = "Start Recording";
    status.classList.add("testStatusHidden");
    statusText.textContent = "Ready";
  }

  // 3. Recording & Smart Stop
  async function startRecording() {
    if (recording) return;
    recording = true;
    chunks = [];
    wordCount = 0;
    lastAudioTime = Date.now();
    
    status.classList.remove("testStatusHidden");
    statusText.textContent = "Listening…";
    takeBtn.hidden = true;
    stopBtn.hidden = false;
    waveformContainer.hidden = false;

    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Visualizer
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioCtx.createAnalyser();
      const source = audioCtx.createMediaStreamSource(micStream);
      source.connect(analyser);
      analyser.fftSize = 2048;
      dataArray = new Uint8Array(analyser.frequencyBinCount);
      drawWaveform();

      recorder = new MediaRecorder(micStream);
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = processRecording;
      recorder.start();

      // Simple word detection simulation for smart stop
      // In a real app, we'd use continuous speech recognition here
      // For this implementation, we'll assume words are being spoken if volume is high
      const wordSim = setInterval(() => {
        if (!recording) {
          clearInterval(wordSim);
          return;
        }
        // Increment word count based on audio pulses (simplified)
        wordCount++; 
      }, 1000);

    } catch (e) {
      console.error(e);
      recording = false;
      statusText.textContent = "Mic error. Try again.";
    }
  }

  function stopRecording() {
    if (!recording) return;
    recording = false;
    if (recorder) recorder.stop();
    if (micStream) micStream.getTracks().forEach(t => t.stop());
    if (animationId) cancelAnimationFrame(animationId);
    if (audioCtx) audioCtx.close();
    waveformContainer.hidden = true;
    stopBtn.hidden = true;
    statusText.textContent = "Analyzing…";
  }

  async function processRecording() {
    const blob = new Blob(chunks, { type: 'audio/webm' });
    const fd = new FormData();
    fd.append('audio', blob);
    fd.append('expected', expectedEl.dataset.expected);

    try {
      const res = await fetch('/video-test/analyze', { method: 'POST', body: fd });
      const data = await res.json();
      showResult(data);
    } catch (e) {
      statusText.textContent = "Analysis failed. Try again.";
      takeBtn.hidden = false;
    }
  }

  function drawWaveform() {
    if (!recording) return;
    const ctx = waveformCanvas.getContext("2d");
    analyser.getByteTimeDomainData(dataArray);
    
    ctx.clearRect(0, 0, waveformCanvas.width, waveformCanvas.height);
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#2563eb";
    ctx.beginPath();
    
    const sliceWidth = waveformCanvas.width / dataArray.length;
    let x = 0;
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      const v = dataArray[i] / 128.0;
      const y = (v * waveformCanvas.height) / 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
      x += sliceWidth;
      sum += Math.abs(dataArray[i] - 128);
    }
    ctx.stroke();

    const volume = sum / dataArray.length;
    if (volume > 5) {
      lastAudioTime = Date.now();
      silenceWarning.hidden = true;
    } else if (Date.now() - lastAudioTime > 1500) {
      silenceWarning.hidden = false;
    }

    // Smart Stop: 1.8s silence + at least 3 words
    if (Date.now() - lastAudioTime > 1800 && wordCount >= 3) {
      stopRecording();
      return;
    }

    animationId = requestAnimationFrame(drawWaveform);
  }

  // 4. Results & Summary
  function showResult(data) {
    status.classList.add("testStatusHidden");
    quizResult.hidden = false;
    quizResult.classList.add("fadeIn");

    // Animate bars
    const scores = {
      overall: data.score * 10,
      phoneme: (data.score * 10) - 5, // Simulated breakdown for now
      fluency: (data.score * 10) + 2,
      rhythm: (data.score * 10) - 3
    };
    
    sessionScores.push(scores.overall);

    overallScoreVal.textContent = `${scores.overall}%`;
    overallFill.style.setProperty("--p", `${scores.overall}%`);
    phonemeScoreVal.textContent = `${scores.phoneme}%`;
    phonemeFill.style.setProperty("--p", `${scores.phoneme}%`);
    fluencyScoreVal.textContent = `${scores.fluency}%`;
    fluencyFill.style.setProperty("--p", `${scores.fluency}%`);
    rhythmScoreVal.textContent = `${scores.rhythm}%`;
    rhythmFill.style.setProperty("--p", `${scores.rhythm}%`);

    // Word Chips
    wordChips.innerHTML = "";
    const words = expectedEl.dataset.expected.split(" ");
    words.forEach(w => {
      const chip = document.createElement("span");
      chip.className = "wordChip chipGood"; // Simplified for now
      chip.textContent = w;
      wordChips.appendChild(chip);
    });

    aiFeedbackText.textContent = data.feedback ? data.feedback.join(". ") : "Good job! Focus on your intonation.";
  }

  function showFinalSummary() {
    quizResult.hidden = true;
    finalSummary.hidden = false;
    finalSummary.classList.add("fadeIn");
    
    const avg = Math.round(sessionScores.reduce((a, b) => a + b, 0) / sessionScores.length);
    totalSessionScore.textContent = avg;
  }

  // Event Listeners
  takeBtn.addEventListener("click", startRecording);
  stopBtn.addEventListener("click", stopRecording);
  nextBtn.addEventListener("click", () => {
    currentIdx++;
    showSentence();
  });

  initVideoDetection();
})();
