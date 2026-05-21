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
  TestTube,
  Sparkles,
  X,
  CheckCircle,
  AlertCircle,
  Save,
  History as HistoryIcon
} from "lucide-react";
import { ScreenCaptureTest } from "./components";
import "./App.css";

interface Message {
  id: string;
  sender: "user" | "assistant" | "system";
  text: string;
  timestamp: Date;
}

interface Settings {
  llm_provider: string;
  model_name: string;
  show_debug_overlay: boolean;
  auto_advance: boolean;
  hotkey: string;
  openai_api_key: string;
  openai_base_url?: string;
  gemini_api_key?: string;
  use_omniparser: boolean;
  use_gpu: boolean;
  models_downloaded?: boolean;
  execution_mode: string;
}

interface HistoryItem {
  id: string;
  task: string;
  status: "completed" | "cancelled" | "failed";
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
  const [rustLogs, setRustLogs] = useState<string[]>([]);
  const [sidecarStatus, setSidecarStatus] = useState<"idle" | "running" | "error">("idle");
  const a11yStatus = "disconnected" as "connected" | "disconnected";

  // Sprint 8 States
  const [settings, setSettings] = useState<Settings>({
    llm_provider: "copilot",
    model_name: "gpt-4o-mini",
    show_debug_overlay: false,
    auto_advance: true,
    hotkey: "Ctrl+Alt+K",
    openai_api_key: "",
    openai_base_url: "",
    gemini_api_key: "",
    use_omniparser: false,
    use_gpu: false,
    models_downloaded: false,
    execution_mode: "supervised"
  });
  const [currentPlan, setCurrentPlan] = useState<any>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(-1);
  const [taskHistory, setTaskHistory] = useState<HistoryItem[]>([]);
  const [saveSuccess, setSaveSuccess] = useState(false);
  
  // Agent States (Sprint 13)
  const [agentProposedAction, setAgentProposedAction] = useState<any>(null);
  const [agentHistory, setAgentHistory] = useState<any[]>([]);
  const [isAgentRunning, setIsAgentRunning] = useState(false);
  const [countdown, setCountdown] = useState<number | null>(null);
  
  // Model Download States
  const [downloadProgress, setDownloadProgress] = useState<number | null>(null);
  const [downloadStatus, setDownloadStatus] = useState<string>("");
  
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const settingsRef = useRef(settings);
  settingsRef.current = settings;

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
        
        // Reset download progress to clear any stale stuck UI from a previous server session
        setDownloadProgress(null);
        setDownloadStatus("");
        
        // Request settings on connect
        socket?.send(JSON.stringify({ type: "get_settings" }));
      };

      socket.onmessage = (event) => {
        if (!active) return;
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === "settings_data") {
            setSettings(data.settings);
            addSystemMessage("Successfully loaded settings from backend config.");
          } else if (data.type === "settings_saved") {
            addSystemMessage("✓ Settings saved successfully to keyring & config file.");
            setSaveSuccess(true);
            setTimeout(() => setSaveSuccess(false), 3000);
          } else if (data.type === "download_progress") {
            setDownloadProgress(data.percentage);
            setDownloadStatus(data.status);
            if (data.percentage === 100) {
              addSystemMessage(`✓ ${data.status}`);
              setTimeout(() => {
                setDownloadProgress(null);
                setDownloadStatus("");
              }, 4000);
            } else if (data.percentage === -1) {
              addSystemMessage(`❌ ${data.status}`);
              setTimeout(() => {
                setDownloadProgress(null);
                setDownloadStatus("");
              }, 6000);
            }
          } else if (data.type === "agent_action_proposed") {
            const action = data.action;
            const history = data.history || [];
            setAgentProposedAction(action);
            setAgentHistory(history);
            setIsAgentRunning(true);
            
            let actionDesc = "";
            if (action.tool === "click") {
              actionDesc = `Click at coordinates (${action.args.x}, ${action.args.y}) with button: ${action.args.button}`;
            } else if (action.tool === "type_text") {
              actionDesc = `Type text: "${action.args.text}"`;
            } else if (action.tool === "key_press") {
              actionDesc = `Press keys: "${action.args.keys}"`;
            } else if (action.tool === "scroll") {
              actionDesc = `Scroll ${action.args.direction} by ${action.args.amount} at (${action.args.x}, ${action.args.y})`;
            } else if (action.tool === "wait") {
              actionDesc = `Wait for ${action.args.seconds} seconds`;
            } else if (action.tool === "read_screen") {
              actionDesc = `Read screen & update visible elements`;
            } else if (action.tool === "finish") {
              actionDesc = `Finish task (${action.args.success ? "Success" : "Failed"}): ${action.args.message}`;
            }
            
            addAssistantMessage(`Proposed Action: ${actionDesc}\nReasoning: "${action.thought}"`);
            
            if (settingsRef.current.execution_mode === "yolo") {
              if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({ type: "agent_step_execute", action }));
              }
              setAgentProposedAction(null);
            } else if (settingsRef.current.execution_mode === "autonomous") {
              setCountdown(1.5);
            }
          } else if (data.type === "agent_finished") {
            setIsAgentRunning(false);
            setAgentProposedAction(null);
            addSystemMessage(`✓ Task Completed: ${data.message}`);
            addAssistantMessage(`Task execution finished! ${data.message}`);
          } else if (data.type === "agent_aborted") {
            setIsAgentRunning(false);
            setAgentProposedAction(null);
            addSystemMessage(`❌ Task Aborted: ${data.message}`);
          } else if (data.type === "ack" && data.received === "task_start") {
            const plan = data.plan;
            if (plan && plan.steps && plan.steps.length > 0) {
              startPlan(plan);
            } else {
              addAssistantMessage(`Failed to generate task plan: ${plan?.error || "Unknown error"}`);
            }
          } else if (data.type === "error") {
            addAssistantMessage(`Error: ${data.message}`);
          } else if (data.type !== "pong" && data.type !== "ping") {
            addAssistantMessage(`Backend update: ${JSON.stringify(data)}`);
          }
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

  // Agent Helpers (Sprint 13)
  const handleApproveAction = (action: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      setCountdown(null);
      wsRef.current.send(JSON.stringify({ type: "agent_step_execute", action }));
      setAgentProposedAction(null);
    }
  };

  const handleAbortAgent = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      setCountdown(null);
      wsRef.current.send(JSON.stringify({ type: "agent_abort" }));
      setAgentProposedAction(null);
    }
  };

  useEffect(() => {
    if (settings.execution_mode !== "autonomous" || countdown === null || !agentProposedAction) return;

    if (countdown <= 0) {
      handleApproveAction(agentProposedAction);
      return;
    }

    const timer = setTimeout(() => {
      setCountdown(prev => (prev !== null ? prev - 0.5 : null));
    }, 500);

    return () => clearTimeout(timer);
  }, [countdown, agentProposedAction, settings.execution_mode]);

  // Helpers for step progression
  const startPlan = (plan: any) => {
    setCurrentPlan(plan);
    setCurrentStepIndex(0);
    const step = plan.steps[0];
    addSystemMessage(`Started task guidance session: "${plan.task}"`);
    addAssistantMessage(`I've created a ${plan.steps.length}-step guide. Let's do Step 1: ${step.description}`);
    
    // Update target bounding box in Rust for click-tracking
    if (step.bbox) {
      const [x, y, w, h] = step.bbox;
      invoke("set_active_target_bbox", {
        x: Math.round(x),
        y: Math.round(y),
        w: Math.round(w),
        h: Math.round(h)
      }).catch((err) => console.error("Failed to set target bbox in Rust:", err));
    } else {
      invoke("set_active_target_bbox", { x: 0, y: 0, w: 0, h: 0 }).catch(() => {});
    }
    
    import("@tauri-apps/api/event").then(({ emit }) => {
      emit("show-guidance-hint", {
        step_number: step.step_number,
        total_steps: plan.steps.length,
        description: step.description,
        action: step.action,
        bbox: step.bbox
      });
    });
  };

  const handleNextStep = () => {
    if (!currentPlan || !currentPlan.steps || currentPlan.steps.length === 0) return;

    // Notify backend that the previous step has completed successfully
    if (currentStepIndex >= 0 && currentStepIndex < currentPlan.steps.length) {
      const completedStep = currentPlan.steps[currentStepIndex];
      if (wsRef.current && wsStatus === "connected") {
        wsRef.current.send(JSON.stringify({
          type: "step_result",
          step_number: completedStep.step_number,
          description: completedStep.description,
          action: completedStep.action,
          status: "success",
          details: "Completed by user progression"
        }));
      }
    }

    setCurrentStepIndex((prevIndex) => {
      const nextIndex = prevIndex + 1;
      if (nextIndex >= currentPlan.steps.length) {
        // Task completed!
        addSystemMessage("✓ Task completed! Celebration animated in HUD.");
        addAssistantMessage("Task completed! Let me know if there's anything else I can guide you through.");
        
        // Clear hint on overlay
        import("@tauri-apps/api/event").then(({ emit }) => {
          emit("clear-guidance-hint");
        });
        invoke("set_active_target_bbox", { x: 0, y: 0, w: 0, h: 0 }).catch(() => {});
        
        // Add to history
        setTaskHistory((prev) => [
          {
            id: Math.random().toString(),
            task: currentPlan.task,
            status: "completed",
            timestamp: new Date()
          },
          ...prev
        ]);
        
        setCurrentPlan(null);
        return -1;
      }
      
      // Send next step to overlay
      const step = currentPlan.steps[nextIndex];
      addSystemMessage(`Stepping to: ${step.description}`);
      addAssistantMessage(`Step ${step.step_number} of ${currentPlan.steps.length}: ${step.description}`);
      
      // Update target bounding box in Rust for click-tracking
      if (step.bbox) {
        const [x, y, w, h] = step.bbox;
        invoke("set_active_target_bbox", {
          x: Math.round(x),
          y: Math.round(y),
          w: Math.round(w),
          h: Math.round(h)
        }).catch((err) => console.error("Failed to set target bbox in Rust:", err));
      } else {
        invoke("set_active_target_bbox", { x: 0, y: 0, w: 0, h: 0 }).catch(() => {});
      }
      
      import("@tauri-apps/api/event").then(({ emit }) => {
        emit("show-guidance-hint", {
          step_number: step.step_number,
          total_steps: currentPlan.steps.length,
          description: step.description,
          action: step.action,
          bbox: step.bbox
        });
      });
      
      return nextIndex;
    });
  };

  const handleCancelTask = () => {
    if (!currentPlan) return;

    // Notify backend that the active step was cancelled
    if (currentStepIndex >= 0 && currentStepIndex < currentPlan.steps.length) {
      const activeStep = currentPlan.steps[currentStepIndex];
      if (wsRef.current && wsStatus === "connected") {
        wsRef.current.send(JSON.stringify({
          type: "step_result",
          step_number: activeStep.step_number,
          description: activeStep.description,
          action: activeStep.action,
          status: "cancelled",
          details: "Cancelled by user button"
        }));
      }
    }
    
    addSystemMessage("Task cancelled by user.");
    addAssistantMessage("Task execution has been cancelled.");
    
    // Clear hint on overlay
    import("@tauri-apps/api/event").then(({ emit }) => {
      emit("clear-guidance-hint");
    });
    invoke("set_active_target_bbox", { x: 0, y: 0, w: 0, h: 0 }).catch(() => {});
    
    // Add to history
    setTaskHistory((prev) => [
      {
        id: Math.random().toString(),
        task: currentPlan.task,
        status: "cancelled",
        timestamp: new Date()
      },
      ...prev
    ]);
    
    setCurrentPlan(null);
    setCurrentStepIndex(-1);
  };

  // Listen to Tauri events emitted from Rust backend & Overlay
  useEffect(() => {
    const unlistenStart = listen("tray-start", () => {
      addSystemMessage("System Tray command: [Start] activated");
    });
    const unlistenStop = listen("tray-stop", () => {
      addSystemMessage("System Tray command: [Stop] activated");
    });
    const unlistenNav = listen("navigate", (event) => {
      const target = event.payload as string;
      if (target === "settings") {
        setActiveTab("settings");
      }
    });
    const unlistenAutoAdvance = listen("auto-advance-step", () => {
      handleNextStep();
    });
    const unlistenRequestNextStep = listen("request-next-step", () => {
      handleNextStep();
    });

    return () => {
      unlistenStart.then((fn) => fn());
      unlistenStop.then((fn) => fn());
      unlistenNav.then((fn) => fn());
      unlistenAutoAdvance.then((fn) => fn());
      unlistenRequestNextStep.then((fn) => fn());
    };
  }, [currentPlan, currentStepIndex]);

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
      setAgentHistory([]);
      setAgentProposedAction(null);
      setIsAgentRunning(true);
      wsRef.current.send(JSON.stringify({
        type: "agent_start",
        query: userMsg,
        mode: settings.execution_mode
      }));
    } else {
      setTimeout(() => {
        addAssistantMessage("I received your task. (Note: FastAPI backend websocket is currently disconnected. Start backend server using dev.ps1 script.)");
      }, 1000);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && e.ctrlKey) {
      e.preventDefault();
      // Trigger send message
      const fakeEvent = { preventDefault: () => {} } as React.FormEvent;
      handleSendMessage(fakeEvent);
    }
  };

  const handleSaveSettings = (e: React.FormEvent) => {
    e.preventDefault();
    if (wsRef.current && wsStatus === "connected") {
      wsRef.current.send(JSON.stringify({
        type: "save_settings",
        settings: settings
      }));
    } else {
      addSystemMessage("WebSocket offline: Settings saved in memory only. Connect FastAPI backend to persist settings.");
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    }
  };

  const handleDownloadModels = () => {
    if (wsRef.current && wsStatus === "connected") {
      setDownloadProgress(0);
      setDownloadStatus("Starting download...");
      wsRef.current.send(JSON.stringify({ type: "download_models" }));
      addSystemMessage("Requested OmniParser model weights download from Hugging Face...");
    } else {
      addSystemMessage("Cannot start download: Backend WebSocket offline.");
    }
  };

  const handleCancelDownload = () => {
    if (wsRef.current && wsStatus === "connected") {
      wsRef.current.send(JSON.stringify({ type: "cancel_download" }));
      addSystemMessage("Cancelling OmniParser model download...");
    }
  };

  const progressPercent = currentPlan && currentPlan.steps && currentPlan.steps.length > 0
    ? Math.round(((currentStepIndex + 1) / currentPlan.steps.length) * 100)
    : 0;

  return (
    <div className="app-container">
      {/* Premium Header */}
      <header className="app-header">
        <div className="logo-container">
          <span className="logo-text">👑 StepPilot</span>
          <span className="logo-badge">Sprint 8</span>
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

          {currentPlan && (
            <div className="sidebar-section progress-sidebar-widget">
              <span className="sidebar-title">Active Mission</span>
              <div className="active-mission-card">
                <span className="mission-name">{currentPlan.task}</span>
                <span className="mission-step">Step {currentStepIndex + 1} of {currentPlan.steps.length}</span>
                <div className="progress-bar-container">
                  <div className="progress-bar-fill" style={{ width: `${progressPercent}%` }}></div>
                </div>
                <button className="cancel-mission-button" onClick={handleCancelTask}>
                  <X size={12} /> Cancel Task
                </button>
              </div>
            </div>
          )}

          <div className="sidebar-section" style={{ marginTop: "auto" }}>
            <span className="sidebar-title">Global Hotkeys</span>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "13px" }}>
              <span style={{ color: "var(--text-secondary)" }}>Toggle HUD</span>
              <kbd className="hotkey-badge">{settings.hotkey}</kbd>
            </div>
          </div>
        </aside>

        {/* Dynamic Content Pane */}
        {activeTab === "chat" && (
          <section className="app-chat-pane">
            {isAgentRunning && (
              <div className="task-progress-hud agent-hud" style={{
                background: "rgba(30, 27, 75, 0.85)",
                border: "1px solid rgba(139, 92, 246, 0.4)",
                boxShadow: "0 8px 32px 0 rgba(139, 92, 246, 0.2)",
                backdropFilter: "blur(12px)",
                borderRadius: "12px",
                padding: "16px",
                display: "flex",
                flexDirection: "column",
                gap: "12px",
                marginBottom: "16px",
                position: "relative",
                zIndex: 10
              }}>
                <div className="hud-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div className="hud-info" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <Sparkles className="hud-icon animate-pulse" style={{ color: "#a78bfa" }} size={18} />
                    <span className="hud-task-title" style={{ fontWeight: "700", color: "#e9d5ff", letterSpacing: "0.5px" }}>
                      AI Agent Loop Active ({settings.execution_mode.toUpperCase()})
                    </span>
                  </div>
                  <div className="hud-stats">
                    <span className="hud-step-badge" style={{
                      background: "rgba(139, 92, 246, 0.2)",
                      border: "1px solid rgba(139, 92, 246, 0.4)",
                      padding: "2px 8px",
                      borderRadius: "12px",
                      fontSize: "11px",
                      color: "#c084fc",
                      fontWeight: "600"
                    }}>
                      Action #{agentHistory.length + 1}
                    </span>
                  </div>
                </div>

                {/* History list preview */}
                {agentHistory.length > 0 && (
                  <div className="agent-history-summary" style={{
                    fontSize: "11px",
                    color: "rgba(255, 255, 255, 0.5)",
                    background: "rgba(0, 0, 0, 0.2)",
                    borderRadius: "6px",
                    padding: "6px 10px",
                    maxHeight: "60px",
                    overflowY: "auto"
                  }}>
                    <div style={{ fontWeight: "600", marginBottom: "2px" }}>Previous Actions:</div>
                    {agentHistory.map((h, i) => (
                      <div key={i}>
                        ✓ {h.tool}({JSON.stringify(h.args)}) → <span style={{ color: h.result === "success" ? "#34d399" : "#f87171" }}>{h.result}</span>
                      </div>
                    ))}
                  </div>
                )}

                {agentProposedAction ? (
                  <div className="agent-proposed-action-block" style={{
                    background: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    borderRadius: "8px",
                    padding: "12px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px"
                  }}>
                    <div style={{ fontSize: "12px", color: "#a78bfa", fontStyle: "italic" }}>
                      <strong>Thought:</strong> "{agentProposedAction.thought}"
                    </div>
                    <div style={{ fontSize: "13px", color: "#fff", display: "flex", alignItems: "center", gap: "6px" }}>
                      <strong>Tool Call:</strong> 
                      <code style={{
                        background: "rgba(139, 92, 246, 0.25)",
                        padding: "2px 6px",
                        borderRadius: "4px",
                        color: "#ddd",
                        fontFamily: "monospace"
                      }}>
                        {agentProposedAction.tool}({JSON.stringify(agentProposedAction.args)})
                      </code>
                    </div>

                    <div className="agent-action-buttons" style={{ display: "flex", gap: "10px", marginTop: "4px", alignItems: "center" }}>
                      {settings.execution_mode === "guided" && (
                        <button className="hud-next-button" style={{ width: "100%", justifySelf: "stretch" }} onClick={() => handleApproveAction(agentProposedAction)}>
                          I completed this step, proceed →
                        </button>
                      )}
                      
                      {settings.execution_mode === "supervised" && (
                        <>
                          <button className="hud-next-button" style={{ flex: 1, padding: "8px 16px", borderRadius: "6px", fontWeight: "600", background: "var(--accent-primary)", border: "none", cursor: "pointer", color: "white" }} onClick={() => handleApproveAction(agentProposedAction)}>
                            Approve Action & Run
                          </button>
                          <button className="hud-cancel-button" style={{ background: "rgba(248, 113, 113, 0.15)", color: "#f87171", border: "1px solid rgba(248, 113, 113, 0.3)", padding: "8px 12px", borderRadius: "6px", cursor: "pointer" }} onClick={handleAbortAgent}>
                            Abort Agent
                          </button>
                        </>
                      )}

                      {settings.execution_mode === "autonomous" && (
                        <>
                          <div style={{ display: "flex", alignItems: "center", gap: "10px", flex: 1 }}>
                            <div className="countdown-ring" style={{
                              width: "28px",
                              height: "28px",
                              borderRadius: "50%",
                              border: "2px solid #8b5cf6",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: "11px",
                              fontWeight: "bold",
                              color: "#c084fc",
                              animation: "pulse 1.5s infinite"
                            }}>
                              {countdown}
                            </div>
                            <span style={{ fontSize: "12px", color: "rgba(255, 255, 255, 0.7)" }}>
                              Executing automatically...
                            </span>
                          </div>
                          <button className="hud-cancel-button" style={{ background: "rgba(248, 113, 113, 0.2)", color: "#f87171", border: "1px solid rgba(248, 113, 113, 0.4)", padding: "8px 16px", borderRadius: "6px", cursor: "pointer", fontWeight: "600" }} onClick={handleAbortAgent}>
                            PAUSE AGENT
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ) : (
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "rgba(255, 255, 255, 0.7)" }}>
                    <div className="agent-thinking-spinner" style={{
                      width: "14px",
                      height: "14px",
                      border: "2px solid rgba(139, 92, 246, 0.2)",
                      borderTopColor: "#a78bfa",
                      borderRadius: "50%",
                      animation: "spin 0.8s linear infinite"
                    }}></div>
                    <span>Agent is thinking / analyzing screen...</span>
                    <button className="hud-cancel-button" style={{ marginLeft: "auto", fontSize: "12px", padding: "4px 8px" }} onClick={handleAbortAgent}>
                      Cancel Task
                    </button>
                  </div>
                )}
              </div>
            )}

            {!isAgentRunning && currentPlan && (
              <div className="task-progress-hud">
                <div className="hud-row">
                  <div className="hud-info">
                    <Sparkles className="hud-icon animate-pulse" size={16} />
                    <span className="hud-task-title">Guidance Active: {currentPlan.task}</span>
                  </div>
                  <div className="hud-stats">
                    <span className="hud-step-badge">Step {currentStepIndex + 1} of {currentPlan.steps.length}</span>
                    <span className="hud-percentage">{progressPercent}%</span>
                  </div>
                </div>
                <div className="hud-progress-track">
                  <div className="hud-progress-bar" style={{ width: `${progressPercent}%` }}></div>
                </div>
                <div className="hud-step-instruction">
                  <strong>Instruction:</strong> {currentPlan.steps[currentStepIndex]?.description}
                </div>
                <div className="hud-actions">
                  <button className="hud-cancel-button" onClick={handleCancelTask}>
                    <X size={14} /> Cancel Mission
                  </button>
                  {!settings.auto_advance && (
                    <button className="hud-next-button" onClick={handleNextStep}>
                      Next Step →
                    </button>
                  )}
                </div>
              </div>
            )}

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
                <select
                  value={settings.execution_mode}
                  onChange={(e) => {
                    const newMode = e.target.value;
                    setSettings(prev => ({ ...prev, execution_mode: newMode }));
                    if (wsRef.current && wsStatus === "connected") {
                      wsRef.current.send(JSON.stringify({
                        type: "save_settings",
                        settings: { ...settings, execution_mode: newMode }
                      }));
                    }
                  }}
                  className="mode-select"
                  title="Execution Mode"
                >
                  <option value="supervised">Supervised</option>
                  <option value="yolo">YOLO</option>
                  <option value="autonomous">Autonomous</option>
                  <option value="guided">Guided</option>
                </select>
                <input
                  type="text"
                  className="chat-input"
                  placeholder="Ask me to guide you through a task (e.g. 'Open Notepad')... (Ctrl+Enter to send)"
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={handleKeyPress}
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

            <div className="dashboard-split-grid">
              {/* Diagnostic Control Actions */}
              <div className="stat-card" style={{ gap: "16px", flex: 1 }}>
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

              {/* Task History Panel */}
              <div className="stat-card task-history-card" style={{ gap: "12px", flex: 1 }}>
                <span className="sidebar-title" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <HistoryIcon size={14} /> Task Session History
                </span>
                <div className="history-list">
                  {taskHistory.length === 0 ? (
                    <span className="no-history-text">No tasks executed in this session.</span>
                  ) : (
                    taskHistory.map((item) => (
                      <div key={item.id} className={`history-item ${item.status}`}>
                        <div className="history-icon">
                          {item.status === "completed" ? (
                            <CheckCircle size={14} color="#10b981" />
                          ) : item.status === "cancelled" ? (
                            <AlertCircle size={14} color="#f59e0b" />
                          ) : (
                            <AlertCircle size={14} color="#ef4444" />
                          )}
                        </div>
                        <div className="history-details">
                          <span className="history-task">{item.task}</span>
                          <span className="history-time">{item.timestamp.toLocaleTimeString()}</span>
                        </div>
                        <span className={`history-status-badge ${item.status}`}>
                          {item.status}
                        </span>
                      </div>
                    ))
                  )}
                </div>
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

            <div className="settings-grid">
              {/* Interactive Settings Form */}
              <form onSubmit={handleSaveSettings} className="settings-form-container">
                <div className="settings-form-card">
                  <span className="sidebar-title card-section-title">Core Configurations</span>
                  
                  {saveSuccess && (
                    <div style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "10px 14px",
                      background: "rgba(16, 185, 129, 0.1)",
                      border: "1px solid rgba(16, 185, 129, 0.3)",
                      borderRadius: "8px",
                      color: "#34d399",
                      fontSize: "13px",
                      fontWeight: "600",
                      animation: "slideUp 0.25s ease-out",
                      marginTop: "4px"
                    }}>
                      <CheckCircle size={16} /> Configuration saved successfully!
                    </div>
                  )}
                  
                  <div className="settings-field">
                    <label className="field-label">LLM Gateway Provider</label>
                    <select
                      className="settings-select"
                      value={settings.llm_provider}
                      onChange={(e) => {
                        const provider = e.target.value;
                        const defaultModel = provider === "gemini" ? "gemini-3.5-flash" : "gpt-4o-mini";
                        setSettings({ ...settings, llm_provider: provider, model_name: defaultModel });
                      }}
                    >
                      <option value="copilot">GitHub Copilot SDK (Primary)</option>
                      <option value="openai">OpenAI API (Fallback)</option>
                      <option value="gemini">Google Gemini AI</option>
                    </select>
                  </div>

                  <div className="settings-field">
                    <label className="field-label">Vision Model Selection</label>
                    {settings.llm_provider === "openai" && settings.openai_base_url ? (
                      <input
                        type="text"
                        className="settings-input"
                        placeholder="e.g. meta/llama3-70b-instruct or llama3.1"
                        value={settings.model_name}
                        onChange={(e) => setSettings({ ...settings, model_name: e.target.value })}
                      />
                    ) : (
                      <select
                        className="settings-select"
                        value={settings.model_name}
                        onChange={(e) => setSettings({ ...settings, model_name: e.target.value })}
                      >
                        {settings.llm_provider === "gemini" ? (
                          <>
                            <optgroup label="Gemini 3.5 (Latest)">
                              <option value="gemini-3.5-flash">gemini-3.5-flash (Frontier-class performance at low cost)</option>
                            </optgroup>
                            <optgroup label="Gemini 3.1 (Stable)">
                              <option value="gemini-3.1-pro">gemini-3.1-pro (Google's most intelligent model for complex reasoning)</option>
                              <option value="gemini-3.1-flash-lite">gemini-3.1-flash-lite (Optimized for speed and high-scale workloads)</option>
                            </optgroup>
                            <optgroup label="Gemini 2.5 (Legacy support)">
                              <option value="gemini-2.5-pro">gemini-2.5-pro (Former flagship model widely used for production)</option>
                              <option value="gemini-2.5-flash">gemini-2.5-flash (Fast, cost-efficient multimodal model)</option>
                            </optgroup>
                          </>
                        ) : (
                          <>
                            <optgroup label="Flagship Frontier Models">
                              <option value="gpt-5.5">gpt-5.5 (Premier Frontier, Complex Reasoning)</option>
                              <option value="gpt-5.4">gpt-5.4 (Flagship Professional, Reasoning & Tool Use)</option>
                              <option value="gpt-5.2">gpt-5.2 (General Instructions & Coding)</option>
                              <option value="gpt-5.1">gpt-5.1 (Coding & Agentic, Configurable Reasoning)</option>
                              <option value="gpt-4o">gpt-4o (Legacy Vision Intelligent)</option>
                            </optgroup>
                            <optgroup label="Cost-Efficient & Mini Models">
                              <option value="gpt-5.4-mini">gpt-5.4-mini (Strongest Mini for Subagents)</option>
                              <option value="gpt-4o-mini">gpt-4o-mini (Fast, Multimodal Everyday)</option>
                              <option value="gpt-5-mini">gpt-5-mini (Lightweight, Responsive Coding)</option>
                              <option value="gpt-4.1-mini">gpt-4.1-mini (Specialized Instruction Follower)</option>
                              <option value="gpt-4.1-nano">gpt-4.1-nano (Specialized High-Volume Batch)</option>
                              <option value="gpt-5-nano">gpt-5-nano (Ultra-Efficient Scaled Workflows)</option>
                            </optgroup>
                          </>
                        )}
                      </select>
                    )}
                  </div>

                  <div className="settings-field">
                    <label className="field-label">Execution & Autonomy Mode</label>
                    <select
                      className="settings-select"
                      value={settings.execution_mode}
                      onChange={(e) => setSettings({ ...settings, execution_mode: e.target.value })}
                    >
                      <option value="guided">Guided Mode (Draw Overlay Hints; User Executes Actions)</option>
                      <option value="supervised">Supervised Mode (Confirm Every Backend Action Before Run)</option>
                      <option value="yolo">YOLO Mode (Full Hands-Free Execution; Instant Tool Runs)</option>
                      <option value="autonomous">Autonomous Mode (Full Hands-Free execution with countdown)</option>
                    </select>
                    <small className="field-help" style={{ color: "rgba(255, 255, 255, 0.4)", fontSize: "11px", marginTop: "4px", display: "block" }}>
                      {settings.execution_mode === "guided" && "Guided Mode displays bounding boxes and visual indicators, instructing you where to click manually."}
                      {settings.execution_mode === "supervised" && "Supervised Mode queries the AI agent step-by-step and asks for your click confirmation in the UI before performing mouse or keyboard moves."}
                      {settings.execution_mode === "yolo" && "YOLO Mode executes steps instantly as soon as they are proposed by the LLM without any confirmation or countdown."}
                      {settings.execution_mode === "autonomous" && "Autonomous Mode executes steps consecutively with a 1.5s countdown timer. Keep mouse at top-left corner of the screen to trigger PyAutoGUI emergency fail-safe."}
                    </small>
                  </div>

                  <div className="settings-field">
                    <label className="field-label">OpenAI API Key</label>
                    <input
                      type="password"
                      className="settings-input"
                      placeholder={settings.openai_api_key ? "••••••••••••••••••••••••" : "Enter OpenAI API Key..."}
                      value={settings.openai_api_key}
                      onChange={(e) => setSettings({ ...settings, openai_api_key: e.target.value })}
                    />
                    <small className="field-help">API key is saved securely using the Windows Credential Manager.</small>
                  </div>

                  <div className="settings-field">
                    <label className="field-label">OpenAI Custom Base URL</label>
                    <input
                      type="text"
                      className="settings-input"
                      placeholder="e.g. https://integrate.api.nvidia.com/v1"
                      value={settings.openai_base_url || ""}
                      onChange={(e) => setSettings({ ...settings, openai_base_url: e.target.value })}
                    />
                    <small className="field-help">Leave empty to use default OpenAI endpoint, or enter a custom endpoint URL (e.g. for NVIDIA NIM, Groq, OpenRouter, or local Ollama).</small>
                  </div>

                  <div className="settings-field">
                    <label className="field-label">Gemini API Key</label>
                    <input
                      type="password"
                      className="settings-input"
                      placeholder={settings.gemini_api_key ? "••••••••••••••••••••••••" : "Enter Gemini API Key..."}
                      value={settings.gemini_api_key || ""}
                      onChange={(e) => setSettings({ ...settings, gemini_api_key: e.target.value })}
                    />
                    <small className="field-help">API key is saved securely using the Windows Credential Manager.</small>
                  </div>

                  <div className="settings-field">
                    <label className="field-label">Global HUD Hotkey</label>
                    <input
                      type="text"
                      className="settings-input"
                      value={settings.hotkey}
                      onChange={(e) => setSettings({ ...settings, hotkey: e.target.value })}
                    />
                  </div>

                  <div className="settings-checkbox-group">
                    <label className="checkbox-container">
                      <input
                        type="checkbox"
                        checked={settings.show_debug_overlay}
                        onChange={(e) => setSettings({ ...settings, show_debug_overlay: e.target.checked })}
                      />
                      <span className="checkbox-custom"></span>
                      <div className="checkbox-text">
                        <span className="checkbox-title">Enable Developer Debug Overlay</span>
                        <span className="checkbox-desc">Renders all detected elements, source IDs, and OCR bounding boxes.</span>
                      </div>
                    </label>

                    <label className="checkbox-container">
                      <input
                        type="checkbox"
                        checked={settings.auto_advance}
                        onChange={(e) => setSettings({ ...settings, auto_advance: e.target.checked })}
                      />
                      <span className="checkbox-custom"></span>
                      <div className="checkbox-text">
                        <span className="checkbox-title">Auto-Advance Steps on Target Click</span>
                        <span className="checkbox-desc">Automatically steps forward when click tracker detects a click in target bounding box.</span>
                      </div>
                    </label>

                    <label className="checkbox-container">
                      <input
                        type="checkbox"
                        checked={settings.use_omniparser || false}
                        onChange={(e) => setSettings({ ...settings, use_omniparser: e.target.checked })}
                      />
                      <span className="checkbox-custom"></span>
                      <div className="checkbox-text">
                        <span className="checkbox-title">Enable OmniParser Icon Detection</span>
                        <span className="checkbox-desc">Enables visual icon & button detection (YOLOv8 + Florence-2) alongside OCR & UIA.</span>
                      </div>
                    </label>

                    <label className="checkbox-container">
                      <input
                        type="checkbox"
                        checked={settings.use_gpu || false}
                        onChange={(e) => setSettings({ ...settings, use_gpu: e.target.checked })}
                      />
                      <span className="checkbox-custom"></span>
                      <div className="checkbox-text">
                        <span className="checkbox-title">Use CUDA GPU Acceleration</span>
                        <span className="checkbox-desc">Enables CUDA acceleration for OmniParser inference (requires compatible NVIDIA GPU & CUDA).</span>
                      </div>
                    </label>

                    {settings.use_omniparser && (
                      <div className="model-download-section" style={{
                        marginTop: "16px",
                        padding: "16px",
                        background: "rgba(255, 255, 255, 0.03)",
                        border: "1px dashed rgba(255, 255, 255, 0.15)",
                        borderRadius: "8px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "10px"
                      }}>
                        <span className="checkbox-title" style={{ fontSize: "14px", fontWeight: "600", display: "flex", alignItems: "center", gap: "6px" }}>
                          📦 OmniParser Weights & Models (YOLOv8 + Florence-2)
                        </span>
                        <span className="checkbox-desc" style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.4" }}>
                          Real-world visual processing requires downloading model weights (~490MB total). Once downloaded, the application works fully offline.
                        </span>
                        
                        {downloadProgress === null ? (
                          settings.models_downloaded ? (
                            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                              <span style={{ color: "#10b981", fontSize: "13px", fontWeight: "500", display: "flex", alignItems: "center", gap: "6px" }}>
                                ✓ Models fully downloaded and ready for offline use.
                              </span>
                              <button
                                type="button"
                                className="nav-button"
                                style={{
                                  width: "max-content",
                                  alignSelf: "flex-start",
                                  background: "rgba(255, 255, 255, 0.05)",
                                  color: "var(--text-secondary)",
                                  border: "1px solid rgba(255, 255, 255, 0.1)",
                                  padding: "6px 12px",
                                  borderRadius: "4px",
                                  cursor: "pointer",
                                  fontSize: "12px",
                                  fontWeight: "500"
                                }}
                                onClick={handleDownloadModels}
                              >
                                Re-verify / Download Again
                              </button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              className="nav-button active"
                              style={{ 
                                width: "max-content", 
                                alignSelf: "flex-start", 
                                display: "flex", 
                                alignItems: "center", 
                                gap: "6px", 
                                background: "var(--accent-primary)", 
                                color: "white", 
                                padding: "8px 16px",
                                cursor: "pointer",
                                borderRadius: "6px"
                              }}
                              onClick={handleDownloadModels}
                            >
                              Download Models Now
                            </button>
                          )
                        ) : (
                          <div className="download-progress-container" style={{ width: "100%" }}>
                            <div className="download-progress-info" style={{ display: "flex", justifyContent: "space-between", fontSize: "13px", marginBottom: "4px" }}>
                              <span style={{ color: "var(--text-secondary)" }}>{downloadStatus}</span>
                              <strong style={{ color: "var(--accent-primary)" }}>{downloadProgress >= 0 ? `${downloadProgress}%` : ""}</strong>
                            </div>
                            {downloadProgress >= 0 && downloadProgress < 100 && (
                              <div className="progress-bar-container" style={{ background: "rgba(255, 255, 255, 0.1)", height: "8px", borderRadius: "4px", overflow: "hidden", position: "relative", marginBottom: "10px" }}>
                                <div className="progress-bar-fill" style={{
                                  width: `${downloadProgress}%`,
                                  background: "var(--accent-primary)",
                                  height: "100%",
                                  transition: "width 0.25s ease"
                                }}></div>
                              </div>
                            )}
                            {downloadProgress >= 0 && downloadProgress < 100 && (
                              <button
                                type="button"
                                className="nav-button"
                                style={{
                                  background: "rgba(239, 68, 68, 0.15)",
                                  color: "#ef4444",
                                  border: "1px solid rgba(239, 68, 68, 0.3)",
                                  padding: "6px 12px",
                                  borderRadius: "4px",
                                  cursor: "pointer",
                                  fontSize: "12px",
                                  fontWeight: "500",
                                  marginTop: "4px",
                                  transition: "all 0.2s"
                                }}
                                onClick={handleCancelDownload}
                                onMouseEnter={(e) => {
                                  e.currentTarget.style.background = "rgba(239, 68, 68, 0.25)";
                                }}
                                onMouseLeave={(e) => {
                                  e.currentTarget.style.background = "rgba(239, 68, 68, 0.15)";
                                }}
                              >
                                Cancel Download
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <button type="submit" className="save-settings-button">
                    <Save size={16} /> Save Configuration
                  </button>
                </div>
              </form>

              {/* Settings Card Ends */}
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
