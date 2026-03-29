(() => {
  const micBtn = document.getElementById("chatMic");
  const micLabel = document.getElementById("micLabel");
  const wave = document.getElementById("wave");
  const wrap = document.getElementById("chatWrap");
  const cont = document.getElementById("chatContinue");
  const promptChips = document.getElementById("promptChips");
  const textInput = document.getElementById("chatTextInput");
  const sendBtn = document.getElementById("chatSend");
  const miniLoad = document.getElementById("chatMiniLoad");
  const miniLoadText = document.getElementById("chatMiniLoadText");

  const DEMO_MODE = Boolean(window.__DEMO_MODE__);
  const debug = () => {};

  let recorder = null;
  let chunks = [];
  let micStream = null;
  let recording = false;

  const replies = [
    "Great! Try speaking a bit slower.",
    "Nice pronunciation! Repeat: 'Thank you for your time.'",
    "Focus on 'th' sound. Repeat: 'Thanks for the update.'",
    "I'm doing great! Let's practice your pronunciation.",
  ];

  function addBubble(role, text) {
    const el = document.createElement("div");
    el.className = `chatBubble ${role === "user" ? "chatU" : "chatA"}`;
    el.innerHTML = `<div class="chatMeta">${role === "user" ? "You" : "AI"}</div><div class="chatText"></div>`;
    el.querySelector(".chatText").textContent = text;
    wrap.appendChild(el);
    wrap.scrollTop = wrap.scrollHeight;
  }

  function stepActive(el) {
    if (!el) return;
    el.classList.add("aiStepActive");
  }

  function showMini(text) {
    if (miniLoad) miniLoad.hidden = false;
    if (miniLoadText) miniLoadText.textContent = text || "AI is replying…";
  }

  function hideMini() {
    if (miniLoad) miniLoad.hidden = true;
  }

  async function start() {
    if (recording) return;
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      debug(e);
      addBubble("ai", "Microphone permission denied. Please allow microphone access.");
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
      addBubble("ai", "Recording is not supported in this browser.");
      if (micStream) micStream.getTracks().forEach((t) => t.stop());
      micStream = null;
      return;
    }

    chunks = [];
    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data);
    };
    recorder.onstop = async () => {
      const blob = new Blob(chunks, { type: "audio/webm" });
      if (micStream) micStream.getTracks().forEach((t) => t.stop());
      micStream = null;
      await handleBlob(blob);
    };
    recorder.start();
    recording = true;
    micLabel.textContent = "Stop";
    if (wave) wave.classList.add("waveActive");
    micBtn.classList.add("micBtnActive");
  }

  function stop() {
    if (!recording) return;
    recording = false;
    micLabel.textContent = "Start";
    if (wave) wave.classList.remove("waveActive");
    micBtn.classList.remove("micBtnActive");
    try {
      recorder.stop();
    } catch (e) {
      debug(e);
    }
  }

  async function handleBlob(blob) {
    showMini("Analyzing…");
    const startedAt = Date.now();
    let payload = null;
    try {
      if (DEMO_MODE) {
        payload = { user: "How are you?", ai: replies[Math.floor(Math.random() * replies.length)] };
      } else {
        const fd = new FormData();
        fd.append("audio", new File([blob], "voice.webm", { type: "audio/webm" }));
        const res = await fetch("/ai-conversation/upload", { method: "POST", body: fd });
        payload = await res.json().catch(() => null);
      }
    } catch (e) {
      debug(e);
      payload = { user: "How are you?", ai: replies[Math.floor(Math.random() * replies.length)] };
    }

    const minMs = 180;
    const elapsed = Date.now() - startedAt;
    const wait = Math.max(0, minMs - elapsed);
    setTimeout(() => {
      hideMini();
      const userText = (payload && payload.user) || "How are you?";
      const aiText = (payload && payload.ai) || replies[Math.floor(Math.random() * replies.length)];
      addBubble("user", userText);
      addBubble("ai", aiText);
    }, wait);
  }

  async function sendText(text) {
    const t = String(text || "").trim();
    if (!t) return;
    if (textInput) textInput.value = "";
    addBubble("user", t);
    showMini("AI is replying…");
    let payload = null;
    try {
      if (DEMO_MODE) {
        payload = { user: t, ai: replies[Math.floor(Math.random() * replies.length)] };
      } else {
        const res = await fetch("/ai-conversation/text", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: t }),
        });
        payload = await res.json().catch(() => null);
      }
    } catch (e) {
      debug(e);
      payload = { user: t, ai: replies[Math.floor(Math.random() * replies.length)] };
    }
    const aiText = (payload && payload.ai) || replies[Math.floor(Math.random() * replies.length)];
    setTimeout(() => {
      hideMini();
      addBubble("ai", aiText);
    }, 180);
  }

  if (micBtn)
    micBtn.addEventListener("click", () => {
      if (recording) stop();
      else start();
    });

  if (cont)
    cont.addEventListener("click", () => {
      addBubble("ai", "Continue by saying another short sentence.");
    });

  if (promptChips)
    promptChips.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-prompt]");
      if (!btn) return;
      const p = btn.getAttribute("data-prompt") || "";
      if (textInput) {
        textInput.value = p;
        textInput.focus();
      }
    });

  if (sendBtn)
    sendBtn.addEventListener("click", () => {
      sendText(textInput ? textInput.value : "");
    });

  if (textInput)
    textInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        sendText(textInput.value);
      }
    });

  window.addEventListener("beforeunload", () => {
    try {
      if (micStream) micStream.getTracks().forEach((t) => t.stop());
    } catch {}
  });
})();
