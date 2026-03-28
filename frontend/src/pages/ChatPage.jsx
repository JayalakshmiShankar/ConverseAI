import { useMemo, useState } from "react";
import { api } from "../lib/api";
import { getSelectedLanguage } from "../lib/state";
import { AudioRecorder } from "../components/AudioRecorder";

function speak(text) {
  try {
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1;
    u.pitch = 1;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  } catch {
    return;
  }
}

export function ChatPage() {
  const language = useMemo(() => getSelectedLanguage(), []);
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Say a short business phrase. I will reply with a new phrase to repeat." },
  ]);
  const [text, setText] = useState("");
  const [audioBlob, setAudioBlob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const add = (role, t) => setMessages((m) => [...m, { role, text: t }]);

  const sendText = async () => {
    setError("");
    if (!language) {
      setError("Select a language first.");
      return;
    }
    if (!text.trim()) return;
    const userText = text.trim();
    setText("");
    add("user", userText);
    setLoading(true);
    try {
      const res = await api.chat({ language, userText });
      add("assistant", res.assistant_text);
      speak(res.assistant_text);
    } catch (e) {
      setError(e.message || "Chat failed");
    } finally {
      setLoading(false);
    }
  };

  const sendVoice = async () => {
    setError("");
    if (!language) {
      setError("Select a language first.");
      return;
    }
    if (!audioBlob) {
      setError("Record a voice message first.");
      return;
    }
    setLoading(true);
    try {
      const file = new File([audioBlob], "voice.webm", { type: "audio/webm" });
      const analysis = await api.createSession({ language, referenceText: "", mouthMetrics: null, audioFile: file });
      add("user", analysis.transcript);
      const res = await api.chat({ language, userText: analysis.transcript });
      add("assistant", res.assistant_text);
      speak(res.assistant_text);
    } catch (e) {
      setError(e.message || "Voice flow failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="pageTitle">AI Conversation Bot</div>
      <div className="muted">
        Selected language: <span className="chip">{language || "Not selected"}</span>
      </div>
      {error ? <div className="error">{error}</div> : null}

      <div className="card">
        <div className="chatLog">
          {messages.map((m, idx) => (
            <div className={`chatMsg ${m.role === "assistant" ? "chatA" : "chatU"}`} key={`${idx}-${m.role}`}>
              <div className="chatRole">{m.role === "assistant" ? "AI" : "You"}</div>
              <div className="chatText">{m.text}</div>
            </div>
          ))}
        </div>

        <div className="chatRow">
          <input
            className="input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type a phrase..."
            onKeyDown={(e) => (e.key === "Enter" ? sendText() : null)}
          />
          <button className="primaryBtn" type="button" disabled={loading} onClick={sendText}>
            Send
          </button>
        </div>
      </div>

      <div className="grid2">
        <AudioRecorder onAudioReady={(b) => setAudioBlob(b)} />
        <div className="card">
          <div className="cardTitle">Real-time Loop</div>
          <div className="muted">
            Record a short phrase → AI replies → repeat the phrase. Each voice message runs speech-to-text with your selected language.
          </div>
          <div className="rowButtons">
            <button className="primaryBtn" type="button" disabled={loading} onClick={sendVoice}>
              Send voice
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
