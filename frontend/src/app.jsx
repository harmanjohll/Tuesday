import { useState, useRef, useEffect } from "preact/hooks";
import { VoiceButton } from "./voice.jsx";

export function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const messagesEnd = useRef(null);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text) => {
    if (!text.trim() || streaming) return;

    const userMsg = { role: "user", content: text.trim() };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput("");
    setStreaming(true);

    // Add empty assistant message that we'll stream into
    const assistantMsg = { role: "assistant", content: "" };
    setMessages([...updatedMessages, assistantMsg]);

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: updatedMessages }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let fullResponse = "";

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
          if (line.startsWith("event:done")) {
            break;
          }
        }
      }
    } catch (err) {
      setMessages([
        ...updatedMessages,
        { role: "assistant", content: "Connection lost. Try again." },
      ]);
    }

    setStreaming(false);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleVoiceTranscript = (transcript) => {
    sendMessage(transcript);
  };

  return (
    <div class="tuesday">
      <header class="header">
        <div class="header-mark">T</div>
        <span class="header-name">Tuesday</span>
        <div class="header-status">
          <span class={`dot ${streaming ? "active" : "idle"}`} />
          {streaming ? "thinking" : "online"}
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
            disabled={streaming}
            autofocus
          />
          <button type="submit" disabled={streaming || !input.trim()} class="send-btn">
            &uarr;
          </button>
        </form>
        <VoiceButton onTranscript={handleVoiceTranscript} disabled={streaming} />
      </footer>
    </div>
  );
}
