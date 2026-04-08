import { useState, useEffect, useRef } from "preact/hooks";
import { AgentOrb } from "./agent-orb.jsx";

function getAuthToken() {
  return localStorage.getItem("tuesday_auth_token") || "";
}

function authHeaders() {
  const token = getAuthToken();
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

// Predefined colors for the color picker
const COLOR_OPTIONS = [
  "#FF6B6B", "#4ECDC4", "#FFE66D", "#A855F7",
  "#10B981", "#3B82F6", "#F43F5E", "#64748B",
];

export function MindCastle({ onBack }) {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const chatEndRef = useRef(null);

  // Create form state
  const [newName, setNewName] = useState("");
  const [newRole, setNewRole] = useState("");
  const [newColor, setNewColor] = useState(COLOR_OPTIONS[0]);

  const fetchAgents = () => {
    fetch("/agents", { headers: authHeaders() })
      .then((r) => r.ok ? r.json() : [])
      .then(setAgents)
      .catch(() => {});
  };

  useEffect(() => {
    fetchAgents();
    const interval = setInterval(fetchAgents, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const createAgent = async () => {
    if (!newName.trim() || !newRole.trim()) return;
    try {
      const res = await fetch("/agents", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ name: newName, role: newRole, color: newColor }),
      });
      if (res.ok) {
        setNewName("");
        setNewRole("");
        setShowCreate(false);
        fetchAgents();
      }
    } catch (e) {
      console.error("Failed to create agent:", e);
    }
  };

  const deleteAgent = async (agentId, e) => {
    e.stopPropagation();
    if (!confirm("Delete this agent?")) return;
    await fetch(`/agents/${agentId}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (selectedAgent?.id === agentId) {
      setSelectedAgent(null);
      setChatMessages([]);
    }
    fetchAgents();
  };

  const selectAgent = async (agent) => {
    setSelectedAgent(agent);
    setShowCreate(false);
    // Load full agent data including messages
    try {
      const res = await fetch(`/agents/${agent.id}`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setChatMessages(
          (data.messages || [])
            .filter((m) => typeof m.content === "string")
            .map((m) => ({ role: m.role, content: m.content }))
        );
      }
    } catch (e) {
      setChatMessages([]);
    }
  };

  const sendChat = async () => {
    if (!chatInput.trim() || !selectedAgent || isStreaming) return;
    const userMsg = { role: "user", content: chatInput.trim() };
    const updated = [...chatMessages, userMsg];
    setChatMessages(updated);
    setChatInput("");
    setIsStreaming(true);

    setChatMessages([...updated, { role: "assistant", content: "" }]);
    let fullResponse = "";

    try {
      const res = await fetch(`/agents/${selectedAgent.id}/chat`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ message: userMsg.content }),
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
              setChatMessages([
                ...updated,
                { role: "assistant", content: fullResponse },
              ]);
            } else if (currentEvent === "error" && data) {
              fullResponse += `\n\n⚠️ ${data}`;
              setChatMessages([
                ...updated,
                { role: "assistant", content: fullResponse || `Error: ${data}` },
              ]);
            }
          }
        }
      }
    } catch (e) {
      if (!fullResponse) {
        fullResponse = "Connection lost. Try again.";
        setChatMessages([
          ...updated,
          { role: "assistant", content: fullResponse },
        ]);
      }
    }

    setIsStreaming(false);
    fetchAgents(); // Refresh status
  };

  const approveAgent = async (agentId, e) => {
    e.stopPropagation();
    try {
      await fetch(`/agents/${agentId}/approve`, {
        method: "POST",
        headers: authHeaders(),
      });
      fetchAgents();
    } catch (err) {
      console.error("Failed to approve agent:", err);
    }
  };

  const retryAgent = async (agentId, e) => {
    e.stopPropagation();
    try {
      await fetch(`/agents/${agentId}/retry`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ instructions: "" }),
      });
      fetchAgents();
    } catch (err) {
      console.error("Failed to retry agent:", err);
    }
  };

  const statusLabel = (s) => {
    const labels = {
      idle: "Idle",
      working: "Working...",
      done: "Done",
      needs_review: "Needs Review",
      failed: "Failed",
      error: "Error",
    };
    return labels[s] || s;
  };

  return (
    <div class="mind-castle">
      <header class="mc-header">
        <button class="mc-back-btn" onClick={onBack}>
          &larr;
        </button>
        <span class="mc-title">Mind Castle</span>
        <button
          class="mc-create-btn"
          onClick={() => { setShowCreate(!showCreate); setSelectedAgent(null); }}
        >
          +
        </button>
      </header>

      <div class="mc-content">
        {/* Agent Grid */}
        <div class="mc-grid">
          {agents.map((agent) => (
            <div
              key={agent.id}
              class={`mc-agent-card ${selectedAgent?.id === agent.id ? "selected" : ""}`}
              onClick={() => selectAgent(agent)}
            >
              <AgentOrb color={agent.color} status={agent.status} size={64} />
              <div class="mc-agent-info">
                <span class="mc-agent-name">{agent.name}</span>
                {agent.model && <span class="mc-agent-model">{agent.model}</span>}
                <span class={`mc-agent-status status-${agent.status}`}>
                  {statusLabel(agent.status)}
                </span>
              </div>
              {agent.current_task && (
                <div class="mc-agent-task">{agent.current_task}</div>
              )}
              {(agent.status === "needs_review" || agent.status === "failed") && (
                <div class="agent-review-actions">
                  <button class="review-btn approve" onClick={(e) => approveAgent(agent.id, e)}>
                    Approve
                  </button>
                  <button class="review-btn retry" onClick={(e) => retryAgent(agent.id, e)}>
                    Retry
                  </button>
                </div>
              )}
              <button
                class="mc-delete-btn"
                onClick={(e) => deleteAgent(agent.id, e)}
                title="Delete agent"
              >
                &times;
              </button>
            </div>
          ))}

          {agents.length === 0 && !showCreate && (
            <div class="mc-empty">
              <p>No agents yet.</p>
              <p>Create your first specialist agent to get started.</p>
            </div>
          )}
        </div>

        {/* Reflections Tile */}
        {!selectedAgent && !showCreate && <ReflectionsTile />}

        {/* Create Agent Form */}
        {showCreate && (
          <div class="mc-create-form">
            <h3>Create Agent</h3>
            <input
              type="text"
              placeholder="Agent name (e.g. Strategist)"
              value={newName}
              onInput={(e) => setNewName(e.target.value)}
              autofocus
            />
            <input
              type="text"
              placeholder="Role (e.g. Analyzes proposals and provides strategic recommendations)"
              value={newRole}
              onInput={(e) => setNewRole(e.target.value)}
            />
            <div class="mc-color-picker">
              {COLOR_OPTIONS.map((c) => (
                <button
                  key={c}
                  class={`mc-color-swatch ${newColor === c ? "active" : ""}`}
                  style={{ background: c }}
                  onClick={() => setNewColor(c)}
                />
              ))}
            </div>
            <button
              class="mc-submit-btn"
              onClick={createAgent}
              disabled={!newName.trim() || !newRole.trim()}
            >
              Create
            </button>
          </div>
        )}

        {/* Agent Chat Panel */}
        {selectedAgent && !showCreate && (
          <div class="mc-chat-panel">
            <div class="mc-chat-header">
              <AgentOrb color={selectedAgent.color} status={selectedAgent.status} size={32} />
              <div>
                <span class="mc-chat-name">{selectedAgent.name}</span>
                <span class="mc-chat-role">{selectedAgent.role}</span>
              </div>
            </div>
            <div class="mc-chat-messages">
              {chatMessages.map((msg, i) => (
                <div key={i} class={`mc-chat-msg ${msg.role}`}>
                  <div class="mc-chat-msg-content">{msg.content}</div>
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>
            <form
              class="mc-chat-input"
              onSubmit={(e) => { e.preventDefault(); sendChat(); }}
            >
              <input
                type="text"
                value={chatInput}
                onInput={(e) => setChatInput(e.target.value)}
                placeholder={`Talk to ${selectedAgent.name}...`}
                disabled={isStreaming}
              />
              <button type="submit" disabled={!chatInput.trim() || isStreaming}>
                &uarr;
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}


function ReflectionsTile() {
  const [reflections, setReflections] = useState([]);
  const [expanded, setExpanded] = useState(false);

  const fetchReflections = () => {
    fetch("/reflections/micro", { headers: authHeaders() })
      .then((r) => r.ok ? r.json() : [])
      .then(setReflections)
      .catch(() => {});
  };

  useEffect(() => {
    fetchReflections();
    const interval = setInterval(fetchReflections, 30000);
    return () => clearInterval(interval);
  }, []);

  const approve = async (id, e) => {
    e.stopPropagation();
    await fetch(`/reflections/micro/${id}/approve`, {
      method: "POST",
      headers: authHeaders(),
    });
    fetchReflections();
  };

  const dismiss = async (id, e) => {
    e.stopPropagation();
    await fetch(`/reflections/micro/${id}/dismiss`, {
      method: "POST",
      headers: authHeaders(),
    });
    fetchReflections();
  };

  if (reflections.length === 0) return null;

  return (
    <div class="mc-reflections-tile">
      <div
        class="mc-reflections-header"
        onClick={() => setExpanded(!expanded)}
      >
        <span class="mc-reflections-title">Reflections</span>
        <span class="mc-reflections-badge">{reflections.length}</span>
        <span class="mc-reflections-toggle">{expanded ? "−" : "+"}</span>
      </div>
      {expanded && (
        <div class="mc-reflections-list">
          {reflections.map((r) => (
            <div key={r.id} class="mc-reflection-item">
              <div class="mc-reflection-time">
                {new Date(r.timestamp).toLocaleDateString("en-SG", {
                  month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                })}
              </div>
              <div class="mc-reflection-content">{r.content}</div>
              <div class="mc-reflection-actions">
                <button class="mc-ref-btn approve" onClick={(e) => approve(r.id, e)}>
                  Approve
                </button>
                <button class="mc-ref-btn dismiss" onClick={(e) => dismiss(r.id, e)}>
                  Dismiss
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
