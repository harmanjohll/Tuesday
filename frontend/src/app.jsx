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

  // Short filler phrases to bridge TTS latency
  const PRIMERS = ["Right.", "One moment.", "Let me see.", "Okay.", "Sure."];

  const playPrimer = () => {
    if (!("speechSynthesis" in window)) return;
    const phrase = PRIMERS[Math.floor(Math.random() * PRIMERS.length)];
    const utter = new SpeechSynthesisUtterance(phrase);
    utter.rate = 0.95;
    utter.pitch = 0.9;
    utter.volume = 0.6; // subtle, not jarring
    // Try to pick a deeper voice
    const voices = speechSynthesis.getVoices();
    const deep = voices.find((v) => /daniel|alex|tom|james/i.test(v.name));
    if (deep) utter.voice = deep;
    speechSynthesis.speak(utter);
  };

  const speakResponse = (text) => {
    // Fire-and-forget: don't await this. User can keep chatting while Tuesday speaks.
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000); // 15s timeout

    setTuesdayState("speaking");

    // Instant filler while ElevenLabs loads
    playPrimer();

    fetch("/chat/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal: controller.signal,
    })
      .then((res) => {
        clearTimeout(timeout);
        if (!res.ok) throw new Error(`TTS returned ${res.status}`);
        return res.blob();
      })
      .then((blob) => {
        if (blob.size < 100) throw new Error("TTS returned empty audio");
        const url = URL.createObjectURL(blob);
        // Stop browser filler voice when real audio arrives
        if ("speechSynthesis" in window) speechSynthesis.cancel();

        const audio = new Audio(url);
        audioRef.current = audio;

        audio.onended = () => {
          setTuesdayState("idle");
          URL.revokeObjectURL(url);
        };
        audio.onerror = () => {
          setTuesdayState("idle");
          URL.revokeObjectURL(url);
        };

        return audio.play();
      })
      .catch((err) => {
        clearTimeout(timeout);
        console.warn("TTS unavailable:", err.message);
        setTuesdayState("idle");
      });
  };

  const sendMessage = async (text) => {
    if (!text.trim() || tuesdayState === "thinking") return;

    // If Tuesday is speaking and user sends a new message, stop everything
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if ("speechSynthesis" in window) speechSynthesis.cancel();

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

    // Try TTS in background (fire-and-forget). If it fails, user won't notice.
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
    if (isListening) {
      setTuesdayState("listening");
    } else if (tuesdayState === "listening") {
      setTuesdayState("idle");
    }
  };

  // Only block input while thinking. Speaking doesn't block - user can interrupt.
  const isBusy = tuesdayState === "thinking";

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
