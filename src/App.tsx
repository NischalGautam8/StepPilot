import { useState, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  Send,
  Settings as SettingsIcon,
  Activity,
  Tv,
  Command,
  Play,
  Square,
  MessageSquare,
  TestTube
} from "lucide-react";
import { ScreenCaptureTest } from "./components";
import "./App.css";

interface Message {
  id: string;
  sender: "user" | "assistant" | "system";
  text: string;
  timestamp: Date;
}

function App() {
  const [activeTab, setActiveTab] = useState<"chat" | "dashboard" | "settings" | "sprint2test">("chat");
  const [wsStatus, setWsStatus] = useState<"connected" | "disconnected" | "connecting">("connecting");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "init",
      sender: "system",
      text: "StepPilot core engine initialized. System tray and hotkey Ctrl+Alt+K ready.",
      timestamp: new Date()
    }
  ]);
  const [inputText, setInputText] = useState("");
  const [nameInput, setNameInput] = useState("");
  const [greetResponse, setGreetResponse] = useState("");
  const [rustLogs, setRustLogs] = useState<string[]>([]);
  const [sidecarStatus, setSidecarStatus] = useState<"idle" | "running" | "error">("idle");
  const a11yStatus = "disconnected" as "connected" | "disconnected";
  
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Setup WebSocket connection to local FastAPI backend
  useEffect(() => {
    let active = true;
    let socket: WebSocket | null = null;
    let reconnectTimeout: number;

    const connectWS = () => {
      if (!active) return;
      setWsStatus("connecting");
      
      socket = new WebSocket("ws://127.0.0.1:8765/ws");

      socket.onopen = () => {
        if (!active) return;
        setWsStatus("connected");
        setSidecarStatus("running");
        addSystemMessage("WebSocket bridge to local FastAPI backend established.");
      };

      socket.onmessage = (event) => {
        if (!active) return;
        try {
          const data = JSON.parse(event.data);
          addAssistantMessage(`FastAPI Backend Response: ${JSON.stringify(data)}`);
        } catch {
          addAssistantMessage(`Raw message: ${event.data}`);
        }
      };

      socket.onclose = () => {
        if (!active) return;
        setWsStatus("disconnected");
        setSidecarStatus("idle");
        // Automatically attempt reconnection with 3s backoff
        reconnectTimeout = window.setTimeout(connectWS, 3000);
      };

      socket.onerror = () => {
        socket?.close();
      };

      wsRef.current = socket;
    };

    connectWS();

    return () => {
      active = false;
      clearTimeout(reconnectTimeout);
      socket?.close();
    };
  }, []);

  // Listen to Tauri events emitted from Rust backend
  useEffect(() => {
    let unlistenStart: (() => void) | null = null;
    let unlistenStop: (() => void) | null = null;
    let unlistenNav: (() => void) | null = null;

    const setupTauriListeners = async () => {
      try {
        unlistenStart = await listen("tray-start", () => {
          addSystemMessage("System Tray command: [Start] activated");
        });
        unlistenStop = await listen("tray-stop", () => {
          addSystemMessage("System Tray command: [Stop] activated");
        });
        unlistenNav = await listen("navigate", (event) => {
          const target = event.payload as string;
          if (target === "settings") {
            setActiveTab("settings");
          }
        });
      } catch (err) {
        console.error("Failed to register Tauri event listeners:", err);
      }
    };

    setupTauriListeners();

    return () => {
      if (unlistenStart) unlistenStart();
      if (unlistenStop) unlistenStop();
      if (unlistenNav) unlistenNav();
    };
  }, []);

  // Auto-scroll to the bottom of the chat list
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const addSystemMessage = (text: string) => {
    setMessages((prev) => [
      ...prev,
      { id: Math.random().toString(), sender: "system", text, timestamp: new Date() }
    ]);
  };

  const addAssistantMessage = (text: string) => {
    setMessages((prev) => [
      ...prev,
      { id: Math.random().toString(), sender: "assistant", text, timestamp: new Date() }
    ]);
  };

  // UI action handlers triggering Tauri IPC Commands
  const testGreet = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nameInput.trim()) return;
    try {
      const response: string = await invoke("greet", { name: nameInput });
      setGreetResponse(response);
      logRustCall("greet", response);
    } catch (err) {
      setGreetResponse(`IPC Error: ${err}`);
    }
  };

  const triggerCapture = async () => {
    try {
      addSystemMessage("Triggering Screen Capture IPC Call...");
      const result: string = await invoke("capture_screen");
      addSystemMessage(`Capture result: ${result}`);
      logRustCall("capture_screen", result);
    } catch (err) {
      addSystemMessage(`Capture failed: ${err}`);
    }
  };

  const triggerCursorPos = async () => {
    try {
      const result: [number, number] = await invoke("get_cursor_position");
      addSystemMessage(`Current cursor position: X=${result[0]}, Y=${result[1]}`);
      logRustCall("get_cursor_position", JSON.stringify(result));
    } catch (err) {
      addSystemMessage(`Cursor tracking error: ${err}`);
    }
  };

  const toggleSidecar = async (action: "start" | "stop") => {
    try {
      const command = action === "start" ? "start_sidecar" : "stop_sidecar";
      addSystemMessage(`Triggering Python sidecar IPC ${action}...`);
      const result: string = await invoke(command);
      addSystemMessage(`Sidecar command result: ${result}`);
      logRustCall(command, result);
    } catch (err) {
      addSystemMessage(`Sidecar command failed: ${err}`);
    }
  };

  const logRustCall = (command: string, response: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setRustLogs((prev) => [`[${timestamp}] INVOKE "${command}" -> ${response.slice(0, 50)}...`, ...prev]);
  };

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    const userMsg = inputText.trim();
    setMessages((prev) => [
      ...prev,
      { id: Math.random().toString(), sender: "user", text: userMsg, timestamp: new Date() }
    ]);
    setInputText("");

    // Send query to local FastAPI via websocket
    if (wsRef.current && wsStatus === "connected") {
      wsRef.current.send(JSON.stringify({ type: "user_query", query: userMsg }));
    } else {
      setTimeout(() => {
        addAssistantMessage("I received your task. (Note: FastAPI backend websocket is currently disconnected. Start backend server using dev.ps1 script.)");
      }, 1000);
    }
  };

  return (
    <div className="app-container">
      {/* Premium Header */}
      <header className="app-header">
        <div className="logo-container">
          <span className="logo-text">👑 StepPilot</span>
          <span className="logo-badge">Sprint 1</span>
        </div>
        
        <div className="status-indicator">
          <div className={`status-dot ${wsStatus !== "connected" ? "disconnected" : ""}`}></div>
          <span>FastAPI Service: {wsStatus === "connected" ? "Connected" : wsStatus === "connecting" ? "Connecting..." : "Offline"}</span>
        </div>
      </header>

      {/* Main Layout */}
      <main className="app-main">
        {/* Navigation Sidebar */}
        <aside className="app-sidebar">
          <div className="sidebar-section">
            <span className="sidebar-title">Core Navigation</span>
            <button
              className={`nav-button ${activeTab === "chat" ? "active" : ""}`}
              onClick={() => setActiveTab("chat")}
            >
              <MessageSquare size={18} />
              Guidance Chat
            </button>
            <button
              className={`nav-button ${activeTab === "dashboard" ? "active" : ""}`}
              onClick={() => setActiveTab("dashboard")}
            >
              <Activity size={18} />
              System Dashboard
            </button>
            <button
              className={`nav-button ${activeTab === "sprint2test" ? "active" : ""}`}
              onClick={() => setActiveTab("sprint2test")}
            >
              <TestTube size={18} />
              Sprint 2 Test
            </button>
            <button
              className={`nav-button ${activeTab === "settings" ? "active" : ""}`}
              onClick={() => setActiveTab("settings")}
            >
              <SettingsIcon size={18} />
              App Settings
            </button>
          </div>

          <div className="sidebar-section" style={{ marginTop: "auto" }}>
            <span className="sidebar-title">Global Hotkeys</span>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "13px" }}>
              <span style={{ color: "var(--text-secondary)" }}>Toggle HUD</span>
              <kbd className="hotkey-badge">Ctrl+Alt+K</kbd>
            </div>
          </div>
        </aside>

        {/* Dynamic Content Pane */}
        {activeTab === "chat" && (
          <section className="app-chat-pane">
            <div className="chat-messages">
              {messages.map((msg) => (
                <div key={msg.id} className={`message-bubble ${msg.sender}`}>
                  {msg.text}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-container">
              <form onSubmit={handleSendMessage} className="chat-input-form">
                <input
                  type="text"
                  className="chat-input"
                  placeholder="Ask me to guide you through a task (e.g. 'Open Notepad')..."
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                />
                <button type="submit" className="send-button">
                  <Send size={16} />
                </button>
              </form>
            </div>
          </section>
        )}

        {activeTab === "dashboard" && (
          <section className="dashboard-panel">
            <div>
              <h2 className="dashboard-title">System Dashboard</h2>
              <p className="dashboard-subtitle">Monitor services, triggers, and active subprocesses.</p>
            </div>

            {/* Performance Stats Grid */}
            <div className="stats-grid">
              <div className="stat-card">
                <span className="stat-label">Sidecar Status</span>
                <span className="stat-value" style={{ color: sidecarStatus === "running" ? "var(--accent-primary)" : "var(--text-muted)" }}>
                  {sidecarStatus === "running" ? "Running" : "Idle / Stopped"}
                </span>
                <div className="stat-glow"></div>
              </div>

              <div className="stat-card">
                <span className="stat-label">Windows UIA Bridge</span>
                <span className="stat-value" style={{ color: a11yStatus === "connected" ? "var(--accent-primary)" : "var(--text-muted)" }}>
                  {a11yStatus === "connected" ? "Active" : "Inactive"}
                </span>
                <div className="stat-glow"></div>
              </div>

              <div className="stat-card">
                <span className="stat-label">Websocket Latency</span>
                <span className="stat-value">
                  {wsStatus === "connected" ? "< 1ms" : "--"}
                </span>
                <div className="stat-glow"></div>
              </div>
            </div>

            {/* Diagnostic Control Actions */}
            <div className="stat-card" style={{ gap: "16px" }}>
              <span className="sidebar-title" style={{ paddingBottom: "4px", borderBottom: "1px solid var(--border-color)" }}>
                Diagnostic IPC Controls (Rust &lt;-&gt; React)
              </span>
              
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                <button className="nav-button active" onClick={triggerCapture}>
                  <Tv size={16} style={{ marginRight: "4px" }} />
                  Screen Capture
                </button>
                <button className="nav-button active" onClick={triggerCursorPos}>
                  <Command size={16} style={{ marginRight: "4px" }} />
                  Query Cursor Pos
                </button>
                <button className="nav-button active" onClick={() => toggleSidecar("start")}>
                  <Play size={16} style={{ marginRight: "4px" }} />
                  Start Sidecar
                </button>
                <button className="nav-button active" onClick={() => toggleSidecar("stop")}>
                  <Square size={16} style={{ marginRight: "4px" }} />
                  Stop Sidecar
                </button>
              </div>
            </div>

            {/* IPC Live Logs */}
            <div className="stat-card" style={{ flex: 1, gap: "12px", minHeight: "150px" }}>
              <span className="sidebar-title">Live IPC Event Logs</span>
              <div style={{
                fontFamily: "monospace",
                fontSize: "12px",
                color: "var(--text-secondary)",
                display: "flex",
                flexDirection: "column",
                gap: "6px",
                overflowY: "auto",
                maxHeight: "180px"
              }}>
                {rustLogs.length === 0 ? (
                  <span style={{ color: "var(--text-muted)" }}>No IPC interactions logged yet. Trigger an action above.</span>
                ) : (
                  rustLogs.map((log, index) => <div key={index}>{log}</div>)
                )}
              </div>
            </div>
          </section>
        )}

        {activeTab === "settings" && (
          <section className="dashboard-panel">
            <div>
              <h2 className="dashboard-title">App Settings</h2>
              <p className="dashboard-subtitle">Configure LLM providers, model bindings, and hotkeys.</p>
            </div>

            <div className="stat-card" style={{ gap: "20px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <label className="sidebar-title">IPC Greeting Test</label>
                <form onSubmit={testGreet} style={{ display: "flex", gap: "12px" }}>
                  <input
                    type="text"
                    style={{
                      flex: 1,
                      background: "rgba(255, 255, 255, 0.03)",
                      border: "1px solid var(--border-color)",
                      borderRadius: "8px",
                      color: "var(--text-primary)",
                      padding: "10px 14px",
                      outline: "none"
                    }}
                    placeholder="Enter name to greet..."
                    value={nameInput}
                    onChange={(e) => setNameInput(e.target.value)}
                  />
                  <button type="submit" className="nav-button active" style={{ height: "40px" }}>
                    Invoke IPC Greet
                  </button>
                </form>
                {greetResponse && (
                  <div style={{
                    marginTop: "8px",
                    padding: "8px 12px",
                    background: "var(--accent-primary-glow)",
                    border: "1px solid rgba(16, 185, 129, 0.2)",
                    borderRadius: "6px",
                    fontSize: "13px",
                    color: "var(--accent-primary)"
                  }}>
                    {greetResponse}
                  </div>
                )}
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <span className="sidebar-title">LLM Gateway Provider</span>
                <select style={{
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "8px",
                  color: "var(--text-primary)",
                  padding: "10px",
                  fontFamily: "inherit"
                }} disabled>
                  <option>GitHub Copilot SDK (Primary)</option>
                  <option>OpenAI API (Fallback)</option>
                </select>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <span className="sidebar-title">Vision Model Selection</span>
                <select style={{
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "8px",
                  color: "var(--text-primary)",
                  padding: "10px",
                  fontFamily: "inherit"
                }} disabled>
                  <option>Local OCR Pipeline + Windows UIA</option>
                  <option>GPT-4o Vision Integration</option>
                </select>
              </div>
            </div>
          </section>
        )}

        {activeTab === "sprint2test" && (
          <section className="dashboard-panel">
            <ScreenCaptureTest />
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
