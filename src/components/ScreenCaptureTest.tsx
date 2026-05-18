import { useState } from 'react';
import { invoke } from '@tauri-apps/api/core';

/**
 * Sprint 2 Test Component
 * Tests screen capture and WebSocket communication
 */
export function ScreenCaptureTest() {
  const [status, setStatus] = useState<string>('Ready');
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [lastCapture, setLastCapture] = useState<{
    width: number;
    height: number;
    size: number;
    timestamp: string;
  } | null>(null);

  const WS_URL = 'ws://127.0.0.1:8765/ws';

  const connectWebSocket = async () => {
    try {
      setStatus('Connecting to WebSocket...');
      await invoke('ws_connect', { url: WS_URL });
      setWsConnected(true);
      setStatus('WebSocket connected');
    } catch (error) {
      setStatus(`WebSocket connection failed: ${error}`);
      setWsConnected(false);
    }
  };

  const captureAndSend = async () => {
    try {
      setStatus('Capturing screenshot...');
      
      // Capture screenshot
      const screenshotData = await invoke<string>('capture_screen');
      
      if (!screenshotData) {
        setStatus('Screenshot capture returned empty data');
        return;
      }

      setStatus('Sending screenshot via WebSocket...');
      
      // Send via WebSocket
      await invoke('ws_send_screenshot', {
        url: WS_URL,
        data: screenshotData,
        width: 1920, // These will be actual values from capture in production
        height: 1080,
      });

      setLastCapture({
        width: 1920,
        height: 1080,
        size: screenshotData.length,
        timestamp: new Date().toISOString(),
      });

      setStatus('Screenshot sent successfully!');
    } catch (error) {
      setStatus(`Error: ${error}`);
    }
  };

  const captureDifferential = async () => {
    try {
      setStatus('Capturing with differential detection...');
      
      const screenshotData = await invoke<string>('capture_screen_diff');
      
      if (!screenshotData || screenshotData.length === 0) {
        setStatus('No changes detected - frame skipped');
        return;
      }

      setStatus('Changes detected, sending screenshot...');
      
      await invoke('ws_send_screenshot', {
        url: WS_URL,
        data: screenshotData,
        width: 1920,
        height: 1080,
      });

      setStatus('Screenshot sent (differential mode)');
    } catch (error) {
      setStatus(`Error: ${error}`);
    }
  };

  const resetDiff = async () => {
    try {
      await invoke('reset_screenshot_diff');
      setStatus('Differential detection reset');
    } catch (error) {
      setStatus(`Error: ${error}`);
    }
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'system-ui' }}>
      <h2>Sprint 2: Screen Capture & WebSocket Test</h2>
      
      <div style={{ marginBottom: '20px' }}>
        <h3>Status</h3>
        <p style={{ 
          padding: '10px', 
          background: '#f0f0f0', 
          borderRadius: '4px',
          fontFamily: 'monospace'
        }}>
          {status}
        </p>
        <p>
          WebSocket: <strong style={{ color: wsConnected ? 'green' : 'red' }}>
            {wsConnected ? 'Connected' : 'Disconnected'}
          </strong>
        </p>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h3>Actions</h3>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button 
            onClick={connectWebSocket}
            style={{ padding: '10px 20px', cursor: 'pointer' }}
          >
            Connect WebSocket
          </button>
          
          <button 
            onClick={captureAndSend}
            disabled={!wsConnected}
            style={{ 
              padding: '10px 20px', 
              cursor: wsConnected ? 'pointer' : 'not-allowed',
              opacity: wsConnected ? 1 : 0.5
            }}
          >
            Capture & Send Screenshot
          </button>
          
          <button 
            onClick={captureDifferential}
            disabled={!wsConnected}
            style={{ 
              padding: '10px 20px', 
              cursor: wsConnected ? 'pointer' : 'not-allowed',
              opacity: wsConnected ? 1 : 0.5
            }}
          >
            Capture (Differential)
          </button>
          
          <button 
            onClick={resetDiff}
            style={{ padding: '10px 20px', cursor: 'pointer' }}
          >
            Reset Diff Detection
          </button>
        </div>
      </div>

      {lastCapture && (
        <div style={{ marginBottom: '20px' }}>
          <h3>Last Capture</h3>
          <ul style={{ fontFamily: 'monospace', fontSize: '14px' }}>
            <li>Dimensions: {lastCapture.width}x{lastCapture.height}</li>
            <li>Data Size: {(lastCapture.size / 1024).toFixed(2)} KB</li>
            <li>Timestamp: {lastCapture.timestamp}</li>
          </ul>
        </div>
      )}

      <div style={{ 
        marginTop: '30px', 
        padding: '15px', 
        background: '#e8f4f8', 
        borderRadius: '4px' 
      }}>
        <h3>Sprint 2 Checklist</h3>
        <ul>
          <li>✓ Screen capture using scrap crate (DXGI)</li>
          <li>✓ JPEG compression with image crate</li>
          <li>✓ Differential screenshot detection</li>
          <li>✓ FastAPI WebSocket endpoint at /ws</li>
          <li>✓ WebSocket client in Rust (tungstenite)</li>
          <li>✓ Typed JSON message protocol</li>
          <li>✓ WebSocket connection manager in Python</li>
          <li>✓ Reconnection logic with exponential backoff</li>
        </ul>
      </div>
    </div>
  );
}
