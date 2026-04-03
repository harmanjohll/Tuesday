import { useState, useRef, useEffect } from "preact/hooks";
import { VoiceButton } from "./voice.jsx";
import { QuantumField } from "./particles.jsx";

export function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [tuesdayState, setTuesdayState] = useState("idle"); // idle | listening | thinking | speaking
  const messagesEnd = useRef(null);
  const audioRef = useRef(null);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const speakResponse = async (text) => {
    try {
      setTuesdayState("speaking");
      const res = await fetch("/chat/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      if (!res.ok) {
        console.warn("TTS unavailable, skipping voice output");
        setTuesdayState("idle");
        return;
      }

      const audioBlob = await res.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      audio.onended = () => {
        setTuesdayState("idle");
        URL.revokeObjectURL(audioUrl);
      };

      audio.onerror = () => {
        setTuesdayState("idle");
        URL.revokeObjectURL(audioUrl);
      };

      await audio.play();
    } catch (err) {
      console.warn("TTS error:", err);
      setTuesdayState("idle");
    }
  };

  const sendMessage = async (text) => {
    if (!text.trim() || tuesdayState === "thinking" || tuesdayState === "speaking") return;

    const userMsg = { role: "user", content: text.trim() };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput("");
    setTuesdayState("thinking");

    // Add empty assistant message that we'll stream into
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

    // Try to speak the response (TTS). Falls back gracefully if no API key.
    if (fullResponse && fullResponse !== "Connection lost. Try again.") {
      await speakResponse(fullResponse);
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
    if (isListening) {
      setTuesdayState("listening");
    } else if (tuesdayState === "listening") {
      setTuesdayState("idle");
    }
  };

  const isBusy = tuesdayState === "thinking" || tuesdayState === "speaking";

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

      <main class="messages">
        {messages.length === 0 && (
          <div class="empty-state">
            <div class="empty-mark">T</div>
            <p>Tuesday is online.</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} class={`message ${msg.role}`}>
            <div class="message-content">{msg.content}</div>
          </div>
        ))}
        <div ref={messagesEnd} />
      </main>

      <footer class="input-bar">
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
        <VoiceButton
          onTranscript={handleVoiceTranscript}
          onListeningChange={handleListeningChange}
          disabled={isBusy}
        />
      </footer>
    </div>
  );
}
