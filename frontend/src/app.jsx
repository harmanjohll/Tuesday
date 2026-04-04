import { useState, useRef, useEffect } from "preact/hooks";
import { VoiceInput } from "./voice.jsx";
import { QuantumField } from "./particles.jsx";

function getOrCreateSessionId() {
  let id = localStorage.getItem("tuesday_session_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("tuesday_session_id", id);
  }
  return id;
}

function getAuthToken() {
  return localStorage.getItem("tuesday_auth_token") || "";
}

function authHeaders() {
  const token = getAuthToken();
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

export function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [tuesdayState, setTuesdayState] = useState("idle");
  const [toolStatus, setToolStatus] = useState(null);
  const [needsUnlock, setNeedsUnlock] = useState(false);
  const [sessionId, setSessionId] = useState(getOrCreateSessionId);
  const messagesEnd = useRef(null);
  const audioRef = useRef(null);
  const pendingAudioRef = useRef(null);
  const abortRef = useRef(null);       // AbortController for active stream
  const ttsAbortRef = useRef(null);     // AbortController for TTS fetch
  const interruptCooldownRef = useRef(false); // Ignore echo after voice interrupt

  // Load session history on mount
  useEffect(() => {
    if (!sessionId) return;
    fetch(`/sessions/${sessionId}`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.messages?.length) {
          const displayMsgs = data.messages
            .filter((m) => typeof m.content === "string")
            .map((m) => ({ role: m.role, content: m.content }));
          setMessages(displayMsgs);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const stopEverything = () => {
    // Abort active SSE stream
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    // Abort TTS fetch
    if (ttsAbortRef.current) {
      ttsAbortRef.current.abort();
      ttsAbortRef.current = null;
    }
    // Stop audio playback
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current = null;
    }
    // Clear pending audio
    if (pendingAudioRef.current) {
      URL.revokeObjectURL(pendingAudioRef.current.url);
      pendingAudioRef.current = null;
    }
    setNeedsUnlock(false);
    setToolStatus(null);
    setTuesdayState("idle");
    // Cooldown: ignore voice input for 1s after interrupt (avoids echo)
    interruptCooldownRef.current = true;
    setTimeout(() => { interruptCooldownRef.current = false; }, 1000);
  };

  const clearChat = (e) => {
    e.stopPropagation();
    stopEverything();
    setMessages([]);
    // Session ID stays the same — knowledge persists in .md files
  };

  const playAudio = (blob) => {
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

    const playPromise = audio.play();
    if (playPromise) {
      playPromise.catch(() => {
        pendingAudioRef.current = { audio, url };
        setNeedsUnlock(true);
      });
    }
  };

  const unlockAndPlay = () => {
    const pending = pendingAudioRef.current;
    if (pending) {
      pendingAudioRef.current = null;
      setNeedsUnlock(false);
      pending.audio.play().catch(() => {
        setTuesdayState("idle");
        URL.revokeObjectURL(pending.url);
      });
    }
  };

  const speakResponse = (text) => {
    setTuesdayState("speaking");

    const controller = new AbortController();
    ttsAbortRef.current = controller;

    fetch("/chat/speak", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ text }),
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) {
          const errorBody = await res.text().catch(() => "unknown");
          throw new Error(`TTS ${res.status}: ${errorBody}`);
        }
        return res.blob();
      })
      .then((blob) => {
        ttsAbortRef.current = null;
        if (blob.size < 200) {
          throw new Error(`TTS too small (${blob.size} bytes)`);
        }
        playAudio(blob);
      })
      .catch((err) => {
        ttsAbortRef.current = null;
        if (err.name !== "AbortError") {
          console.warn("TTS failed:", err.message);
        }
        // Only reset to idle if we weren't interrupted for a new message
        if (tuesdayState === "speaking") {
          setTuesdayState("idle");
        }
      });
  };

  const sendMessage = async (text) => {
    if (!text.trim()) return;

    // If Tuesday is busy, interrupt first
    stopEverything();

    const userMsg = { role: "user", content: text.trim() };
    const updatedMessages = [...messages, userMsg];
    // Remove any empty assistant message from a previous interrupted stream
    const cleanMessages = updatedMessages.filter(
      (m) => !(m.role === "assistant" && m.content === "")
    );
    setMessages(cleanMessages);
    setInput("");
    setTuesdayState("thinking");
    setToolStatus(null);

    setMessages([...cleanMessages, { role: "assistant", content: "" }]);

    let fullResponse = "";
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          messages: cleanMessages,
          session_id: sessionId,
        }),
        signal: controller.signal,
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
          if (line.startsWith("event:")) {
            var currentEvent = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            const data = line.slice(5).trim();
            if (currentEvent === "token" && data) {
              fullResponse += data;
              setMessages([
                ...cleanMessages,
                { role: "assistant", content: fullResponse },
              ]);
            } else if (currentEvent === "tool_status" && data) {
              setToolStatus(data);
            } else if (currentEvent === "done") {
              setToolStatus(null);
            }
          }
        }
      }
    } catch (err) {
      if (err.name === "AbortError") {
        // User interrupted — keep whatever we got so far
        if (fullResponse) {
          setMessages([
            ...cleanMessages,
            { role: "assistant", content: fullResponse + " ..." },
          ]);
        }
        return; // Don't speak, don't change state (stopEverything already handled it)
      }
      fullResponse = "Connection lost. Try again.";
      setMessages([
        ...cleanMessages,
        { role: "assistant", content: fullResponse },
      ]);
    }

    abortRef.current = null;
    setToolStatus(null);

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
    // Voice detected while Tuesday is speaking — interrupt, don't send
    if (tuesdayState === "speaking") {
      stopEverything();
      return;
    }
    // Ignore echo shortly after an interrupt
    if (interruptCooldownRef.current) return;
    sendMessage(transcript);
  };

  const handleListeningChange = (isListening) => {
    if (isListening && tuesdayState === "idle") {
      setTuesdayState("listening");
    } else if (!isListening && tuesdayState === "listening") {
      setTuesdayState("idle");
    }
  };

  const isActive = tuesdayState === "thinking" || tuesdayState === "speaking";
  // Only pause mic during thinking — keep it on during speaking for voice interrupt
  const micPaused = tuesdayState === "thinking";

  const stateLabel = {
    idle: "online",
    listening: "listening",
    thinking: "thinking",
    speaking: "speaking",
  };

  const dotClass = tuesdayState === "idle" ? "idle" : tuesdayState;

  return (
    <div class="tuesday" onClick={unlockAndPlay}>
      <QuantumField state={tuesdayState} />

      <header class="header">
        <div class="header-mark">T</div>
        <span class="header-name">Tuesday</span>
        <div class="header-status">
          <span class={`dot ${dotClass}`} />
          {stateLabel[tuesdayState]}
        </div>
        {isActive && (
          <button
            class="stop-btn"
            onClick={(e) => { e.stopPropagation(); stopEverything(); }}
            title="Stop Tuesday"
          >
            Stop
          </button>
        )}
        <button
          class="clear-chat-btn"
          onClick={clearChat}
          title="Clear chat"
        >
          &times;
        </button>
      </header>

      <div class="chat-window">
        {needsUnlock && (
          <div class="unlock-hint">Tap anywhere to hear Tuesday's voice</div>
        )}
        <div class="messages">
          {messages.map((msg, i) => (
            <div key={i} class={`message ${msg.role}`}>
              <div class="message-content">{msg.content}</div>
            </div>
          ))}
          {toolStatus && (
            <div class="tool-status">{toolStatus}</div>
          )}
          <div ref={messagesEnd} />
        </div>

        <div class="input-bar">
          <form onSubmit={handleSubmit} class="input-form">
            <input
              type="text"
              value={input}
              onInput={(e) => setInput(e.target.value)}
              placeholder="Talk to Tuesday..."
              autofocus
            />
            <button type="submit" disabled={!input.trim()} class="send-btn">
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
