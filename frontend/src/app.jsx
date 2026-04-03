import { useState, useRef, useEffect } from "preact/hooks";
import { VoiceInput } from "./voice.jsx";
import { QuantumField } from "./particles.jsx";

export function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [tuesdayState, setTuesdayState] = useState("idle");
  const messagesEnd = useRef(null);
  const audioRef = useRef(null);
  const audioUnlockedRef = useRef(false);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Unlock audio playback on first user interaction.
  // Chrome blocks audio.play() until the user has clicked/tapped/typed.
  // Playing a silent buffer on first interaction permanently unlocks audio.
  useEffect(() => {
    const unlock = () => {
      if (audioUnlockedRef.current) return;
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const buf = ctx.createBuffer(1, 1, 22050);
      const src = ctx.createBufferSource();
      src.buffer = buf;
      src.connect(ctx.destination);
      src.start(0);
      audioUnlockedRef.current = true;
      ctx.close();
    };
    document.addEventListener("click", unlock, { once: true });
    document.addEventListener("keydown", unlock, { once: true });
    document.addEventListener("touchstart", unlock, { once: true });
    return () => {
      document.removeEventListener("click", unlock);
      document.removeEventListener("keydown", unlock);
      document.removeEventListener("touchstart", unlock);
    };
  }, []);

  const speakResponse = (text) => {
    setTuesdayState("speaking");

    fetch("/chat/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    })
      .then(async (res) => {
        if (!res.ok) {
          const errorBody = await res.text().catch(() => "unknown");
          throw new Error(`TTS ${res.status}: ${errorBody}`);
        }
        return res.blob();
      })
      .then((blob) => {
        if (blob.size < 200) {
          throw new Error(`TTS too small (${blob.size} bytes)`);
        }
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audioRef.current = audio;

        const cleanup = () => {
          setTuesdayState("idle");
          URL.revokeObjectURL(url);
          audioRef.current = null;
        };

        audio.onended = cleanup;
        audio.onerror = cleanup;

        return audio.play();
      })
      .catch((err) => {
        console.warn("TTS failed:", err.message);
        setTuesdayState("idle");
      });
  };

  const sendMessage = async (text) => {
    if (!text.trim() || tuesdayState === "thinking") return;

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    const userMsg = { role: "user", content: text.trim() };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput("");
    setTuesdayState("thinking");

    setMessages([...updatedMessages, { role: "assistant", content: "" }]);

    let fullResponse = "";

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: updatedMessages }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data:")) {
            const data = line.slice(5).trim();
            if (data) {
              fullResponse += data;
              setMessages([
                ...updatedMessages,
                { role: "assistant", content: fullResponse },
              ]);
            }
          }
        }
      }
    } catch (err) {
      fullResponse = "Connection lost. Try again.";
      setMessages([
        ...updatedMessages,
        { role: "assistant", content: fullResponse },
      ]);
    }

    if (fullResponse && fullResponse !== "Connection lost. Try again.") {
      speakResponse(fullResponse);
    } else {
      setTuesdayState("idle");
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleVoiceTranscript = (transcript) => {
    sendMessage(transcript);
  };

  const handleListeningChange = (isListening) => {
    if (isListening && tuesdayState === "idle") {
      setTuesdayState("listening");
    } else if (!isListening && tuesdayState === "listening") {
      setTuesdayState("idle");
    }
  };

  const isBusy = tuesdayState === "thinking";
  const micPaused = tuesdayState === "thinking" || tuesdayState === "speaking";

  const stateLabel = {
    idle: "online",
    listening: "listening",
    thinking: "thinking",
    speaking: "speaking",
  };

  const dotClass = tuesdayState === "idle" ? "idle" : tuesdayState;

  return (
    <div class="tuesday">
      <QuantumField state={tuesdayState} />

      <header class="header">
        <div class="header-mark">T</div>
        <span class="header-name">Tuesday</span>
        <div class="header-status">
          <span class={`dot ${dotClass}`} />
          {stateLabel[tuesdayState]}
        </div>
      </header>

      <div class="chat-window">
        <div class="messages">
          {messages.map((msg, i) => (
            <div key={i} class={`message ${msg.role}`}>
              <div class="message-content">{msg.content}</div>
            </div>
          ))}
          <div ref={messagesEnd} />
        </div>

        <div class="input-bar">
          <form onSubmit={handleSubmit} class="input-form">
            <input
              type="text"
              value={input}
              onInput={(e) => setInput(e.target.value)}
              placeholder="Talk to Tuesday..."
              disabled={isBusy}
              autofocus
            />
            <button type="submit" disabled={isBusy || !input.trim()} class="send-btn">
              &uarr;
            </button>
          </form>
          <VoiceInput
            onTranscript={handleVoiceTranscript}
            onListeningChange={handleListeningChange}
            paused={micPaused}
          />
        </div>
      </div>
    </div>
  );
}
