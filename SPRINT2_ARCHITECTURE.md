# Sprint 2 Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         StepPilot System                         │
│                      (Sprint 2 Components)                       │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│                  │         │                  │         │                  │
│  React Frontend  │◄───────►│   Rust Backend   │◄───────►│ Python Backend   │
│   (TypeScript)   │  Tauri  │     (Tauri)      │   WS    │    (FastAPI)     │
│                  │   IPC   │                  │         │                  │
└──────────────────┘         └──────────────────┘         └──────────────────┘
        │                            │                            │
        │                            │                            │
        ▼                            ▼                            ▼
  ┌──────────┐              ┌──────────────┐            ┌──────────────┐
  │   UI     │              │   Screen     │            │   Message    │
  │Components│              │   Capture    │            │   Handlers   │
  └──────────┘              └──────────────┘            └──────────────┘
```

## Component Details

### 1. React Frontend (TypeScript)

```
src/
├── App.tsx                    # Main app with Sprint 2 test tab
└── components/
    └── ScreenCaptureTest.tsx  # Test UI for Sprint 2 features
```

**Responsibilities:**
- User interface for testing
- Invoke Tauri commands
- Display status and results
- Handle user interactions

**Key Functions:**
```typescript
invoke('ws_connect', { url })
invoke('capture_screen')
invoke('capture_screen_diff')
invoke('ws_send_screenshot', { url, data, width, height })
```

### 2. Rust Backend (Tauri)

```
src-tauri/src/
├── lib.rs           # Command registration
├── capture.rs       # Screen capture implementation
└── ws_client.rs     # WebSocket client
```

**Responsibilities:**
- Screen capture (DXGI)
- JPEG compression
- Base64 encoding
- WebSocket client
- Differential detection

**Data Flow:**
```
Display → Capturer → Frame (BGRA) → Convert (RGBA) → 
ImageBuffer → JPEG Encode → Base64 → WebSocket Send
```

### 3. Python Backend (FastAPI)

```
backend/
├── main.py              # FastAPI app & message handlers
└── core/
    └── ws_manager.py    # Connection manager
```

**Responsibilities:**
- WebSocket server
- Message routing
- Screenshot processing
- Connection management
- Health checks

**Message Flow:**
```
WebSocket Receive → Parse JSON → Route to Handler → 
Process → Send Response
```

## Message Protocol

### Message Types & Flow

```
┌─────────────┐                                    ┌─────────────┐
│             │  1. screenshot                     │             │
│    Rust     │───────────────────────────────────►│   Python    │
│   Client    │                                    │   Server    │
│             │  2. ack                            │             │
│             │◄───────────────────────────────────│             │
└─────────────┘                                    └─────────────┘
       │                                                  │
       │  3. ping (every 10s)                            │
       │─────────────────────────────────────────────────►
       │                                                  │
       │  4. pong                                         │
       │◄─────────────────────────────────────────────────
       │                                                  │
```

### Message Structure

```typescript
// Screenshot Message
{
  type: "screenshot",
  data: "base64_jpeg_string...",
  width: 1920,
  height: 1080,
  timestamp: 1234567890
}

// Acknowledgement
{
  type: "ack",
  received: "screenshot",
  width: 1920,
  height: 1080,
  size_bytes: 150000
}

// Error
{
  type: "error",
  message: "Error description",
  code: "ERROR_CODE"
}

// Health Check
{ type: "ping" }
{ type: "pong" }
```

## Screen Capture Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    Screen Capture Flow                       │
└─────────────────────────────────────────────────────────────┘

1. Get Primary Display
   └─► Display::primary()

2. Create Capturer
   └─► Capturer::new(display)

3. Wait for Frame
   └─► capturer.frame() [with retry on WouldBlock]

4. Convert BGRA → RGBA
   └─► Swap R and B channels

5. Create ImageBuffer
   └─► ImageBuffer::from_raw(width, height, rgba_data)

6. Differential Check (if enabled)
   ├─► Compute SHA-256 hash
   ├─► Compare with previous hash
   └─► Skip if unchanged

7. JPEG Compression
   └─► img.write_to(buffer, ImageFormat::Jpeg)
   └─► Quality: 75

8. Base64 Encoding
   └─► general_purpose::STANDARD.encode(jpeg_buffer)

9. Return base64 string
```

## WebSocket Connection Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                  Connection Lifecycle                        │
└─────────────────────────────────────────────────────────────┘

[Disconnected]
      │
      │ connect()
      ▼
[Connecting] ──────► [Failed] ──┐
      │                         │
      │ Success                 │ Retry with
      ▼                         │ exponential backoff
[Connected] ◄───────────────────┘
      │
      │ Health check every 10s
      │ (ping/pong)
      │
      │ Connection lost
      ▼
[Reconnecting] ──► [Exponential Backoff]
      │                    │
      │                    │ 1s, 2s, 4s, 8s, 16s...
      │                    │ Max 10 attempts
      │                    │
      └────────────────────┘
```

## Differential Detection Algorithm

```
┌─────────────────────────────────────────────────────────────┐
│              Differential Detection Logic                    │
└─────────────────────────────────────────────────────────────┘

capture_screen_diff() called
      │
      ▼
Capture screenshot
      │
      ▼
Compute SHA-256 hash
      │
      ▼
┌─────────────────┐
│ Previous hash   │ No ──► Store current hash
│ exists?         │        Return screenshot
└─────────────────┘
      │ Yes
      ▼
┌─────────────────┐
│ Hashes match?   │ Yes ──► Return empty string
└─────────────────┘        (skip transmission)
      │ No
      ▼
Store current hash
Return screenshot
```

## Connection Manager Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              WsConnectionManager (Python)                    │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  active_connections: Dict[str, WebSocket]                    │
│  message_handlers: Dict[str, Callable]                       │
│  _health_check_tasks: Dict[str, asyncio.Task]                │
└──────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
  ┌──────────┐      ┌──────────┐    ┌──────────┐
  │ connect  │      │  listen  │    │  send    │
  └──────────┘      └──────────┘    └──────────┘
        │                 │                 │
        ▼                 ▼                 ▼
  Accept WS         Receive msg      Send JSON
  Start health      Route handler    to client
  check task        Handle errors    
```

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Error Handling                            │
└─────────────────────────────────────────────────────────────┘

Error Occurs
      │
      ▼
┌─────────────────┐
│ Error Type?     │
└─────────────────┘
      │
      ├─► Capture Error ──► Log + Return error string
      │
      ├─► WS Send Error ──► Log + Attempt reconnect
      │
      ├─► WS Receive Error ──► Log + Close connection
      │
      ├─► Handler Error ──► Log + Send error message
      │
      └─► JSON Parse Error ──► Log + Send error message
```

## Performance Characteristics

```
┌─────────────────────────────────────────────────────────────┐
│                  Performance Metrics                         │
└─────────────────────────────────────────────────────────────┘

Screen Capture (DXGI)        │████████░░│  50-100ms
JPEG Compression (Q75)       │████░░░░░░│  20-50ms
Base64 Encoding              │██░░░░░░░░│  10-20ms
WebSocket Send (local)       │█░░░░░░░░░│  1-5ms
Python Receive & Decode      │██░░░░░░░░│  10-20ms
                             └───────────┘
Total End-to-End Latency:    100-200ms

Bandwidth (per screenshot):
- Raw RGBA: ~8MB (1920x1080x4)
- JPEG Q75: ~150KB (98% reduction)
- Base64: ~200KB (33% overhead)
```

## Security Considerations

```
┌─────────────────────────────────────────────────────────────┐
│                  Security Features                           │
└─────────────────────────────────────────────────────────────┘

1. Local-only WebSocket
   └─► Bound to 127.0.0.1 (no external access)

2. No authentication (local trust)
   └─► Backend and frontend on same machine

3. Message validation
   └─► JSON schema validation
   └─► Type checking with Serde/Pydantic

4. Error sanitization
   └─► No stack traces to frontend
   └─► Structured error messages

5. Resource limits
   └─► Max reconnection attempts: 10
   └─► Health check timeout: 10s
```

## Future Enhancements (Post-Sprint 2)

```
┌─────────────────────────────────────────────────────────────┐
│              Planned Improvements                            │
└─────────────────────────────────────────────────────────────┘

1. Multi-monitor support
   └─► Capture specific displays
   └─► Stitch multiple displays

2. Binary WebSocket frames
   └─► Remove base64 overhead
   └─► Direct binary transmission

3. Adaptive quality
   └─► Adjust JPEG quality based on bandwidth
   └─► Higher quality for static screens

4. Compression algorithms
   └─► WebP for better compression
   └─► AVIF for even better compression

5. Incremental updates
   └─► Send only changed regions
   └─► Delta encoding
```

---

**Architecture Version**: Sprint 2  
**Last Updated**: May 18, 2026  
**Status**: Production Ready
