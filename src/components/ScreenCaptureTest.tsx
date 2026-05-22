import { useState, useEffect, useRef } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { emitTo, listen } from '@tauri-apps/api/event';

interface UIElement {
  id: string;
  type: string;
  text: string;
  bbox: number[];
  confidence: number;
  source: 'ocr' | 'a11y' | 'merged';
  enabled: boolean;
  automation_id: string;
}

/**
 * Sprint 3 Test Component
 * Interactive diagnostic dashboard for Screen Capture & Element Detection Pipeline
 */
export function ScreenCaptureTest() {
  const [status, setStatus] = useState<string>('Ready to initialize pipeline');
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [detectedElements, setDetectedElements] = useState<UIElement[]>([]);
  const [lastCapture, setLastCapture] = useState<{
    width: number;
    height: number;
    size: number;
    timestamp: string;
    elementsCount: number;
  } | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');

  // AI Task Planner states
  const [taskQuery, setTaskQuery] = useState<string>('Click Connect WebSocket button');
  const [planningStatus, setPlanningStatus] = useState<string>('No plan generated yet');
  const [isPlanning, setIsPlanning] = useState<boolean>(false);
  const [generatedPlan, setGeneratedPlan] = useState<{
    task: string;
    error?: string;
    steps: Array<{
      step_number: number;
      description: string;
      target_element_id: string | null;
      action: string;
      bbox: number[] | null;
    }>;
  } | null>(null);

  const [activeStepIndex, setActiveStepIndex] = useState<number | null>(null);

  // Sync refs to prevent state stale closures inside the Tauri global listener
  const activeStepIndexRef = useRef<number | null>(null);
  const generatedPlanRef = useRef<any>(null);

  useEffect(() => {
    activeStepIndexRef.current = activeStepIndex;
  }, [activeStepIndex]);

  useEffect(() => {
    generatedPlanRef.current = generatedPlan;
  }, [generatedPlan]);

  // Listen for native click monitoring events and manual next step clicks from overlay
  useEffect(() => {
    const handleAdvance = () => {
      const prevIndex = activeStepIndexRef.current;
      const plan = generatedPlanRef.current;
      
      console.log("Step progression triggered! Current index:", prevIndex);
      if (prevIndex !== null && plan && plan.steps && prevIndex < (plan.steps.length - 1)) {
        showStepGuidance(prevIndex + 1, plan);
      } else {
        clearStepGuidance();
      }
    };

    const unlistenAuto = listen<any>("auto-advance-step", handleAdvance);
    const unlistenManual = listen<any>("request-next-step", handleAdvance);

    return () => {
      unlistenAuto.then((fn) => fn());
      unlistenManual.then((fn) => fn());
    };
  }, []);

  const WS_URL = 'ws://127.0.0.1:8765/ws?client_id=rust-client';

  const connectWebSocket = async () => {
    try {
      setStatus('Establishing WebSocket handshake...');
      await invoke('ws_connect', { url: WS_URL });
      setWsConnected(true);
      setStatus('WebSocket secure tunnel connected successfully.');
    } catch (error) {
      setStatus(`WebSocket connection failed: ${error}`);
      setWsConnected(false);
    }
  };

  useEffect(() => {
    connectWebSocket();
  }, []);

  const processResponse = (response: any, screenshotSize: number) => {
    if (response && response.type === 'ack' && response.elements) {
      const elements: UIElement[] = response.elements;
      setDetectedElements(elements);
      setLastCapture({
        width: response.width || 1920,
        height: response.height || 1080,
        size: screenshotSize,
        timestamp: new Date().toLocaleTimeString(),
        elementsCount: elements.length,
      });
      setStatus(`Success: Screen parsed! Extracted ${elements.length} interactive elements.`);
    } else {
      setStatus('Screenshot processed, but no UIElements were extracted.');
    }
  };

  const captureAndSend = async () => {
    try {
      setStatus('Triggering DXGI screen capture...');
      const screenshotData = await invoke<string>('capture_screen');
      
      if (!screenshotData) {
        setStatus('Error: Screenshot capture returned empty buffer.');
        return;
      }

      setStatus('Streaming screenshot payload through WebSocket & running ScreenParser...');
      
      const response = await invoke<any>('ws_send_screenshot', {
        url: WS_URL,
        data: screenshotData,
        width: 1920,
        height: 1080,
      });

      processResponse(response, screenshotData.length);
    } catch (error) {
      setStatus(`Pipeline execution error: ${error}`);
    }
  };

  const captureDifferential = async () => {
    try {
      setStatus('Querying screenshot with SHA-256 differential detector...');
      const screenshotData = await invoke<string>('capture_screen_diff');
      
      if (!screenshotData || screenshotData.length === 0) {
        setStatus('No changes detected in display buffer. Frame skipped (network-optimized).');
        return;
      }

      setStatus('Display changes detected. Uploading new frame to parser...');
      
      const response = await invoke<any>('ws_send_screenshot', {
        url: WS_URL,
        data: screenshotData,
        width: 1920,
        height: 1080,
      });

      processResponse(response, screenshotData.length);
    } catch (error) {
      setStatus(`Differential pipeline error: ${error}`);
    }
  };

  const resetDiff = async () => {
    try {
      await invoke('reset_screenshot_diff');
      setStatus('Differential SHA-256 detection registry reset.');
    } catch (error) {
      setStatus(`Error resetting registry: ${error}`);
    }
  };

  const generatePlan = async () => {
    if (!taskQuery.trim()) {
      setPlanningStatus('Please enter a valid task query.');
      return;
    }
    
    setIsPlanning(true);
    setPlanningStatus('Decomposing task query and serializing elements tree...');
    setGeneratedPlan(null);
    
    try {
      const response = await invoke<any>('ws_send_task_start', {
        url: WS_URL,
        query: taskQuery
      });
      
      setIsPlanning(false);
      
      if (response && response.plan) {
        const plan = response.plan;
        if (plan.error) {
          setPlanningStatus(`Failed: ${plan.error}`);
        } else {
          // Intelligent client-side heuristics mapping for element bounding boxes
          if (plan.steps) {
            plan.steps = plan.steps.map((step: any) => {
              const queryLower = step.description.toLowerCase();
              
              // If coordinates are missing, empty, or zero-sized, search for text-based match or taskbar fallback
              const isBboxEmpty = !step.bbox || step.bbox.length !== 4 || (step.bbox[2] === 0 && step.bbox[3] === 0);
              if (isBboxEmpty || !step.target_element_id) {
                 // Heuristic 1: Dynamic application keyword search inside parsed elements list
                 const words = queryLower
                    .replace(/[.,\/#!$%\^&\*;:{}=\-_`~()]/g, "")
                    .split(/\s+/)
                    .filter((w: string) => w.length >= 3);
                 let matchedEl = null;
                 
                 for (const word of words) {
                   // Skip generic terms
                   if (["click", "open", "launch", "icon", "icons", "taskbar", "button", "buttons", "application", "windows", "the", "your", "this", "app", "apps", "shortcut", "shortcuts"].includes(word)) {
                     continue;
                   }
                   
                   matchedEl = detectedElements.find(el => 
                     el.text && el.text.toLowerCase().includes(word)
                   );
                   if (matchedEl) {
                     console.log(`Heuristics Fallback: Dynamic match for keyword '${word}' to element:`, matchedEl);
                     break;
                   }
                 }
                 
                 if (matchedEl) {
                   console.log("Heuristics Fallback: Bound missing step target to element:", matchedEl);
                   return {
                     ...step,
                     target_element_id: matchedEl.id,
                     bbox: matchedEl.bbox
                   };
                 }
                
                // Heuristic 2: Taskbar location geometry mapping fallback for taskbar and icon shortcuts
                if (queryLower.includes("taskbar") || queryLower.includes("docker") || queryLower.includes("slack") || queryLower.includes("icon")) {
                  const screenW = window.screen.width || 1920;
                  const screenH = window.screen.height || 1080;
                  
                  // Center-right Windows 11 pinned buttons alignment coordinate estimation
                  const fallbackX = Math.round(screenW / 2) + 40;
                  const fallbackY = screenH - 24; // Taskbar vertical center
                  
                  console.log(`Heuristics Fallback: Applied estimated taskbar geometry [X=${fallbackX}, Y=${fallbackY}]`);
                  return {
                    ...step,
                    target_element_id: "elem_docker_taskbar_fallback",
                    bbox: [fallbackX - 20, fallbackY - 20, 40, 40]
                  };
                }
              }
              return step;
            });
          }

          setGeneratedPlan(plan);
          setPlanningStatus(`Guidance plan successfully generated! Found ${plan.steps?.length || 0} steps.`);
          // Auto-trigger Step 1 guidance on the transparent overlay!
          if (plan.steps && plan.steps.length > 0) {
            showStepGuidance(0, plan);
          }
        }
      } else if (response && response.error) {
        setPlanningStatus(`Task planning failed: ${response.error}`);
      } else {
        setPlanningStatus('Unexpected response format received from WebSocket.');
      }
    } catch (error) {
      setIsPlanning(false);
      setPlanningStatus(`Task planning error: ${error}`);
    }
  };

  const showStepGuidance = async (index: number, plan = generatedPlan) => {
    if (!plan || !plan.steps || plan.steps.length <= index) return;
    
    const step = plan.steps[index];
    setActiveStepIndex(index);
    
    try {
      // 1. Ensure transparency overlay window is visible
      await invoke('toggle_overlay', { show: true });

      // 2. Register coordinates in Rust for background left-click polling
      if (step.bbox && step.bbox.length === 4 && (step.bbox[2] > 0 || step.bbox[3] > 0)) {
        await invoke('set_active_target_bbox', {
          x: step.bbox[0],
          y: step.bbox[1],
          w: step.bbox[2],
          h: step.bbox[3]
        });
      } else {
        await invoke('set_active_target_bbox', { x: 0, y: 0, w: 0, h: 0 });
      }
      
      // 3. Emit active guidance hint directly to the overlay window
      await emitTo('overlay', 'show-guidance-hint', {
        step_number: step.step_number,
        total_steps: plan.steps.length,
        description: step.description,
        action: step.action,
        bbox: step.bbox,
        target_element_id: step.target_element_id
      });
      
      setStatus(`Overlay guidance active: Step ${step.step_number} ("${step.description}")`);
    } catch (err) {
      setStatus(`Failed to trigger overlay: ${err}`);
    }
  };

  const clearStepGuidance = async () => {
    setActiveStepIndex(null);
    try {
      // 1. Clear coordinates in Rust to stop polling
      await invoke('set_active_target_bbox', { x: 0, y: 0, w: 0, h: 0 });

      // 2. Emit clear event directly to the overlay window
      await emitTo('overlay', 'clear-guidance-hint', {});
      
      // 3. Hide overlay window in Rust
      await invoke('toggle_overlay', { show: false });
      
      setStatus('Overlay guidance cleared.');
    } catch (err) {
      setStatus(`Failed to clear overlay: ${err}`);
    }
  };

  // Filter elements by user query
  const filteredElements = detectedElements.filter(el => {
    const query = searchQuery.toLowerCase();
    return (
      el.text.toLowerCase().includes(query) ||
      el.type.toLowerCase().includes(query) ||
      el.source.toLowerCase().includes(query) ||
      el.automation_id.toLowerCase().includes(query)
    );
  });

  return (
    <div style={{
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '40px 20px',
      fontFamily: "'Inter', system-ui, sans-serif",
      color: '#f4f4f5',
      background: '#09090b',
      minHeight: '100vh'
    }}>
      {/* Header section with glassmorphic glow */}
      <div style={{
        background: 'linear-gradient(135deg, #18181b 0%, #09090b 100%)',
        border: '1px solid #27272a',
        borderRadius: '16px',
        padding: '30px',
        marginBottom: '30px',
        position: 'relative',
        overflow: 'hidden',
        boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.5)'
      }}>
        <div style={{
          position: 'absolute',
          top: '-50px',
          right: '-50px',
          width: '200px',
          height: '200px',
          background: 'rgba(59, 130, 246, 0.15)',
          borderRadius: '50%',
          filter: 'blur(60px)',
          zIndex: 0
        }} />

        <h1 style={{
          fontSize: '28px',
          fontWeight: 700,
          margin: '0 0 10px 0',
          background: 'linear-gradient(90deg, #60a5fa 0%, #a78bfa 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          zIndex: 1,
          position: 'relative'
        }}>
          Sprint 3: OCR & Element Detection Pipeline
        </h1>
        <p style={{ color: '#a1a1aa', fontSize: '15px', margin: 0, zIndex: 1, position: 'relative' }}>
          Real-time UI analysis combining PaddleOCR v4 text extraction and Windows Accessibility UIA tree structures.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2.5fr', gap: '30px' }}>
        {/* Sidebar Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{
            background: '#18181b',
            border: '1px solid #27272a',
            borderRadius: '12px',
            padding: '20px',
            boxShadow: '0 4px 20px rgba(0,0,0,0.2)'
          }}>
            <h3 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 15px 0', color: '#e4e4e7' }}>
              Connection Status
            </h3>
            
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px',
              background: '#09090b',
              border: '1px solid #27272a',
              borderRadius: '8px',
              marginBottom: '15px'
            }}>
              <span style={{ fontSize: '13px', color: '#a1a1aa' }}>WebSocket Backend</span>
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '12px',
                fontWeight: 600,
                color: wsConnected ? '#10b981' : '#ef4444'
              }}>
                <span style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: wsConnected ? '#10b981' : '#ef4444',
                  boxShadow: wsConnected ? '0 0 8px #10b981' : 'none'
                }} />
                {wsConnected ? 'ACTIVE' : 'DISCONNECTED'}
              </span>
            </div>

            <button
              onClick={connectWebSocket}
              style={{
                width: '100%',
                padding: '12px',
                background: wsConnected ? 'transparent' : '#2563eb',
                border: wsConnected ? '1px solid #27272a' : 'none',
                color: '#ffffff',
                borderRadius: '8px',
                fontSize: '14px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                if (!wsConnected) e.currentTarget.style.background = '#1d4ed8';
              }}
              onMouseLeave={(e) => {
                if (!wsConnected) e.currentTarget.style.background = '#2563eb';
              }}
            >
              {wsConnected ? 'Reconnect WebSocket' : 'Connect WebSocket'}
            </button>
          </div>

          <div style={{
            background: '#18181b',
            border: '1px solid #27272a',
            borderRadius: '12px',
            padding: '20px',
            boxShadow: '0 4px 20px rgba(0,0,0,0.2)'
          }}>
            <h3 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 15px 0', color: '#e4e4e7' }}>
              Pipeline Operations
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <button
                onClick={captureAndSend}
                disabled={!wsConnected}
                style={{
                  padding: '12px',
                  background: wsConnected ? '#10b981' : '#27272a',
                  color: wsConnected ? '#ffffff' : '#71717a',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: wsConnected ? 'pointer' : 'not-allowed',
                  transition: 'all 0.2s',
                }}
              >
                Capture & Parse Elements
              </button>

              <button
                onClick={captureDifferential}
                disabled={!wsConnected}
                style={{
                  padding: '12px',
                  background: wsConnected ? '#8b5cf6' : '#27272a',
                  color: wsConnected ? '#ffffff' : '#71717a',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: wsConnected ? 'pointer' : 'not-allowed',
                  transition: 'all 0.2s',
                }}
              >
                Differential Parse
              </button>

              <button
                onClick={resetDiff}
                style={{
                  padding: '12px',
                  background: 'transparent',
                  color: '#e4e4e7',
                  border: '1px solid #27272a',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => e.currentTarget.style.borderColor = '#52525b'}
                onMouseLeave={(e) => e.currentTarget.style.borderColor = '#27272a'}
              >
                Reset Differential Cache
              </button>
            </div>
          </div>

          {/* Diagnostic Stats */}
          {lastCapture && (
            <div style={{
              background: '#18181b',
              border: '1px solid #27272a',
              borderRadius: '12px',
              padding: '20px',
              fontSize: '13px'
            }}>
              <h3 style={{ fontSize: '15px', fontWeight: 600, margin: '0 0 12px 0', color: '#e4e4e7' }}>
                Frame Telemetry
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontFamily: 'monospace' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#a1a1aa' }}>Canvas Size:</span>
                  <span>{lastCapture.width}x{lastCapture.height}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#a1a1aa' }}>Payload:</span>
                  <span>{(lastCapture.size / 1024).toFixed(1)} KB</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#a1a1aa' }}>Elements:</span>
                  <span style={{ color: '#60a5fa', fontWeight: 'bold' }}>{lastCapture.elementsCount}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#a1a1aa' }}>Timestamp:</span>
                  <span>{lastCapture.timestamp}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Console & Results Table */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Active Status Console */}
          <div style={{
            background: '#18181b',
            border: '1px solid #27272a',
            borderRadius: '12px',
            padding: '16px 20px',
            fontFamily: 'monospace',
            fontSize: '13px',
            boxShadow: '0 4px 20px rgba(0,0,0,0.1)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ color: '#a1a1aa', fontWeight: 'bold' }}>SYSTEM:</span>
              <span style={{ color: '#38bdf8' }}>{status}</span>
            </div>
          </div>

          {/* AI Task Orchestrator & Action Planner Deck */}
          <div style={{
            background: 'linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%)',
            border: '1px solid #312e81',
            borderRadius: '12px',
            padding: '24px',
            boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.4)',
            display: 'flex',
            flexDirection: 'column',
            gap: '15px'
          }}>
            <h3 style={{ fontSize: '18px', fontWeight: 600, margin: 0, color: '#c084fc', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>🧠</span> AI Guidance Orchestrator & Action Planner
            </h3>
            
            <div style={{ display: 'flex', gap: '10px' }}>
              <input
                type="text"
                value={taskQuery}
                onChange={(e) => setTaskQuery(e.target.value)}
                placeholder="Enter desktop task (e.g. 'Click Connect WebSocket button', 'Open Slack'...)"
                disabled={!wsConnected || isPlanning}
                style={{
                  flex: 1,
                  background: '#020617',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  color: '#f8fafc',
                  padding: '12px 16px',
                  fontSize: '14px',
                  outline: 'none',
                  opacity: wsConnected ? 1 : 0.6
                }}
              />
              
              <button
                onClick={generatePlan}
                disabled={!wsConnected || isPlanning}
                style={{
                  background: wsConnected ? 'linear-gradient(135deg, #a855f7 0%, #7c3aed 100%)' : '#334155',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '0 24px',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: wsConnected && !isPlanning ? 'pointer' : 'not-allowed',
                  transition: 'opacity 0.2s'
                }}
              >
                {isPlanning ? 'Planning...' : 'Decompose & Plan'}
              </button>
            </div>
            
            <div style={{
              fontFamily: 'monospace',
              fontSize: '12px',
              color: '#94a3b8',
              background: 'rgba(15, 23, 42, 0.6)',
              padding: '10px 14px',
              border: '1px solid #1e293b',
              borderRadius: '6px'
            }}>
              <span style={{ fontWeight: 'bold', color: '#c084fc' }}>PLANNER STATUS:</span> {planningStatus}
            </div>
            
            {/* Steps Roadmap Render */}
            {generatedPlan && (
              <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                  <h4 style={{ fontSize: '14px', fontWeight: 600, margin: 0, color: '#cbd5e1' }}>
                    Step-by-Step Guidance Roadmap:
                  </h4>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      onClick={clearStepGuidance}
                      style={{
                        background: 'rgba(239, 68, 68, 0.1)',
                        color: '#f87171',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        borderRadius: '4px',
                        padding: '4px 10px',
                        fontSize: '11px',
                        fontWeight: 600,
                        cursor: 'pointer'
                      }}
                    >
                      Clear Overlay
                    </button>
                    {activeStepIndex !== null && activeStepIndex < (generatedPlan.steps.length - 1) && (
                      <button
                        onClick={() => showStepGuidance(activeStepIndex + 1)}
                        style={{
                          background: 'rgba(168, 85, 247, 0.15)',
                          color: '#c084fc',
                          border: '1px solid rgba(168, 85, 247, 0.4)',
                          borderRadius: '4px',
                          padding: '4px 10px',
                          fontSize: '11px',
                          fontWeight: 600,
                          cursor: 'pointer'
                        }}
                      >
                        Next Step →
                      </button>
                    )}
                  </div>
                </div>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {generatedPlan.steps.map((step) => {
                    let actionBadgeColor = '#38bdf8';
                    let actionBg = 'rgba(56, 189, 248, 0.1)';
                    if (step.action === 'done') {
                      actionBadgeColor = '#34d399';
                      actionBg = 'rgba(52, 211, 153, 0.1)';
                    } else if (step.action === 'click') {
                      actionBadgeColor = '#fbbf24';
                      actionBg = 'rgba(251, 191, 36, 0.1)';
                    }
                    
                    const isActive = activeStepIndex === (step.step_number - 1);
                    
                    return (
                      <div
                        key={step.step_number}
                        onClick={() => showStepGuidance(step.step_number - 1)}
                        style={{
                          background: isActive ? 'rgba(124, 58, 237, 0.12)' : 'rgba(30, 41, 59, 0.5)',
                          border: isActive ? '1px solid #c084fc' : '1px solid #334155',
                          boxShadow: isActive ? '0 0 15px rgba(192, 132, 252, 0.25)' : 'none',
                          borderRadius: '8px',
                          padding: '12px 16px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '15px',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease-in-out'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                          <span style={{
                            width: '24px',
                            height: '24px',
                            borderRadius: '50%',
                            background: isActive ? '#c084fc' : '#7c3aed',
                            color: '#ffffff',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '12px',
                            fontWeight: 'bold',
                            boxShadow: isActive ? '0 0 8px #c084fc' : 'none'
                          }}>
                            {step.step_number}
                          </span>
                          
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                            <span style={{
                              fontSize: '13px',
                              color: isActive ? '#ffffff' : '#f1f5f9',
                              fontWeight: isActive ? 600 : 500
                            }}>
                              {step.description}
                            </span>
                            {step.target_element_id && (
                              <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                                Target ID: <strong style={{ color: '#fbbf24' }}>{step.target_element_id}</strong>
                                {step.bbox && ` | Coordinates: [${step.bbox.join(', ')}]`}
                              </span>
                            )}
                          </div>
                        </div>
                        
                        <span style={{
                          color: actionBadgeColor,
                          background: actionBg,
                          border: `1px solid ${actionBadgeColor}44`,
                          padding: '3px 8px',
                          borderRadius: '12px',
                          fontSize: '11px',
                          fontWeight: 600,
                          textTransform: 'uppercase'
                        }}>
                          {step.action}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Element List View */}
          <div style={{
            background: '#18181b',
            border: '1px solid #27272a',
            borderRadius: '12px',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
            minHeight: '400px'
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '15px'
            }}>
              <div>
                <h3 style={{ fontSize: '18px', fontWeight: 600, margin: '0 0 4px 0', color: '#e4e4e7' }}>
                  UI Registry
                </h3>
                <span style={{ fontSize: '13px', color: '#71717a' }}>
                  Showing {filteredElements.length} of {detectedElements.length} elements detected
                </span>
              </div>

              {/* Search Bar */}
              <input
                type="text"
                placeholder="Search by text, control type, source..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  background: '#09090b',
                  border: '1px solid #27272a',
                  borderRadius: '8px',
                  color: '#f4f4f5',
                  padding: '8px 16px',
                  fontSize: '14px',
                  width: '260px',
                  outline: 'none',
                }}
              />
            </div>

            {/* Table layout */}
            <div style={{ overflowX: 'auto' }}>
              {filteredElements.length > 0 ? (
                <table style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  fontSize: '13px',
                  textAlign: 'left'
                }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #27272a', color: '#a1a1aa' }}>
                      <th style={{ padding: '12px 8px', fontWeight: 500 }}>ID</th>
                      <th style={{ padding: '12px 8px', fontWeight: 500 }}>Type</th>
                      <th style={{ padding: '12px 8px', fontWeight: 500 }}>Visual Text</th>
                      <th style={{ padding: '12px 8px', fontWeight: 500 }}>Bounding Box</th>
                      <th style={{ padding: '12px 8px', fontWeight: 500 }}>Source</th>
                      <th style={{ padding: '12px 8px', fontWeight: 500 }}>Automation ID</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredElements.map((el) => {
                      // Visual formatting based on element source
                      let sourceColor = '#3b82f6';
                      let sourceBg = 'rgba(59, 130, 246, 0.1)';
                      if (el.source === 'a11y') {
                        sourceColor = '#10b981';
                        sourceBg = 'rgba(16, 185, 129, 0.1)';
                      } else if (el.source === 'merged') {
                        sourceColor = '#a78bfa';
                        sourceBg = 'rgba(167, 139, 250, 0.1)';
                      }

                      return (
                        <tr 
                          key={el.id} 
                          style={{ 
                            borderBottom: '1px solid #27272a',
                            transition: 'background 0.2s',
                            cursor: 'default'
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.background = '#27272a'}
                          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                        >
                          <td style={{ padding: '14px 8px', fontWeight: 600, color: '#f4f4f5' }}>
                            {el.id}
                          </td>
                          <td style={{ padding: '14px 8px' }}>
                            <span style={{
                              background: '#27272a',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              fontSize: '11px',
                              color: '#d4d4d8'
                            }}>
                              {el.type}
                            </span>
                          </td>
                          <td style={{ 
                            padding: '14px 8px', 
                            color: el.text ? '#e4e4e7' : '#71717a',
                            fontStyle: el.text ? 'normal' : 'italic',
                            maxWidth: '180px',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap'
                          }}>
                            {el.text || 'No label'}
                          </td>
                          <td style={{ padding: '14px 8px', fontFamily: 'monospace', color: '#a1a1aa' }}>
                            [{el.bbox.join(', ')}]
                          </td>
                          <td style={{ padding: '14px 8px' }}>
                            <span style={{
                              color: sourceColor,
                              background: sourceBg,
                              border: `1px solid ${sourceColor}44`,
                              padding: '3px 8px',
                              borderRadius: '20px',
                              fontSize: '11px',
                              fontWeight: 600,
                              textTransform: 'uppercase'
                            }}>
                              {el.source}
                            </span>
                          </td>
                          <td style={{ 
                            padding: '14px 8px', 
                            color: '#71717a', 
                            fontFamily: 'monospace',
                            fontSize: '12px' 
                          }}>
                            {el.automation_id || 'n/a'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : (
                <div style={{
                  padding: '60px 0',
                  textAlign: 'center',
                  color: '#71717a'
                }}>
                  <div style={{ fontSize: '32px', marginBottom: '10px' }}>🔍</div>
                  <h4 style={{ margin: '0 0 6px 0', color: '#e4e4e7' }}>No elements captured yet</h4>
                  <p style={{ fontSize: '13px', margin: 0 }}>
                    Connect to the WebSocket and click "Capture & Parse Elements" to analyze your desktop.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
