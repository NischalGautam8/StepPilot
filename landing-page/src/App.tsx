import { useState } from 'react'
import { 
  Download, 
  BookOpen, 
  ArrowRight, 
  Shield, 
  Cpu, 
  Lock, 
  ChevronDown, 
  ChevronUp, 
  Play, 
  RotateCcw
} from 'lucide-react'

// Custom Github SVG Icon to avoid library version mismatches
function GithubIcon({ className }: { className?: string }) {
  return (
    <svg 
      className={className} 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      strokeWidth="2.5" 
      strokeLinecap="round" 
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
      <path d="M9 18c-4.51 2-5-2-7-2" />
    </svg>
  )
}

// FAQ Item Component for Brutalist Accordion
function FaqItem({ question, answer }: { question: string, answer: string }) {
  const [isOpen, setIsOpen] = useState(false)
  return (
    <div className="border-3 border-ink bg-paper mb-4 transition-all duration-150">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full text-left p-6 flex justify-between items-center font-display font-bold text-lg md:text-xl uppercase tracking-tight hover:bg-paper-2 transition-colors cursor-pointer"
        aria-expanded={isOpen}
      >
        <span>{question}</span>
        {isOpen ? <ChevronUp className="w-6 h-6 stroke-[3px]" /> : <ChevronDown className="w-6 h-6 stroke-[3px]" />}
      </button>
      {isOpen && (
        <div className="p-6 border-t-3 border-ink bg-paper-2 font-mono text-sm leading-relaxed text-ink">
          {answer}
        </div>
      )}
    </div>
  )
}

function App() {
  const [activeStep, setActiveStep] = useState(0)
  const [isSimulating, setIsSimulating] = useState(false)

  // Simulation steps for the interactive mockup
  const simulationSteps = [
    {
      title: "1.0 REQUEST",
      prompt: "Create a new GitHub repository called 'steppilot-docs'",
      instruction: "Locating the repository creation page in the browser window...",
      targetX: "24%",
      targetY: "28%",
      targetWidth: "80px",
      targetHeight: "36px",
      guideText: "Step 1: Click the 'New' repository button to begin."
    },
    {
      title: "2.0 PLAN",
      prompt: "Create a new GitHub repository called 'steppilot-docs'",
      instruction: "Focusing the repository name input field...",
      targetX: "24%",
      targetY: "52%",
      targetWidth: "220px",
      targetHeight: "38px",
      guideText: "Step 2: Click the 'Repository name' input and enter 'steppilot-docs'."
    },
    {
      title: "3.0 EXECUTE",
      prompt: "Create a new GitHub repository called 'steppilot-docs'",
      instruction: "Locating the submit button at the bottom of the page...",
      targetX: "24%",
      targetY: "78%",
      targetWidth: "160px",
      targetHeight: "36px",
      guideText: "Step 3: Click 'Create repository' to finalize deployment."
    }
  ]

  const handleNextStep = () => {
    if (activeStep < simulationSteps.length - 1) {
      setActiveStep(activeStep + 1)
    } else {
      setActiveStep(0)
      setIsSimulating(false)
    }
  }

  const startSimulation = () => {
    setActiveStep(0)
    setIsSimulating(true)
  }

  return (
    <div className="min-h-screen bg-paper text-ink font-body selection:bg-accent selection:text-white">
      
      {/* N7 · BRUTAL SLAB NAVIGATION */}
      <header className="sticky top-0 z-50 w-full bg-paper border-b-3 border-ink flex items-center justify-between px-6 py-4">
        <a href="#" className="font-display font-black text-2xl tracking-tighter uppercase flex items-center gap-2">
          <span>STEPPILOT</span>
          <span className="bg-accent text-white px-2 py-0.5 text-xs border-2 border-ink shadow-[2px_2px_0px_var(--color-ink)]">v0.1.0</span>
        </a>
        <nav className="hidden md:flex items-center gap-8" aria-label="Primary">
          <ul className="flex items-center gap-8 list-none m-0 p-0">
            <li>
              <a href="#workflow" className="font-display font-bold text-sm tracking-widest uppercase hover:underline decoration-3 decoration-accent">
                WORKFLOW
              </a>
            </li>
            <li>
              <a href="#features" className="font-display font-bold text-sm tracking-widest uppercase hover:underline decoration-3 decoration-accent">
                FEATURES
              </a>
            </li>
            <li>
              <a href="#faq" className="font-display font-bold text-sm tracking-widest uppercase hover:underline decoration-3 decoration-accent">
                FAQ
              </a>
            </li>
            <li>
              <a href="https://github.com/NischalGautam8/StepPilot" target="_blank" rel="noopener noreferrer" className="font-display font-bold text-sm tracking-widest uppercase hover:underline decoration-3 decoration-accent flex items-center gap-1">
                <GithubIcon className="w-4 h-4" /> GITHUB
              </a>
            </li>
          </ul>
        </nav>
        <a href="#download" className="btn-brutal text-sm py-2 px-4 shadow-[2px_2px_0px_var(--color-ink)] hover:translate-x-0 hover:translate-y-0">
          DOWNLOAD
        </a>
      </header>

      {/* HERO SECTION - H8 MOCKUP SPLIT */}
      <section className="relative w-full max-w-7xl mx-auto px-6 py-12 md:py-20 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center border-b-3 border-ink">
        <div className="lg:col-span-6 flex flex-col items-start text-left">
          <h1 className="font-display font-black text-5xl md:text-6xl xl:text-7xl uppercase leading-none tracking-tight mb-6">
            CO-PILOT FOR <br />
            YOUR ENTIRE <br />
            <span className="bg-accent text-white px-3 py-1 inline-block border-3 border-ink shadow-[6px_6px_0px_var(--color-ink)]">DESKTOP.</span>
          </h1>
          <p className="text-lg md:text-xl font-normal leading-relaxed text-ink-2 max-w-xl mb-8">
            An intelligent desktop companion that watches your screen, understands the visible UI, and overlays real-time visual guidance to lead you through complex local tasks.
          </p>
          <div className="flex flex-wrap gap-4 w-full sm:w-auto">
            <a href="#download" className="btn-brutal flex-1 sm:flex-none text-center justify-center">
              <Download className="w-5 h-5 stroke-[2.5px]" />
              DOWNLOAD APP
            </a>
            <a href="https://github.com/NischalGautam8/StepPilot" target="_blank" rel="noopener noreferrer" className="btn-brutal-secondary flex-1 sm:flex-none text-center justify-center">
              <BookOpen className="w-5 h-5 stroke-[2.5px]" />
              READ THE DOCS
            </a>
          </div>
          
          <div className="mt-8 flex items-center gap-4 text-xs font-mono text-muted">
            <span className="flex items-center gap-1"><Shield className="w-4 h-4 text-accent" /> LOCAL PROCESSORS</span>
            <span>•</span>
            <span className="flex items-center gap-1"><Cpu className="w-4 h-4 text-accent" /> TAURI + RUST CORE</span>
          </div>
        </div>

        {/* INTERACTIVE SIMULATOR (TIGHTLY FIT PRODUCT SHOWCASE) */}
        <div className="lg:col-span-6 w-full">
          <div className="card-brutal p-2 bg-paper-2 overflow-hidden flex flex-col relative w-full aspect-[4/3] min-h-[360px]">
            {/* Window title bar */}
            <div className="flex items-center justify-between px-3 py-2 border-b-3 border-ink bg-paper">
              <span className="font-mono text-xs font-bold uppercase tracking-tight flex items-center gap-2">
                <span className="w-3.5 h-3.5 bg-accent border-2 border-ink rounded-full"></span>
                STEPPILOT HUD OVERLAY SIMULATOR
              </span>
              <div className="flex gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-ink"></span>
                <span className="w-2.5 h-2.5 rounded-full bg-ink"></span>
                <span className="w-2.5 h-2.5 rounded-full bg-ink"></span>
              </div>
            </div>

            {/* Simulated Desktop / Browser viewport */}
            <div className="relative flex-1 bg-white overflow-hidden p-4 flex flex-col font-sans select-none">
              {/* Mock Browser Header */}
              <div className="flex items-center gap-2 p-2 border-2 border-ink bg-paper-2 mb-3 rounded-none text-xs">
                <div className="flex gap-1">
                  <span className="w-2 h-2 rounded-full bg-muted"></span>
                  <span className="w-2 h-2 rounded-full bg-muted"></span>
                </div>
                <div className="flex-1 bg-white border-2 border-ink px-2 py-0.5 text-left font-mono truncate text-[10px]">
                  https://github.com/new
                </div>
              </div>

              {/* Mock GitHub Repo Page */}
              <div className="flex-1 border-2 border-ink p-4 bg-paper text-left flex flex-col justify-between text-xs relative">
                <div>
                  <div className="flex items-center justify-between border-b-2 border-ink pb-2 mb-3">
                    <span className="font-bold text-sm tracking-tight">Create a new repository</span>
                    <span className="bg-ink text-white px-2 py-0.5 font-bold text-[9px] rounded-none">Public</span>
                  </div>

                  {/* Form Element 1: Owner & Name */}
                  <div className="grid grid-cols-12 gap-2 mb-3">
                    <div className="col-span-4">
                      <label className="block text-[10px] font-bold uppercase mb-1">Owner</label>
                      <div className="border-2 border-ink bg-paper-2 p-1.5 font-mono text-[10px]">NischalGautam8</div>
                    </div>
                    <div className="col-span-8">
                      <label className="block text-[10px] font-bold uppercase mb-1">Repository name</label>
                      <div className="border-2 border-ink bg-white p-1.5 font-mono text-[10px] text-ink-2 h-8 flex items-center">
                        {isSimulating && activeStep >= 1 ? "steppilot-docs" : ""}
                      </div>
                    </div>
                  </div>

                  {/* Description */}
                  <div className="mb-3">
                    <label className="block text-[10px] font-bold uppercase mb-1">Description (optional)</label>
                    <div className="border-2 border-ink bg-white p-1.5 text-[10px] text-muted h-6"></div>
                  </div>
                </div>

                {/* Submit Action */}
                <div className="flex justify-between items-center border-t-2 border-ink pt-3">
                  <button className="px-3 py-1 border-2 border-ink bg-paper-2 font-bold font-mono text-[10px]">
                    Cancel
                  </button>
                  <button className="px-3 py-1.5 border-2 border-ink bg-accent text-white font-bold font-display uppercase text-[10px] shadow-[2px_2px_0px_var(--color-ink)]">
                    Create repository
                  </button>
                </div>

                {/* Floating "New" repository button trigger block */}
                <div className="absolute top-2.5 right-24">
                  <button className="px-2.5 py-1 border-2 border-ink bg-accent text-white font-bold text-[9px] flex items-center gap-1 shadow-[2px_2px_0px_var(--color-ink)]">
                    + New
                  </button>
                </div>
              </div>

              {/* OVERLAY HUD (SIMULATING STEPPILOT TRANSPARENT WINDOW) */}
              {isSimulating && (
                <div className="absolute inset-0 bg-transparent pointer-events-none z-10">
                  {/* Glowing Bounding Box */}
                  <div 
                    className="absolute border-4 border-accent animate-pulse shadow-[0_0_12px_#E63946] transition-all duration-300 ease-out"
                    style={{
                      left: simulationSteps[activeStep].targetX,
                      top: simulationSteps[activeStep].targetY,
                      width: simulationSteps[activeStep].targetWidth,
                      height: simulationSteps[activeStep].targetHeight,
                      transform: 'translate(-50%, -50%)'
                    }}
                  />

                  {/* Guidance Arrow */}
                  <svg 
                    className="absolute w-24 h-24 text-accent transition-all duration-300 ease-out"
                    style={{
                      left: `calc(${simulationSteps[activeStep].targetX} + 36px)`,
                      top: `calc(${simulationSteps[activeStep].targetY} + 36px)`,
                      transform: 'translate(-50%, -50%)'
                    }}
                    viewBox="0 0 100 100"
                  >
                    <path 
                      d="M80 80 Q 50 80 15 20" 
                      fill="none" 
                      stroke="#E63946" 
                      strokeWidth="5" 
                      strokeDasharray="4 4"
                    />
                    <polygon 
                      points="10,25 15,10 30,15" 
                      fill="#E63946" 
                    />
                  </svg>

                  {/* Guidance Tooltip Card */}
                  <div 
                    className="absolute bg-ink text-white p-3 border-2 border-accent shadow-lg w-56 font-mono text-[10px] text-left transition-all duration-300 ease-out"
                    style={{
                      left: `calc(${simulationSteps[activeStep].targetX} - 10px)`,
                      top: `calc(${simulationSteps[activeStep].targetY} - 74px)`,
                      transform: 'translateX(-50%)'
                    }}
                  >
                    <div className="font-bold text-accent uppercase mb-0.5">{simulationSteps[activeStep].title}</div>
                    <div className="leading-snug">{simulationSteps[activeStep].guideText}</div>
                  </div>
                </div>
              )}
            </div>

            {/* Simulation controls bar */}
            <div className="p-4 border-t-3 border-ink bg-paper flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-4">
              <div className="flex flex-col text-left">
                <span className="font-mono text-xs text-muted uppercase">Prompt Input:</span>
                <span className="font-display font-black text-sm uppercase tracking-tight truncate">
                  "Create new GitHub repo"
                </span>
              </div>
              
              <div className="flex gap-2">
                {!isSimulating ? (
                  <button 
                    onClick={startSimulation}
                    className="btn-brutal py-1.5 px-3 text-xs flex items-center justify-center gap-1.5 shadow-[2px_2px_0px_var(--color-ink)] hover:translate-x-0 hover:translate-y-0"
                  >
                    <Play className="w-3.5 h-3.5 fill-current" /> SIMULATE GUIDANCE
                  </button>
                ) : (
                  <>
                    <button 
                      onClick={() => setIsSimulating(false)}
                      className="btn-brutal-secondary py-1.5 px-3 text-xs flex items-center justify-center gap-1.5 shadow-[2px_2px_0px_var(--color-ink)] hover:translate-x-0 hover:translate-y-0"
                    >
                      <RotateCcw className="w-3.5 h-3.5" /> RESET
                    </button>
                    <button 
                      onClick={handleNextStep}
                      className="btn-brutal py-1.5 px-3 text-xs flex items-center justify-center gap-1.5 shadow-[2px_2px_0px_var(--color-ink)] hover:translate-x-0 hover:translate-y-0"
                    >
                      <span>NEXT STEP</span>
                      <ArrowRight className="w-3.5 h-3.5 stroke-[2.5px]" />
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION HEAD: S1 LEFT MARGIN NUMBERED */}
      <section id="workflow" className="w-full border-b-3 border-ink">
        <div className="max-w-7xl mx-auto px-6 py-16 grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12">
          {/* Left margin label */}
          <div className="lg:col-span-3 text-left">
            <span className="font-display font-black text-xl tracking-wider text-accent border-b-3 border-accent pb-1 inline-block">
              01 — THE ENGINE
            </span>
          </div>
          
          {/* Main content grid */}
          <div className="lg:col-span-9 text-left">
            <h2 className="font-display font-black text-4xl uppercase tracking-tight mb-8">
              HOW STEPPILOT GUIDES YOUR DESKTOP
            </h2>
            
            {/* F4 · STEP SEQUENCE */}
            <ol className="grid grid-cols-1 md:grid-cols-2 gap-6 list-none p-0 m-0">
              
              <li className="card-brutal p-6 flex flex-col justify-between items-start h-full">
                <div>
                  <span className="font-mono text-sm font-bold text-accent bg-paper-2 border-2 border-ink px-2 py-0.5 inline-block mb-4 shadow-[2px_2px_0px_var(--color-ink)]">
                    1.0 REQUEST
                  </span>
                  <h3 className="font-display font-black text-2xl uppercase mb-3">STATE YOUR INTENT</h3>
                  <p className="font-body text-ink-2 text-sm leading-relaxed">
                    Speak or type your goal directly into the transparent prompt bar (e.g. "Draft an invitation email in Thunderbird" or "Deploy server stack").
                  </p>
                </div>
              </li>

              <li className="card-brutal p-6 flex flex-col justify-between items-start h-full">
                <div>
                  <span className="font-mono text-sm font-bold text-accent bg-paper-2 border-2 border-ink px-2 py-0.5 inline-block mb-4 shadow-[2px_2px_0px_var(--color-ink)]">
                    2.0 OBSERVE
                  </span>
                  <h3 className="font-display font-black text-2xl uppercase mb-3">PROCESS THE SCREEN</h3>
                  <p className="font-body text-ink-2 text-sm leading-relaxed">
                    StepPilot triggers high-performance DXGI screen capture. PaddleOCR and Windows UI Automation parsing run locally to identify every text snippet, button, and input form on your screen.
                  </p>
                </div>
              </li>

              <li className="card-brutal p-6 flex flex-col justify-between items-start h-full">
                <div>
                  <span className="font-mono text-sm font-bold text-accent bg-paper-2 border-2 border-ink px-2 py-0.5 inline-block mb-4 shadow-[2px_2px_0px_var(--color-ink)]">
                    3.0 PLAN
                  </span>
                  <h3 className="font-display font-black text-2xl uppercase mb-3">CONSTRUCT THE PATH</h3>
                  <p className="font-body text-ink-2 text-sm leading-relaxed">
                    VLM orchestrators parse the observed screen structure. The planning engine maps the exact sequences of coordinates, keys, and UI interaction nodes needed to fulfill your request.
                  </p>
                </div>
              </li>

              <li className="card-brutal p-6 flex flex-col justify-between items-start h-full">
                <div>
                  <span className="font-mono text-sm font-bold text-accent bg-paper-2 border-2 border-ink px-2 py-0.5 inline-block mb-4 shadow-[2px_2px_0px_var(--color-ink)]">
                    4.0 GUIDE
                  </span>
                  <h3 className="font-display font-black text-2xl uppercase mb-3">OVERLAY THE PATHWAY</h3>
                  <p className="font-body text-ink-2 text-sm leading-relaxed">
                    A hardware-accelerated click-through transparent canvas paints neon Bézier arrows, glowing border bounding boxes, and step annotations on top of your live desktop apps.
                  </p>
                </div>
              </li>

            </ol>
          </div>
        </div>
      </section>

      {/* SECTION HEAD & F1 BENTO FEATURES */}
      <section id="features" className="w-full border-b-3 border-ink bg-paper-2">
        <div className="max-w-7xl mx-auto px-6 py-16 grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12">
          {/* Left margin label */}
          <div className="lg:col-span-3 text-left">
            <span className="font-display font-black text-xl tracking-wider text-accent border-b-3 border-accent pb-1 inline-block">
              02 — STACK OVERVIEW
            </span>
          </div>

          {/* Bento Grid */}
          <div className="lg:col-span-9 text-left">
            <h2 className="font-display font-black text-4xl uppercase tracking-tight mb-8">
              ARCHITECTURE & CORE SYSTEM CAPABILITIES
            </h2>

            {/* F1 · Bento grid */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
              
              {/* Box 1: Local processing */}
              <div className="md:col-span-8 card-brutal p-6 flex flex-col justify-between min-h-[180px] bg-paper">
                <div>
                  <span className="font-mono text-xs uppercase tracking-widest text-muted block mb-2">// SECURITY FIRST</span>
                  <h3 className="font-display font-black text-2xl uppercase mb-2">100% LOCAL PROCESSING PIPELINE</h3>
                  <p className="text-sm text-ink-2 leading-relaxed max-w-lg">
                    StepPilot processes all image captures, OCR scans, and accessibility tree parsing locally on your hardware. Screenshots are kept in memory and never written to disk or sent to external servers raw.
                  </p>
                </div>
                <div className="flex gap-2 mt-4">
                  <span className="bg-paper-3 px-2 py-0.5 border-2 border-ink font-mono text-[10px] font-bold">PADDLEOCR V4</span>
                  <span className="bg-paper-3 px-2 py-0.5 border-2 border-ink font-mono text-[10px] font-bold">WINDOWS UIA</span>
                </div>
              </div>

              {/* Box 2: Tauri Architecture */}
              <div className="md:col-span-4 card-brutal p-6 flex flex-col justify-between min-h-[180px] bg-paper">
                <div>
                  <span className="font-mono text-xs uppercase tracking-widest text-muted block mb-2">// HARDWARE</span>
                  <h3 className="font-display font-black text-xl uppercase mb-2">TAURI v2 ENGINE</h3>
                  <p className="text-xs text-ink-2 leading-relaxed">
                    A lightweight Rust desktop wrapper provides high-performance DXGI screen grabs, shell bindings, and manages the transparent web-renderer HUD at less than 80MB of memory.
                  </p>
                </div>
                <span className="font-mono text-[10px] font-bold bg-accent text-white border-2 border-ink px-2 py-0.5 self-start">RUST BACKEND</span>
              </div>

              {/* Box 3: Privacy Guard */}
              <div className="md:col-span-4 card-brutal p-6 flex flex-col justify-between min-h-[180px] bg-paper">
                <div>
                  <span className="font-mono text-xs uppercase tracking-widest text-muted block mb-2">// REDACTION</span>
                  <h3 className="font-display font-black text-xl uppercase mb-2">SMART PRIVACY GUARD</h3>
                  <p className="text-xs text-ink-2 leading-relaxed">
                    StepPilot automatically redacts passwords, credit card inputs, and credentials before constructing prompt payloads.
                  </p>
                </div>
                <span className="font-mono text-[10px] font-bold bg-paper-3 border-2 border-ink px-2 py-0.5 self-start flex items-center gap-1">
                  <Lock className="w-3 h-3 text-accent" /> AUTO-REDACT ACTIVE
                </span>
              </div>

              {/* Box 4: Autonomous Controls */}
              <div className="md:col-span-8 card-brutal p-6 flex flex-col justify-between min-h-[180px] bg-paper">
                <div>
                  <span className="font-mono text-xs uppercase tracking-widest text-muted block mb-2">// POST-MVP</span>
                  <h3 className="font-display font-black text-2xl uppercase mb-2">AUTONOMOUS CONTROL (COMING SOON)</h3>
                  <p className="text-sm text-ink-2 leading-relaxed">
                    Optionally grant StepPilot permissions to interact with elements directly using keyboard and cursor emulation. Features fully configurable safety sandboxing, manual overrides, and step verification bounds.
                  </p>
                </div>
                <div className="flex gap-2 mt-4">
                  <span className="bg-paper-3 px-2 py-0.5 border-2 border-ink font-mono text-[10px] font-bold">PYAUTOGUI</span>
                  <span className="bg-paper-3 px-2 py-0.5 border-2 border-ink font-mono text-[10px] font-bold">SANDBOXED RUNTIME</span>
                </div>
              </div>

            </div>
          </div>
        </div>
      </section>

      {/* SECTION HEAD & FAQ - 06 CONVERSATIONAL FAQ */}
      <section id="faq" className="w-full border-b-3 border-ink">
        <div className="max-w-7xl mx-auto px-6 py-16 grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12">
          {/* Left margin label */}
          <div className="lg:col-span-3 text-left">
            <span className="font-display font-black text-xl tracking-wider text-accent border-b-3 border-accent pb-1 inline-block">
              03 — FREQUENT DISPUTES
            </span>
          </div>

          {/* Conversational FAQ */}
          <div className="lg:col-span-9 text-left">
            <h2 className="font-display font-black text-4xl uppercase tracking-tight mb-8">
              COMMON INQUIRIES & DEEP DIVES
            </h2>

            <div className="w-full">
              <FaqItem 
                question="How does the app capture and parse my screen?"
                answer="StepPilot uses high-performance DXGI Desktop Duplication API capture inside Rust. The sidecar processes the frame using PaddleOCR for local OCR, mapping all coordinates, while simultaneously parsing the Windows Accessibility Tree (UIA) to identify buttons, input containers, and native elements."
              />
              <FaqItem 
                question="Are my screenshots sent to third-party servers?"
                answer="We prioritize security. Screen coordinates and structures are processed locally. Only sanitized, redacted text structures and specific visual sub-crops containing interactive regions are transmitted to models (such as OpenAI or GitHub Copilot API) to plan guidance steps. Your full desktop image is never uploaded."
              />
              <FaqItem 
                question="Does StepPilot take control of my mouse and keyboard?"
                answer="By default, NO. StepPilot's core philosophy is visual guidance. It acts as an overlay HUD displaying arrows and instructions. You remain in complete control. An optional autonomous execution mode is in development and will require explicit user permission and sandboxing configurations."
              />
              <FaqItem 
                question="Which operating systems are currently supported?"
                answer="Windows 10/11 is currently required due to our deep integration with Windows DXGI captures and the Windows UI Automation APIs. Support for macOS and Linux is planned for future phases using system-specific accessibility and capturing frameworks."
              />
            </div>
          </div>
        </div>
      </section>

      {/* DOWNLOAD / CTA STRIP SECTION */}
      <section id="download" className="w-full bg-accent text-white py-20 px-6 border-b-3 border-ink relative overflow-hidden">
        {/* Decorative Grid Lines */}
        <div className="absolute inset-0 opacity-10 bg-[linear-gradient(to_right,#000_1px,transparent_1px),linear-gradient(to_bottom,#000_1px,transparent_1px)] bg-[size:40px_40px] pointer-events-none"></div>

        <div className="max-w-4xl mx-auto text-center relative z-10">
          <h2 className="font-display font-black text-4xl md:text-6xl uppercase tracking-tight mb-6 text-stroke-brutal">
            START PILOTING YOUR DESKTOP TODAY
          </h2>
          <p className="font-mono text-sm md:text-base mb-10 max-w-xl mx-auto leading-relaxed text-white/90">
            Get real-time visual assistance on Windows 10/11. Zero local setup required to begin. Plug in your keys and fly.
          </p>
          
          <div className="flex flex-col sm:flex-row justify-center items-center gap-6">
            <a 
              href="https://github.com/NischalGautam8/StepPilot/releases" 
              className="w-full sm:w-auto bg-white text-ink border-3 border-ink px-8 py-4 font-display font-black text-xl uppercase tracking-wider flex items-center justify-center gap-2 hover:translate-x-[-4px] hover:translate-y-[-4px] hover:shadow-[6px_6px_0px_var(--color-ink)] transition-all duration-150 shadow-[4px_4px_0px_var(--color-ink)] cursor-pointer"
            >
              <Download className="w-6 h-6 stroke-[3px] text-accent" />
              DOWNLOAD STABLE (.EXE)
            </a>
            
            <a 
              href="https://github.com/NischalGautam8/StepPilot" 
              target="_blank" 
              rel="noopener noreferrer"
              className="w-full sm:w-auto bg-transparent text-white border-3 border-white px-8 py-4 font-display font-black text-xl uppercase tracking-wider flex items-center justify-center gap-2 hover:translate-x-[-4px] hover:translate-y-[-4px] hover:shadow-[6px_6px_0px_#fff] transition-all duration-150 shadow-[4px_4px_0px_#fff] cursor-pointer"
            >
              <GithubIcon className="w-6 h-6 stroke-[3.0px]" />
              SOURCE CODE
            </a>
          </div>
          
          <div className="mt-8 text-xs font-mono text-white/80">
            MIT LICENSE • VITE + TAURI V2 + RUST + FASTAPI
          </div>
        </div>
      </section>

      {/* FOOTER - FT8 MARQUEE SCROLL */}
      <footer className="w-full overflow-hidden bg-paper border-b-3 border-ink" aria-label="Footer">
        <div className="flex w-[200%] md:w-[150%] animate-marquee whitespace-nowrap py-4 border-t-3 border-ink">
          <span className="font-display font-black text-lg md:text-xl uppercase tracking-wider mx-4">
            STEPPILOT · AI DESKTOP GUIDANCE ASSISTANT · LOCAL OCR · TAURI CORE · MIT LICENSED · STEPPILOT · AI DESKTOP GUIDANCE ASSISTANT · LOCAL OCR · TAURI CORE · MIT LICENSED · STEPPILOT · AI DESKTOP GUIDANCE ASSISTANT · LOCAL OCR · TAURI CORE · MIT LICENSED ·
          </span>
          <span className="font-display font-black text-lg md:text-xl uppercase tracking-wider mx-4">
            STEPPILOT · AI DESKTOP GUIDANCE ASSISTANT · LOCAL OCR · TAURI CORE · MIT LICENSED · STEPPILOT · AI DESKTOP GUIDANCE ASSISTANT · LOCAL OCR · TAURI CORE · MIT LICENSED · STEPPILOT · AI DESKTOP GUIDANCE ASSISTANT · LOCAL OCR · TAURI CORE · MIT LICENSED ·
          </span>
        </div>
        <div className="border-t-3 border-ink py-4 px-6 flex flex-col sm:flex-row justify-between items-center gap-4 bg-paper-2 font-mono text-xs text-muted">
          <span>© 2026 STEPPILOT AUTHORS. ALL RIGHTS RESERVED.</span>
          <div className="flex gap-4">
            <a href="https://github.com/NischalGautam8/StepPilot" className="hover:text-accent font-bold">REPOSITORY</a>
            <span>•</span>
            <a href="https://github.com/NischalGautam8/StepPilot/blob/main/LICENSE" className="hover:text-accent font-bold">MIT LICENSE</a>
          </div>
        </div>
      </footer>

    </div>
  )
}

export default App
