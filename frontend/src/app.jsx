import { useState, useRef, useEffect } from "preact/hooks";
import { VoiceInput } from "./voice.jsx";
import { QuantumField } from "./particles.jsx";
import { MindCastle } from "./mindcastle.jsx";

function getOrCreateSessionId() {
  let id = localStorage.getItem("tuesday_session_id");
  if (!id) {
    id = (crypto.randomUUID?.() ??
      ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
        (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)));
    localStorage.setItem("tuesday_session_id", id);
  }
  return id;
}

function getAuthToken() {
  // Check URL for token param (easy mobile setup)
  const params = new URLSearchParams(window.location.search);
  const urlToken = params.get("token");
  if (urlToken) {
    localStorage.setItem("tuesday_auth_token", urlToken);
    // Clean the URL so token isn't visible
    window.history.replaceState({}, "", window.location.pathname);
    return urlToken;
  }
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
  const [attachment, setAttachment] = useState(null); // { filename, content_block }
  const [activePanel, setActivePanel] = useState("tuesday"); // "tuesday" | "mindcastle"
  const [ttsEnabled, setTtsEnabled] = useState(() => localStorage.getItem("tuesday_tts") !== "off");
  const fileInputRef = useRef(null);
  const messagesEnd = useRef(null);
  const audioRef = useRef(null);
  const pendingAudioRef = useRef(null);
  const abortRef = useRef(null);       // AbortController for active stream
  const ttsAbortRef = useRef(null);     // AbortController for TTS fetch
  const interruptCooldownRef = useRef(false); // Ignore echo after voice interrupt
  const touchStartRef = useRef(null);    // Swipe gesture tracking

  // Load session history and proactive greeting on mount
  useEffect(() => {
    // Proactive context-aware greeting (replaces static morning briefing)
    fetch("/session-start", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({}),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.content) {
          setMessages((prev) => [
            { role: "assistant", content: data.content },
            ...prev,
          ]);
        }
      })
      .catch(() => {});

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

  // Recover from tab switches — browser kills SSE when tab is hidden
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden && tuesdayState === "thinking") {
        // Tab became visible while Tuesday was mid-response
        if (!abortRef.current || abortRef.current.signal.aborted) {
          // Stream was killed — reset state so user can resend
          setTuesdayState("idle");
          setToolStatus(null);
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant" && last.content === "") {
              return prev.slice(0, -1);
            }
            return prev;
          });
        }
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, [tuesdayState]);

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

  const toggleTts = () => {
    setTtsEnabled(prev => {
      const next = !prev;
      localStorage.setItem("tuesday_tts", next ? "on" : "off");
      if (!next) stopEverything();
      return next;
    });
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

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      setToolStatus(`Uploading ${file.name}...`);
      const res = await fetch("/documents/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${getAuthToken()}` },
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setToolStatus(null);
        alert(err.detail || "Upload failed");
        return;
      }
      const data = await res.json();
      setAttachment({ filename: data.filename, content_block: data.content_block });
      setToolStatus(null);
    } catch (err) {
      setToolStatus(null);
      console.error("Upload failed:", err);
    }
    // Reset file input so the same file can be selected again
    e.target.value = "";
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
      const payload = {
        messages: cleanMessages,
        session_id: sessionId,
      };
      // Include attachment if present
      if (attachment) {
        payload.attachments = [attachment.content_block];
        setAttachment(null);
      }
      const res = await fetch("/chat", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(payload),
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
      if (ttsEnabled) {
        speakResponse(fullResponse);
      } else {
        setTuesdayState("idle");
      }
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

  // Swipe gesture: swipe left → Mind Castle, swipe right → Tuesday
  const handleTouchStart = (e) => {
    touchStartRef.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
  };
  const handleTouchEnd = (e) => {
    if (!touchStartRef.current) return;
    const dx = e.changedTouches[0].clientX - touchStartRef.current.x;
    const dy = e.changedTouches[0].clientY - touchStartRef.current.y;
    touchStartRef.current = null;
    // Only trigger on horizontal swipes (dx > 80px, and more horizontal than vertical)
    if (Math.abs(dx) > 80 && Math.abs(dx) > Math.abs(dy) * 1.5) {
      if (dx < 0 && activePanel === "tuesday") setActivePanel("mindcastle");
      if (dx > 0 && activePanel === "mindcastle") setActivePanel("tuesday");
    }
  };

  const isActive = tuesdayState === "thinking" || tuesdayState === "speaking";
  // Pause mic during thinking AND speaking to prevent echo loops
  const micPaused = tuesdayState === "thinking" || tuesdayState === "speaking";

  const stateLabel = {
    idle: "online",
    listening: "listening",
    thinking: "thinking",
    speaking: "speaking",
  };

  const dotClass = tuesdayState === "idle" ? "idle" : tuesdayState;

  // Parse message content for download links (DOWNLOAD:/path|filename|description)
  const renderMessageContent = (content) => {
    const downloadPattern = /DOWNLOAD:(\/documents\/download\/[a-f0-9_]+)\|([^|]+)\|([^\n]+)/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = downloadPattern.exec(content)) !== null) {
      if (match.index > lastIndex) {
        parts.push(content.slice(lastIndex, match.index));
      }
      const [, path, filename, desc] = match;
      parts.push(
        <a
          key={match.index}
          href={path}
          download={filename}
          class="download-link"
          onClick={(e) => e.stopPropagation()}
        >
          {"\u{1F4E5}"} {filename}
        </a>
      );
      lastIndex = match.index + match[0].length;
    }

    if (parts.length === 0) return content;
    if (lastIndex < content.length) {
      parts.push(content.slice(lastIndex));
    }
    return parts;
  };

  return (
    <div
      class="panel-container"
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      {/* Panel toggle */}
      <div class="panel-tabs">
        <button class={`panel-tab ${activePanel === "tuesday" ? "active" : ""}`}
          onClick={() => setActivePanel("tuesday")}>Tuesday</button>
        <button class={`panel-tab ${activePanel === "mindcastle" ? "active" : ""}`}
          onClick={() => setActivePanel("mindcastle")}>Mind Castle</button>
      </div>

      <div class={`panel-slider ${activePanel === "mindcastle" ? "shifted" : ""}`}>
        {/* Tuesday Panel */}
        <div class="panel tuesday-panel">
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
              <div class="message-content">{msg.role === "assistant" ? renderMessageContent(msg.content) : msg.content}</div>
            </div>
          ))}
          {toolStatus && (
            <div class="tool-status">{toolStatus}</div>
          )}
          <div ref={messagesEnd} />
        </div>

        <div class="input-bar">
          {attachment && (
            <div class="attachment-chip">
              {attachment.filename}
              <button onClick={() => setAttachment(null)}>&times;</button>
            </div>
          )}
          <form onSubmit={handleSubmit} class="input-form">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".pdf,.jpg,.jpeg,.png,.gif,.webp,.txt"
              style={{ display: "none" }}
            />
            <button
              type="button"
              class="upload-btn"
              onClick={() => fileInputRef.current?.click()}
              title="Upload a document or image"
            >
              &#128206;
            </button>
            <textarea
              value={input}
              onInput={(e) => {
                setInput(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              placeholder={attachment ? `Ask about ${attachment.filename}...` : "Talk to Tuesday..."}
              rows={1}
              autofocus
            />
            <button type="submit" disabled={!input.trim() && !attachment} class="send-btn">
              &uarr;
            </button>
          </form>
          <VoiceInput
            onTranscript={handleVoiceTranscript}
            onListeningChange={handleListeningChange}
            paused={micPaused}
          />
          <button
            class={`speaker-btn ${!ttsEnabled ? "off" : ""}`}
            onClick={toggleTts}
            aria-label={ttsEnabled ? "Disable voice output" : "Enable voice output"}
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
              {ttsEnabled ? (
                <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" />
              ) : (
                <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" />
              )}
            </svg>
          </button>
        </div>
      </div>
          </div>
        </div>

        {/* Mind Castle Panel */}
        <div class="panel mindcastle-panel">
          <MindCastle onBack={() => setActivePanel("tuesday")} />
        </div>
      </div>
    </div>
  );
}
