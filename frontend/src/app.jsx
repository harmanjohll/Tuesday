import { useState, useRef, useEffect } from "preact/hooks";
import { VoiceInput } from "./voice.jsx";
import { QuantumField } from "./particles.jsx";

// Filler phrases to pre-cache with ElevenLabs voice
const FILLER_PHRASES = ["Right.", "One moment.", "Let me think.", "Sure.", "Okay."];

export function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [tuesdayState, setTuesdayState] = useState("idle");
  const messagesEnd = useRef(null);
  const audioRef = useRef(null);
  const fillerCacheRef = useRef([]); // pre-cached filler audio blobs
  const fillerLoadedRef = useRef(false);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Pre-cache filler phrases using ElevenLabs voice on first load
  useEffect(() => {
    if (fillerLoadedRef.current) return;
    fillerLoadedRef.current = true;

    FILLER_PHRASES.forEach((phrase) => {
      fetch("/chat/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: phrase }),
      })
        .then((res) => {
          if (!res.ok) return null;
          return res.blob();
        })
        .then((blob) => {
          if (blob && blob.size > 100) {
            fillerCacheRef.current.push(blob);
          }
        })
        .catch(() => {}); // silently fail — fillers are optional
    });
  }, []);

  const playFiller = () => {
    const cache = fillerCacheRef.current;
    if (cache.length === 0) return; // no fillers cached yet

    const blob = cache[Math.floor(Math.random() * cache.length)];
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.volume = 0.8;
    audio.onended = () => URL.revokeObjectURL(url);
    audio.onerror = () => URL.revokeObjectURL(url);
    audio.play().catch(() => {});
  };

  const speakResponse = (text) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);

    setTuesdayState("speaking");

    // Play a cached filler in Tuesday's actual voice while full TTS loads
    playFiller();

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
        const audio = new Audio(url);
        audioRef.current = audio;

        audio.onended = () => {
          setTuesdayState("idle");
          URL.revokeObjectURL(url);
          audioRef.current = null;
        };
        audio.onerror = () => {
          setTuesdayState("idle");
          URL.revokeObjectURL(url);
          audioRef.current = null;
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

    // If Tuesday is speaking, stop audio
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
    // Only update visual state if we're idle (don't override thinking/speaking)
    if (isListening && tuesdayState === "idle") {
      setTuesdayState("listening");
    } else if (!isListening && tuesdayState === "listening") {
      setTuesdayState("idle");
    }
  };

  const isBusy = tuesdayState === "thinking";

  // Pause mic while thinking or speaking (avoids picking up TTS audio)
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
        <VoiceInput
          onTranscript={handleVoiceTranscript}
          onListeningChange={handleListeningChange}
          paused={micPaused}
        />
      </footer>
    </div>
  );
}
