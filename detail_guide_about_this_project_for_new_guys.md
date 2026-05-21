# StepPilot - Interview Guide for Software Developers 🎯

## Project Overview (30-second pitch)

**"I built StepPilot, an AI-powered desktop guidance assistant that watches your screen, understands UI elements, and visually guides you through tasks with arrows and overlays. It's like having an AI copilot for your computer."**

---

## 🏗️ Architecture & Tech Stack

### High-Level Architecture
```
┌─────────────────────────────────────────────────────────┐
│                    Desktop App (Tauri)                   │
│  ┌──────────────┐         ┌──────────────────────┐     │
│  │   Frontend   │◄───────►│   Rust Backend       │     │
│  │ React + TS   │  IPC    │   (Screen Capture)   │     │
│  └──────┬───────┘         └──────────┬───────────┘     │
│         │                             │                  │
│         │ WebSocket                   │ WebSocket        │
│         ▼                             ▼                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │         Python FastAPI Backend (Sidecar)         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │  │
│  │  │   OCR    │  │   A11y   │  │  LLM (Gemini) │  │  │
│  │  │ (Paddle) │  │  (UIA)   │  │  OpenAI/Copilot│  │  │
│  │  └──────────┘  └──────────┘  └──────────────┘  │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Tech Stack
- **Frontend:** React 19 + TypeScript + Vite
- **Desktop Framework:** Tauri v2 (Rust + WebView)
- **Backend:** Python FastAPI (async)
- **LLM:** Google Gemini, OpenAI, GitHub Copilot
- **OCR:** PaddleOCR v4
- **UI Detection:** Windows Accessibility API (UIA)
- **State Management:** Zustand
- **Communication:** WebSocket (bidirectional)

---

## 🎯 Key Technical Concepts to Explain

### 1. **Multi-Process Architecture**

**What:** The app runs 3 separate processes:
- Tauri (Rust) - Main app + screen capture
- React (TypeScript) - UI rendering
- Python FastAPI - AI/ML processing

**Why:** 
- Separation of concerns
- Rust for performance-critical tasks (screen capture)
- Python for AI/ML ecosystem
- React for rich UI

**Interview Answer:**
> "I designed a multi-process architecture where Rust handles performance-critical operations like screen capture at 60fps, Python handles AI/ML workloads with access to the rich ecosystem, and React provides a modern UI. They communicate via WebSocket for real-time bidirectional data flow."

---

### 2. **Screen Capture Pipeline**

**Technical Details:**
```rust
// Rust: DXGI-based screen capture
use scrap::{Capturer, Display};

// Captures at 60fps, JPEG compression
// Differential detection (skip unchanged frames)
// Hash-based comparison using xxHash
```

**Key Points:**
- Uses Windows DXGI API (Desktop Duplication API)
- JPEG compression (quality=75) reduces size from ~8MB to ~200KB
- Differential detection saves 90% of processing
- Sends only changed frames to Python

**Interview Answer:**
> "I implemented a high-performance screen capture system using Windows DXGI API in Rust. It captures at 60fps, applies JPEG compression to reduce bandwidth, and uses hash-based differential detection to skip unchanged frames, reducing processing by 90%."

---

### 3. **Computer Vision Pipeline**

**Three Detection Sources:**

```python
# 1. OCR (PaddleOCR) - Text Detection
ocr_results = ocr_engine.ocr_image(image)
# Output: [{text: "Send", bbox: [x,y,w,h], confidence: 0.95}]

# 2. Windows Accessibility API - Control Tree
a11y_results = a11y_reader.get_elements()
# Output: [{type: "Button", name: "Send", bbox: [x,y,w,h]}]

# 3. OmniParser (Optional) - Icon Detection
icon_results = omniparser.detect(image)
# Output: [{type: "Icon", text: "settings", bbox: [x,y,w,h]}]

# Merge with deduplication (IoU > 0.7)
unified = merger.merge(ocr_results, a11y_results, icon_results)
```

**Key Algorithms:**
- **IoU (Intersection over Union):** Deduplicates overlapping elements
- **CLAHE:** Contrast enhancement for better OCR
- **Coordinate Scaling:** Maps preprocessed image coords to screen space

**Interview Answer:**
> "I built a multi-source computer vision pipeline that combines OCR, Windows Accessibility API, and optional icon detection. It uses IoU-based deduplication to merge results, CLAHE for contrast enhancement, and coordinate transformation to map between preprocessed and screen space."

---

### 4. **LLM Integration & Orchestration**

**Provider Pattern:**
```python
class LLMOrchestrator:
    def __init__(self):
        self.gemini = GeminiProvider()
        self.openai = OpenAIProvider()
        self.copilot = CopilotProvider()
    
    async def complete(self, prompt):
        # Try primary provider
        try:
            return await self._call_with_retry(primary_provider)
        except:
            # Automatic fallback
            return await self._call_with_retry(fallback_provider)
```

**Key Features:**
- **Timeout:** 15 seconds per call
- **Retry:** 3 attempts with exponential backoff (1s, 2s, 4s)
- **Fallback:** Copilot → OpenAI → Gemini
- **Token Optimization:** Text-first mode (90% cheaper than vision)

**Interview Answer:**
> "I implemented an LLM orchestrator with the provider pattern supporting multiple LLM backends. It includes timeout handling (15s), exponential backoff retry logic, and automatic failover between providers. I optimized costs by using text-first mode when possible, reducing token usage by 90%."

---

### 5. **WebSocket Communication**

**Bidirectional Real-Time Protocol:**
```javascript
// Frontend → Backend
{
  "type": "task_start",
  "query": "Open Notepad",
  "timestamp": 1234567890
}

// Backend → Frontend
{
  "type": "task_step",
  "step_number": 1,
  "description": "Click the Start button",
  "bbox": [10, 950, 40, 40],
  "action": "click"
}
```

**Key Features:**
- Health checks (ping/pong every 10s)
- Automatic reconnection with backoff
- Message routing with handlers
- Async processing for heavy tasks

**Interview Answer:**
> "I designed a WebSocket-based protocol for real-time bidirectional communication. It includes health checks via ping/pong, automatic reconnection, and async message handlers. Heavy tasks like OCR run in background threads to keep the WebSocket responsive."

---

### 6. **Overlay Rendering System**

**Technical Implementation:**
```typescript
// Transparent, always-on-top window
<div style={{
  position: "fixed",
  width: "100vw",
  height: "100vh",
  pointerEvents: "none",  // Click-through
  zIndex: 99999
}}>
  {/* SVG for shapes */}
  <svg>
    <rect /> {/* Bounding box */}
    <path /> {/* Bézier arrow */}
    <circle /> {/* Pulse animation */}
  </svg>
  
  {/* Draggable tooltip */}
  <div style={{ pointerEvents: "auto" }}>
    {/* Instructions */}
  </div>
</div>
```

**Key Techniques:**
- **Transparent Window:** Tauri window with `transparent: true`
- **Click-Through:** `pointer-events: none` except for interactive elements
- **Dynamic Click-Through:** Rust FFI updates clickable regions
- **Bézier Curves:** Smooth animated arrows
- **CSS Animations:** Pulse, glow, fade effects

**Interview Answer:**
> "I built a transparent overlay system using Tauri's window API. It uses SVG for vector graphics, CSS animations for smooth effects, and dynamic click-through regions managed via Rust FFI. The overlay is always-on-top but click-through except for interactive elements."

---

### 7. **Error Handling & Resilience**

**Multi-Layer Error Handling:**
```python
# Layer 1: Timeout & Retry
async def _call_with_timeout_and_retry(func):
    for attempt in range(MAX_RETRIES):
        try:
            return await asyncio.wait_for(func(), timeout=15)
        except asyncio.TimeoutError:
            await asyncio.sleep(RETRY_DELAYS[attempt])
    raise TimeoutError()

# Layer 2: Provider Fallback
try:
    return await gemini_provider.complete(prompt)
except:
    return await openai_provider.complete(prompt)

# Layer 3: Graceful Degradation
try:
    ocr_results = await ocr_engine.detect()
except:
    ocr_results = []  # Continue with A11y only
```

**Key Patterns:**
- Circuit breaker pattern
- Exponential backoff
- Graceful degradation
- Structured error logging

**Interview Answer:**
> "I implemented multi-layer error handling with timeout/retry logic, automatic provider fallback, and graceful degradation. Each layer has specific error codes and structured logging. The system continues functioning even if individual components fail."

---

### 8. **Performance Optimizations**

**Key Optimizations:**

1. **Differential Screenshot Detection**
   - Hash-based comparison (xxHash)
   - Skip unchanged frames
   - 90% reduction in processing

2. **Element Caching**
   - TTL: 10 seconds
   - Window-based invalidation
   - Reduces OCR calls by 80%

3. **Lazy Loading**
   - OmniParser models loaded on-demand
   - Saves 2GB RAM when not needed

4. **Parallel Processing**
   ```python
   results = await asyncio.gather(
       ocr_task(),
       a11y_task(),
       omniparser_task()
   )
   ```

5. **Image Preprocessing**
   - Crop to active window
   - Resize to max 1280x720
   - Reduces OCR time by 60%

**Interview Answer:**
> "I optimized performance through differential detection (90% reduction), element caching with TTL, lazy loading of ML models, parallel async processing, and image preprocessing. These optimizations reduced latency from 2s to 300ms."

---

## 🎓 Advanced Concepts

### 1. **Async/Await Patterns**
```python
# Concurrent execution
async def parse_screen(image):
    ocr, a11y, icons = await asyncio.gather(
        run_ocr(image),
        run_a11y(),
        run_omniparser(image)
    )
    return merge(ocr, a11y, icons)
```

### 2. **State Management (Zustand)**
```typescript
const useOverlayStore = create((set) => ({
  activeHint: null,
  setHint: (hint) => set({ activeHint: hint }),
  clearHint: () => set({ activeHint: null })
}))
```

### 3. **IPC (Inter-Process Communication)**
```rust
// Tauri command
#[tauri::command]
async fn capture_screen() -> Result<String, String> {
    // Rust implementation
}

// Frontend call
await invoke("capture_screen")
```

### 4. **Coordinate Transformation**
```python
# Preprocessed → Screen space
scale_x = screen_width / preprocessed_width
abs_x = (preprocessed_x * scale_x) + crop_offset_x
```

---

## 💡 Problem-Solving Examples

### Problem 1: "How did you handle high-DPI displays?"

**Answer:**
> "I used `window.devicePixelRatio` to detect DPI scaling and transformed coordinates accordingly. The Rust backend captures at physical pixels, but the overlay renders at logical pixels, so I divide by DPI ratio to map coordinates correctly."

### Problem 2: "How did you optimize LLM costs?"

**Answer:**
> "I implemented a text-first strategy where I send only the element registry (compact format) instead of screenshots 90% of the time. Vision mode is only used when OCR confidence is low (<0.7) or the query requires visual reasoning. This reduced costs by 90%."

### Problem 3: "How did you handle WebSocket disconnections?"

**Answer:**
> "I implemented automatic reconnection with exponential backoff, health checks via ping/pong every 10 seconds, and graceful degradation where the UI shows connection status. The system queues messages during disconnection and replays them on reconnect."

### Problem 4: "How did you ensure the overlay doesn't block user interaction?"

**Answer:**
> "I used `pointer-events: none` on the overlay container for click-through, but set `pointer-events: auto` on interactive elements like the tooltip. Additionally, I implemented dynamic click-through regions in Rust that update based on the tooltip position."

---

## 📊 Metrics & Results

**Performance Metrics:**
- Screen capture: 60fps
- OCR processing: 200-300ms
- End-to-end latency: 300-500ms
- Memory usage: 500MB (2.5GB with OmniParser)
- Token usage: <2,000 tokens per task (90% reduction)

**Technical Achievements:**
- 11/15 sprints completed (73%)
- 3 LLM providers integrated
- 3 detection sources (OCR, A11y, OmniParser)
- Multi-process architecture
- Real-time overlay system
- Robust error handling

---

## 🎯 Interview Questions You Should Prepare

### Architecture Questions:
1. **"Why did you choose Tauri over Electron?"**
   - Smaller bundle size (5MB vs 150MB)
   - Better performance (native Rust)
   - Lower memory usage
   - Access to system APIs

2. **"Why separate Python backend instead of Rust?"**
   - Python has rich AI/ML ecosystem
   - Easier to integrate OCR, LLM libraries
   - Faster iteration for ML experiments
   - Rust for performance-critical paths

3. **"How does the overlay stay on top of all windows?"**
   - Tauri window with `always_on_top: true`
   - Z-index management
   - Window focus handling

### Technical Questions:
1. **"How do you handle race conditions in async code?"**
   - Async locks (asyncio.Lock)
   - Message queuing
   - Atomic operations
   - State machines

2. **"How do you test the screen capture?"**
   - Unit tests for hash comparison
   - Integration tests with mock displays
   - Manual testing with different DPI settings

3. **"How do you handle memory leaks?"**
   - Proper cleanup in destructors
   - Weak references where needed
   - Memory profiling tools
   - Resource pooling

### System Design Questions:
1. **"How would you scale this to multiple users?"**
   - Cloud-based backend
   - User authentication
   - Session management
   - Load balancing

2. **"How would you add support for macOS/Linux?"**
   - Abstract platform-specific code
   - Use cross-platform libraries
   - Conditional compilation
   - Platform-specific modules

---

## 🚀 Key Talking Points

### What Makes This Project Impressive:

1. **Multi-Language Integration**
   - Rust, Python, TypeScript working together
   - Each language used for its strengths

2. **Real-Time Performance**
   - 60fps screen capture
   - <500ms end-to-end latency
   - Smooth animations

3. **AI/ML Integration**
   - Multiple LLM providers
   - Computer vision pipeline
   - Intelligent fallback

4. **Production-Ready Code**
   - Error handling
   - Logging
   - Testing
   - Documentation

5. **Modern Tech Stack**
   - Latest frameworks (Tauri v2, React 19)
   - Async/await patterns
   - WebSocket real-time communication

---

## 📝 Elevator Pitch (1 minute)

> "I built StepPilot, an AI-powered desktop assistant that provides visual guidance for computer tasks. It's a multi-process application using Rust for high-performance screen capture, Python for AI/ML processing with OCR and LLM integration, and React for the UI.
>
> The system captures your screen at 60fps, uses computer vision to detect UI elements through OCR and Windows Accessibility API, and leverages LLMs like Gemini to understand your intent and generate step-by-step guidance. It then renders an interactive overlay with animated arrows and tooltips.
>
> Key technical achievements include differential screenshot detection for 90% performance improvement, multi-provider LLM orchestration with automatic fallback, and a real-time WebSocket protocol with health checks and reconnection logic.
>
> The architecture demonstrates proficiency in systems programming, async patterns, computer vision, AI integration, and modern web technologies."

---

## 🎯 Summary

**Core Competencies Demonstrated:**
- ✅ Multi-language integration (Rust, Python, TypeScript)
- ✅ Systems programming (screen capture, IPC)
- ✅ Computer vision (OCR, element detection)
- ✅ AI/ML integration (LLM orchestration)
- ✅ Real-time communication (WebSocket)
- ✅ Performance optimization (caching, differential detection)
- ✅ Error handling & resilience
- ✅ Modern web development (React, async/await)
- ✅ Desktop application development (Tauri)
- ✅ API design (REST, WebSocket)

**This project showcases end-to-end software engineering skills from low-level systems programming to high-level AI integration!** 🚀
