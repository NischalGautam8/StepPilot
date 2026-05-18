
# Cursor-King: 15-Sprint Implementation Plan

> **AI Desktop Guidance Assistant** — Watches your screen, understands UI, and visually guides you through tasks with arrows, highlights, and tooltips. Post-MVP: autonomous mouse/keyboard control via LLM tool calls.

## Key Decisions

| Decision | Choice |
|----------|--------|
| **LLM Provider** | GitHub Copilot SDK (primary) + OpenAI API (fallback) |
| **Target OS** | Windows only |
| **Voice Input** | None (text input only) |
| **Codebase** | Fresh start in `Cursor-king` |
| **Desktop Framework** | Tauri v2 (Rust + React/TypeScript) |
| **Backend** | Python FastAPI (sidecar process) |
| **OCR** | PaddleOCR v4 (free, local) |
| **UI Detection** | Windows Accessibility API + OmniParser (post-MVP) |
| **Communication** | WebSocket (`ws://127.0.0.1:8765`) |
| **Overlay** | Transparent always-on-top Tauri window, SVG rendering |

---

## Phase 1: MVP Foundation (Sprints 1–4)

### Sprint 1: Project Scaffolding & Core Shell [DONE]
**Goal**: Initialize the monorepo with Tauri + Python FastAPI, establish project structure.
**Duration**: 1 week

- [x] Initialize Tauri v2 project with React 19 + TypeScript frontend in `Cursor-king/`
- [x] Set up Python FastAPI backend in `backend/` with `pyproject.toml`
- [x] Create folder structure per architecture plan:
  - `src-tauri/src/` (Rust: main.rs, lib.rs, capture.rs, cursor.rs, overlay.rs, sidecar.rs)
  - `src/` (React: App.tsx, components/, hooks/, stores/, types/)
  - `backend/` (Python: main.py, core/, vision/, llm/, task/)
- [x] Implement system tray with menu items: Start, Stop, Settings, Quit
- [x] Register global hotkey `Ctrl+Alt+K` to toggle main window
- [x] Create dev launcher script (`scripts/dev.ps1`) that starts both Tauri and FastAPI
- [x] Set up `.gitignore`, `.env.example`, README.md
- [x] Verify both processes start and run independently

**Implementation Detail**: Tauri spawns FastAPI as a sidecar. During dev, run them separately with the launcher script.

---

### Sprint 2: Screen Capture & WebSocket Bridge [DONE]
**Goal**: Capture screenshots from Rust and deliver them to Python via WebSocket.
**Duration**: 1 week

- [x] Implement screen capture in Rust using `scrap` crate (DXGI backend)
- [x] JPEG compression using `image` crate (quality=75, ~100-200KB per frame)
- [x] Implement differential screenshot detection (skip unchanged frames)
- [x] Set up FastAPI WebSocket endpoint at `/ws`
- [x] Implement WebSocket client in Rust (`tungstenite` crate) to connect to Python
- [x] Define typed JSON message protocol:
  - `screenshot` — base64 JPEG from Rust → Python
  - `task_start` — user query from frontend → Python
  - `task_step` — guidance step from Python → frontend
  - `cursor_pos` — cursor position from Rust → Python
  - `error` — error messages
- [x] Implement WebSocket connection manager in Python (`ws_manager.py`)
- [x] Add reconnection logic with exponential backoff
- [x] Verify: capture screenshot → send via WS → receive in Python → log dimensions

**Implementation Detail**: Screenshots are captured on-demand (not continuous). Trigger on task start and after each user action.

---

### Sprint 3: OCR & Element Detection Pipeline [DONE]
**Goal**: Extract text and detect UI elements from screenshots.
**Duration**: 1 week

- [x] Install and configure PaddleOCR v4 in Python backend
  - `use_angle_cls=True`, `lang='en'`, `use_gpu=False`
  - Lower `det_db_thresh=0.3` for UI text sensitivity
- [x] Create `OCREngine` class returning `[{text, bbox, confidence}]`
- [x] Implement Windows Accessibility API reader using `pywinauto`
  - `Desktop(backend="uia")` for active window element tree
  - Extract: control_type, name, bbox, enabled, automation_id
- [x] Create `ElementMerger` that combines OCR + Accessibility results
  - Dedup overlapping bounding boxes (IoU > 0.7)
  - Prefer A11y type info, OCR text content
  - Assign unique element IDs
- [x] Create unified `UIElement` schema:
  ```
  {id, type, text, bbox, confidence, source, enabled, automation_id}
  ```
- [x] Build `ScreenParser` facade that orchestrates OCR + A11y in parallel
- [x] Add preprocessing: resize to 1280x720 before OCR, contrast enhancement
- [x] Verify: screenshot → parse → log detected elements with bounding boxes


**Implementation Detail**: OCR and A11y run concurrently via `asyncio.gather()`. A11y is primary when available; OCR fills gaps for custom-drawn UIs.

---

### Sprint 4: LLM Integration & Task Planning [DONE]
**Goal**: Connect to GitHub Copilot SDK / OpenAI API for task decomposition.
**Duration**: 1 week

- [x] Install GitHub Copilot SDK (`pip install github-copilot-sdk`)
- [x] Create abstract `LLMProvider` base class with `complete()` and `stream()` methods
- [x] Implement `CopilotProvider` using GitHub Copilot SDK
  - Support vision (screenshot blob attachments)
  - Support tool calling schema
- [x] Implement `OpenAIProvider` using `openai` Python SDK
  - `gpt-4o-mini` for text-only analysis (cheap)
  - `gpt-4o` for vision analysis (when screenshot needed)
- [x] Create `LLMOrchestrator` with provider switching via config
- [x] Implement token-minimization strategies:
  - Compact element format: `1:Button"Send"(1020,750,40,40)`
  - Text-first mode (send element registry, not screenshot)
  - Vision mode only when OCR confidence < 0.7
- [x] Write system prompt, task planner prompt, step execution prompt
- [x] Implement task decomposition: user query + elements → ordered steps
- [x] Verify: send elements + query → receive step plan as structured JSON


**Implementation Detail**: Default to Copilot SDK. Fall back to OpenAI API if Copilot unavailable. Text-only mode for 90%+ of calls to minimize costs.

---

## Phase 2: Visual Guidance (Sprints 5–7)

### Sprint 5: Overlay Window & Basic Rendering
**Goal**: Create the transparent click-through overlay and render basic shapes.
**Duration**: 1 week

- [x] Create second Tauri window "overlay" with:
  - `transparent(true)`, `decorations(false)`, `always_on_top(true)`
  - Full-screen dimensions matching primary monitor
  - `set_ignore_cursor_events(true)` for click-through
- [x] Set up Tauri permissions in `capabilities/default.json`
- [x] Create overlay entry point (`overlay.html` / `Overlay.tsx`)
- [x] Implement full-screen SVG canvas component
- [x] Build `BoundingBox` component: colored rectangle with glow animation
- [x] Build `Tooltip` component: positioned label with instruction text
- [x] Build `CircleIndicator` component: pulsing circle at target coordinates
- [x] Implement overlay state management (Zustand store for active hints)
- [x] Wire WebSocket messages from Python → Rust → Overlay window
- [x] Verify: manually send a hint → see bounding box + tooltip on overlay

**Implementation Detail**: Overlay window is created on app start but hidden. Shown when task is active. Uses CSS `pointer-events: none` for click-through on web side.

---

### Sprint 6: Animated Arrow & Guidance Flow
**Goal**: Implement the signature Bézier arrow animation and wire up the full guidance loop.
**Duration**: 1 week

- [ ] Build `GuidanceArrow` SVG component with cubic Bézier path
  - `M cursor_x cursor_y Q midpoint target_x target_y`
  - CSS `stroke-dasharray` + `stroke-dashoffset` animation for "drawing" effect
  - Arrowhead marker via SVG `<marker>` + `<polygon>`
  - Green glow effect via `filter: drop-shadow`
- [ ] Add arrow from current cursor position to target element
- [ ] Track real-time cursor position from Rust → frontend (throttled to 30fps)
- [x] Create `GuidanceRenderer` component that combines:
  - BoundingBox (around target element)
  - Tooltip (instruction text near target)
  - Pulse animation on target
- [x] Implement step transition animations (fade out old, fade in new)
- [x] Wire full loop: user types task → LLM plans → overlay shows Step 1 guidance
- [x] Add step counter badge: "Step 1 of 5"
- [ ] Verify: complete task "open Notepad" with guided arrows

**Implementation Detail**: Cursor position from `GetCursorPos` Win32 API via Rust, sent as `cursor_pos` WS message. Arrow updates smoothly using `requestAnimationFrame`.

---

### Sprint 7: Step Verification & Multi-Step Execution
**Goal**: Detect when user completes a step and automatically advance to the next.
**Duration**: 1 week

- [ ] Implement step verification in Python:
  - After user clicks/types, capture new screenshot
  - Re-run OCR + A11y on new state
  - Compare element states: did target change? Did new elements appear?
- [ ] Create `TaskEngine` state machine: IDLE → PLANNING → GUIDING → VERIFYING → COMPLETE
- [x] Implement automatic re-capture trigger:
  - Listen for mouse click events (from Rust cursor tracker)
- [ ] Debounce: wait 500ms after last event before re-capture
- [ ] Implement retry logic: max 3 retries per step, then re-plan
- [x] Add "Did this work?" confirmation button (temporarily disable click-through)
- [ ] Implement re-planning: if verification fails 3x, ask LLM to re-analyze
- [ ] Add task completion celebration: ✓ animation + "Task complete!" overlay
- [ ] Verify: complete a 3+ step task end-to-end (e.g., "rename a file on desktop")

**Implementation Detail**: Verification uses element diffing — compare element registry before and after action. If target element disappeared or state changed, step is considered complete.

---

## Phase 3: Polish & Intelligence (Sprints 8–10)

### Sprint 8: Main Window UI & Settings
**Goal**: Build a polished chat-like interface and settings panel.
**Duration**: 1 week

- [ ] Design and implement main window UI:
  - Dark theme with glassmorphism effects
  - Chat-style message list (user queries + assistant responses)
  - Text input with "Send" button and Ctrl+Enter shortcut
  - Task progress indicator (step N of M)
  - Cancel task button
- [ ] Build Settings panel:
  - LLM Provider selector (Copilot SDK / OpenAI)
  - API key input (stored securely via `keyring` Python lib)
  - Model selector (gpt-4o, gpt-4o-mini)
  - Toggle: show debug overlay (all detected elements)
  - Toggle: auto-advance steps vs manual confirmation
  - Hotkey customization
- [ ] Implement CSS design system:
  - Color palette (dark mode: slate/zinc base, green accent)
  - Typography (Inter font from Google Fonts)
  - Spacing scale, border-radius tokens
  - Transition/animation tokens
- [ ] Add connection status indicator (green/red dot)
- [ ] Add task history list (in-memory, current session only)
- [ ] Verify: full UI flow from opening app to completing a task

**Implementation Detail**: Settings stored as JSON at `~/.cursor-king/config.json`. Secrets (API keys) stored via Python `keyring` library using Windows Credential Manager.

---

### Sprint 9: Context Management & Smart Prompting
**Goal**: Minimize token usage and improve LLM accuracy with smart context.
**Duration**: 1 week

- [ ] Implement `ContextManager` class:
  - Sliding window: keep last 3 step results in full
  - Compress older steps into summary: "Steps 1-4: opened WhatsApp, found group"
  - Track active window title for context switching detection
- [ ] Implement smart vision toggle:
  - Text-only mode when OCR confidence > 0.85 and elements > 5
  - Vision mode (send screenshot) when confidence low or elements sparse
  - Always vision mode on first analysis of a new window
- [ ] Add screenshot preprocessing:
  - Crop to active window bounds (skip taskbar, other windows)
  - Resize cropped region to max 1280x720
  - Auto-contrast enhancement for dark themes
- [ ] Implement element registry caching:
  - Cache parsed elements with TTL (invalidate after 10s or window change)
  - Send only delta (changed elements) to LLM when possible
- [ ] Add prompt templates with variable substitution
- [ ] Implement privacy filter: redact elements containing "password", "secret", etc.
- [ ] Verify: run 5 different tasks, measure average token usage per task

**Implementation Detail**: Target <2,000 tokens per LLM call average. Vision calls should be <20% of total calls.

---

### Sprint 10: Error Handling & Robustness
**Goal**: Handle edge cases gracefully and add comprehensive error recovery.
**Duration**: 1 week

- [ ] Implement WebSocket reconnection with health checks (ping every 10s)
- [ ] Handle Python sidecar crash: detect exit, restart, re-establish WS
- [ ] Handle window focus changes during guidance:
  - Detect active window title change
  - Pause guidance, show "Window changed" overlay
  - Option to re-analyze new window or return to original
- [ ] Handle LLM API failures:
  - Timeout after 15s
  - Retry with exponential backoff (3 attempts)
  - Show user-friendly error message
  - Fallback: Copilot → OpenAI if primary fails
- [ ] Handle OCR/A11y failures:
  - Graceful degradation (OCR-only if A11y unavailable)
  - Show "Unable to detect elements" with retry button
- [ ] Add structured logging with `structlog`:
  - Log every step transition, LLM call (tokens, latency), errors
  - Log file at `~/.cursor-king/logs/cursor-king.log`
  - Log rotation (max 10MB, keep 3 files)
- [ ] Implement input validation for all WS messages
- [ ] Verify: simulate each failure mode, confirm graceful recovery

**Implementation Detail**: All errors surface as toast notifications in the main window. Debug details go to log file only.

---

## Phase 4: Enhanced Vision (Sprints 11–12)

### Sprint 11: OmniParser Integration
**Goal**: Add icon/button detection beyond text OCR using Microsoft's OmniParser.
**Duration**: 1 week

- [ ] Download OmniParser V2 models (YOLOv8 icon_detect + Florence-2 icon_caption)
- [ ] Create `UIDetector` class wrapping OmniParser inference
- [ ] Integrate into `ScreenParser` pipeline alongside OCR + A11y
- [ ] Update `ElementMerger` to handle three sources:
  - OCR text regions
  - A11y control tree
  - OmniParser icon/button bounding boxes with captions
- [ ] Implement lazy loading: only load OmniParser models when first needed (~2GB RAM)
- [ ] Add GPU toggle: `use_gpu=True` in config enables CUDA for OmniParser
- [ ] Test detection quality on common apps: Chrome, File Explorer, WhatsApp Desktop
- [ ] Benchmark: measure latency increase from adding OmniParser
- [ ] Verify: detect non-text icons (hamburger menu, close button, settings gear)

**Implementation Detail**: OmniParser is optional — disabled by default. Users opt-in via settings. Adds ~300ms on CPU, ~100ms on GPU.

---

### Sprint 12: Visual Debug Mode & Detection Tuning
**Goal**: Build developer tools for visualizing and tuning element detection.
**Duration**: 1 week

- [ ] Implement "Debug Overlay" mode:
  - Toggle via settings or Ctrl+Alt+D
  - Show ALL detected elements as colored bounding boxes on overlay:
    - Blue = OCR text regions
    - Green = A11y controls
    - Orange = OmniParser icons
  - Show element ID labels on each box
  - Show confidence scores
- [ ] Add detection statistics panel:
  - Elements detected per source
  - OCR processing time
  - A11y tree depth and element count
  - Merger dedup count
- [ ] Implement screenshot comparison tool:
  - Side-by-side: raw screenshot vs annotated screenshot
  - Save annotated screenshots to `~/.cursor-king/debug/`
- [ ] Tune PaddleOCR parameters for common failure cases:
  - Dark theme apps (reduce `det_db_thresh`)
  - Small font text (increase resolution before OCR)
  - Multi-language text
- [ ] Tune element merger IoU threshold
- [ ] Verify: debug overlay correctly shows all detection sources with no overlap

**Implementation Detail**: Debug mode is a development accelerator — critical for tuning detection quality on different apps.

---

## Phase 5: Autonomous Agent (Sprints 13–15)

### Sprint 13: Mouse & Keyboard Automation
**Goal**: Enable LLM-driven autonomous control of mouse and keyboard.
**Duration**: 1 week

- [ ] Integrate PyAutoGUI for mouse control:
  - `click(x, y)`, `doubleClick(x, y)`, `rightClick(x, y)`
  - `moveTo(x, y, duration=0.3)` — smooth animated movement
  - `scroll(clicks, x, y)`
- [ ] Integrate PyAutoGUI for keyboard control:
  - `typewrite(text, interval=0.05)` — human-like typing speed
  - `hotkey('ctrl', 'c')` — key combinations
  - `press('enter')` — single key press
- [ ] Implement LLM tool calling schema (OpenAI function calling format):
  - `click(x, y, button)` — click at coordinates
  - `type_text(text)` — type text at cursor
  - `key_press(keys)` — press key combination
  - `scroll(x, y, direction, amount)` — scroll at position
  - `screenshot()` — take new screenshot to observe result
  - `wait(seconds)` — wait for UI to update
- [ ] Create `Actuator` class with two modes:
  - `mode="guide"` → show overlay hints (existing behavior)
  - `mode="auto"` → execute PyAutoGUI actions
- [ ] Implement mode selector in settings: Guided / Supervised / Autonomous
- [ ] Add smooth cursor movement animation before clicks (feels natural)
- [ ] Verify: LLM successfully opens Notepad and types "Hello World"

**Implementation Detail**: PyAutoGUI runs in the Python backend. Coordinate mapping must account for DPI scaling (use `ctypes` to get actual screen scale factor).

---

### Sprint 14: Safety Systems & Supervised Mode
**Goal**: Implement safety mechanisms to prevent unintended actions.
**Duration**: 1 week

- [ ] Implement "Supervised" mode:
  - LLM proposes action → show overlay preview (arrow + label)
  - User confirms via floating [✓ Allow] / [✗ Deny] buttons
  - Temporarily disable click-through for confirmation buttons
  - If denied, ask LLM for alternative approach
- [ ] Implement physical mouse override (emergency stop):
  - Track mouse position continuously
  - If user moves mouse during autonomous action → immediately halt
  - Show "Agent paused — you moved the mouse" notification
  - Option to resume or cancel
- [ ] Implement action risk classification:
  - Low risk: mouse move, scroll, type in text field → auto-allow in autonomous mode
  - Medium risk: click button, press Enter → require confirmation in supervised mode
  - High risk: delete, send, submit, close window → always require confirmation
- [ ] Add action log panel in main window:
  - Every action taken: timestamp, type, coordinates, result
  - Expandable details with before/after screenshots
- [ ] Implement undo system (basic):
  - Record Ctrl+Z after each action as potential undo
  - Offer "Undo last action" button
- [ ] Add PyAutoGUI failsafe: mouse to corner = abort all
- [ ] Verify: supervised mode correctly blocks and confirms before high-risk actions

**Implementation Detail**: Risk classification uses both element type (from A11y) and element text (contains "delete", "send", etc.) to determine risk level.

---

### Sprint 15: End-to-End Polish & Packaging
**Goal**: Final refinement, packaging, and documentation.
**Duration**: 1 week

- [ ] Performance optimization pass:
  - Target <2s end-to-end latency for guidance
  - Profile and optimize bottlenecks (OCR, LLM, rendering)
  - Implement element caching between unchanged frames
  - Parallel pipeline: OCR + A11y + capture run concurrently
- [ ] Build PyInstaller sidecar:
  - Bundle Python backend as `backend.exe`
  - Include PaddleOCR models and dependencies
  - Test standalone execution
- [ ] Configure Tauri production build:
  - Bundle `backend.exe` as external binary (sidecar)
  - Set app icon, metadata, version
  - Build Windows installer (.msi)
- [ ] Create onboarding flow:
  - First-launch setup wizard: enter API key, choose provider
  - Interactive tutorial: "Try saying 'Open Calculator'"
- [ ] Write user documentation:
  - README with setup instructions
  - Supported apps and known limitations
  - Keyboard shortcuts reference
- [ ] Final testing across common apps:
  - File Explorer, Chrome, Notepad, WhatsApp Desktop
  - Test with different Windows themes (light/dark)
  - Test with different DPI scaling (100%, 125%, 150%)
- [ ] Create GitHub release with changelog
- [ ] Verify: clean install from .msi → complete a multi-step task successfully

**Implementation Detail**: Final binary should be <150MB (Tauri ~5MB + Python sidecar ~100-140MB). Installer handles all dependencies.

---

## Difficulty & Timeline Summary

| Sprint | Focus | Difficulty | Est. Duration |
|--------|-------|-----------|---------------|
| 1 | Project Scaffolding | ⭐⭐ Low | 1 week |
| 2 | Screen Capture & WebSocket | ⭐⭐⭐ Medium | 1 week |
| 3 | OCR & Element Detection | ⭐⭐⭐ Medium | 1 week |
| 4 | LLM Integration | ⭐⭐⭐ Medium | 1 week |
| 5 | Overlay Window | ⭐⭐⭐ Medium | 1 week |
| 6 | Animated Arrows & Guidance | ⭐⭐⭐⭐ Medium-High | 1 week |
| 7 | Step Verification | ⭐⭐⭐⭐ High | 1 week |
| 8 | Main UI & Settings | ⭐⭐⭐ Medium | 1 week |
| 9 | Context & Smart Prompting | ⭐⭐⭐ Medium | 1 week |
| 10 | Error Handling | ⭐⭐⭐ Medium | 1 week |
| 11 | OmniParser Integration | ⭐⭐⭐⭐ High | 1 week |
| 12 | Visual Debug Mode | ⭐⭐⭐ Medium | 1 week |
| 13 | Mouse/Keyboard Automation | ⭐⭐⭐ Medium | 1 week |
| 14 | Safety Systems | ⭐⭐⭐⭐ High | 1 week |
| 15 | Polish & Packaging | ⭐⭐⭐⭐ High | 1 week |

**Total: ~15 weeks** (one sprint per week)
**MVP (Sprints 1–7): ~7 weeks**

---

## Tech Stack Summary

| Component | Technology | License | Cost |
|-----------|-----------|---------|------|
| Desktop Shell | Tauri v2 (Rust) | MIT | Free |
| Frontend | React 19 + TypeScript | MIT | Free |
| Build Tool | Vite | MIT | Free |
| State Management | Zustand | MIT | Free |
| Backend | Python FastAPI | MIT | Free |
| IPC | WebSocket (tungstenite + fastapi) | - | Free |
| OCR | PaddleOCR v4 | Apache 2.0 | Free |
| UI Detection | pywinauto (Win UIA) | BSD | Free |
| Icon Detection | OmniParser V2 (YOLOv8) | AGPL/MIT | Free |
| LLM (Primary) | GitHub Copilot SDK | Subscription | ~$10/mo |
| LLM (Fallback) | OpenAI API (gpt-4o-mini) | Pay-per-use | ~$0.003/task |
| Automation | PyAutoGUI | BSD | Free |
| Packaging | PyInstaller + Tauri bundler | - | Free |
| Logging | structlog | MIT | Free |
| Security | keyring (Win Credential Mgr) | MIT | Free |
