import { useState } from 'react';
import { invoke } from '@tauri-apps/api/core';

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

  const WS_URL = 'ws://127.0.0.1:8765/ws';

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
