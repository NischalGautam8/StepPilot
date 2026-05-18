import { useEffect, useState, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen, emit } from "@tauri-apps/api/event";
import { useOverlayStore } from "../stores";

export function Overlay() {
  const { activeHint, visible, setHint, clearHint, setVisible } = useOverlayStore();

  useEffect(() => {
    // Listen for show-guidance-hint event from the main window or Rust
    const unlistenShow = listen<any>("show-guidance-hint", (event) => {
      console.log("Received guidance hint event:", event.payload);
      setHint(event.payload);
      setVisible(true);
    });

    // Listen for clear-guidance-hint event
    const unlistenClear = listen<any>("clear-guidance-hint", () => {
      console.log("Received clear guidance hint event");
      clearHint();
      setVisible(false);
    });

    return () => {
      unlistenShow.then((fn) => fn());
      unlistenClear.then((fn) => fn());
    };
  }, [setHint, clearHint, setVisible]);

  // Draggable Card States and Handlers
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const cardRef = useRef<HTMLDivElement>(null);

  // Reset custom offset when active step changes to snap to next target
  useEffect(() => {
    setPosition(null);
  }, [activeHint]);

  // Synchronize card coordinates/bounds with Rust FFI dynamic click-through
  useEffect(() => {
    if (!visible || !activeHint) {
      invoke("clear_overlay_card_bounds").catch(() => {});
      return;
    }

    const updateBounds = () => {
      if (cardRef.current) {
        const rect = cardRef.current.getBoundingClientRect();
        invoke("set_overlay_card_bounds", {
          x: Math.round(rect.left),
          y: Math.round(rect.top),
          w: Math.round(rect.width),
          h: Math.round(rect.height)
        }).catch(() => {});
      }
    };

    updateBounds();
    const interval = setInterval(updateBounds, 100);

    return () => {
      clearInterval(interval);
      invoke("clear_overlay_card_bounds").catch(() => {});
    };
  }, [position, visible, activeHint]);

  useEffect(() => {
    if (!isDragging) return;
    
    const handleMouseMove = (e: MouseEvent) => {
      setPosition({
        x: Math.max(0, Math.min(window.innerWidth - 300, e.clientX - dragOffset.x)),
        y: Math.max(0, Math.min(window.innerHeight - 150, e.clientY - dragOffset.y))
      });
    };
    
    const handleMouseUp = () => {
      setIsDragging(false);
    };
    
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, dragOffset]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return; // Left click only
    setIsDragging(true);
    
    const tx = activeHint?.bbox && activeHint.bbox[2] > 0 
      ? activeHint.bbox[0] + activeHint.bbox[2] / 2 
      : window.innerWidth / 2;
    const ty = activeHint?.bbox && activeHint.bbox[3] > 0 
      ? activeHint.bbox[1] + activeHint.bbox[3] + 15 
      : window.innerHeight / 2;
      
    const currentX = position ? position.x : Math.max(20, Math.min(window.innerWidth - 320, tx - 150));
    const currentY = position ? position.y : Math.max(20, Math.min(window.innerHeight - 150, ty));
    
    setDragOffset({
      x: e.clientX - currentX,
      y: e.clientY - currentY
    });
  };

  if (!visible || !activeHint) return null;

  // Extract physical bbox coordinates and convert to logical layout coordinates based on DPI scaling factor
  const dpr = window.devicePixelRatio || 1.0;
  const [physX, physY, physW, physH] = activeHint.bbox || [0, 0, 0, 0];
  const x = physX / dpr;
  const y = physY / dpr;
  const w = physW / dpr;
  const h = physH / dpr;
  const hasBbox = activeHint.bbox && w > 0 && h > 0;

  // Safe tooltip coordinates to prevent drawing off-screen
  const tooltipX = hasBbox ? x + w / 2 : window.innerWidth / 2;
  const tooltipY = hasBbox ? y + h + 15 : window.innerHeight / 2;

  // Pulse circle coordinates at the center of target
  const centerX = hasBbox ? x + w / 2 : 0;
  const centerY = hasBbox ? y + h / 2 : 0;

  return (
    <div style={{
      position: "fixed",
      top: 0,
      left: 0,
      width: "100vw",
      height: "100vh",
      pointerEvents: "none",
      zIndex: 99999,
      background: "transparent",
      overflow: "hidden",
      fontFamily: "'Inter', sans-serif"
    }}>
      {/* Full-screen SVG overlay */}
      <svg style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none"
      }}>
        {/* Glow Filters */}
        <defs>
          <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Bounding Box Around Element */}
        {hasBbox && (
          <g>
            {/* Glowing background rectangle */}
            <rect
              x={x}
              y={y}
              width={w}
              height={h}
              rx={6}
              ry={6}
              fill="rgba(139, 92, 246, 0.05)"
              stroke="#a78bfa"
              strokeWidth={3}
              filter="url(#neon-glow)"
              style={{
                animation: "dash-pulse 2s infinite ease-in-out",
                strokeDasharray: "8 4"
              }}
            />
          </g>
        )}

        {/* Pulse circle at center of target */}
        {hasBbox && (
          <g>
            {/* Expanding Pulse Ring 1 */}
            <circle
              cx={centerX}
              cy={centerY}
              r={12}
              fill="none"
              stroke="#c084fc"
              strokeWidth={2}
              style={{
                animation: "pulse-ring 1.8s infinite cubic-bezier(0.215, 0.610, 0.355, 1)",
                transformOrigin: `${centerX}px ${centerY}px`
              }}
            />
            {/* Expanding Pulse Ring 2 */}
            <circle
              cx={centerX}
              cy={centerY}
              r={12}
              fill="none"
              stroke="#818cf8"
              strokeWidth={1.5}
              style={{
                animation: "pulse-ring 1.8s infinite cubic-bezier(0.215, 0.610, 0.355, 1)",
                animationDelay: "0.6s",
                transformOrigin: `${centerX}px ${centerY}px`
              }}
            />
            {/* Solid Core Dot */}
            <circle
              cx={centerX}
              cy={centerY}
              r={5}
              fill="#c084fc"
              filter="url(#neon-glow)"
              style={{
                animation: "core-glow 1.2s infinite alternate ease-in-out"
              }}
            />
          </g>
        )}
      </svg>

      {/* Floating Rich Glassmorphic Tooltip */}
      <div 
        ref={cardRef}
        style={{
          position: "absolute",
          left: `${position ? position.x : Math.max(20, Math.min(window.innerWidth - 320, tooltipX - 150))}px`,
          top: `${position ? position.y : Math.max(20, Math.min(window.innerHeight - 150, tooltipY))}px`,
          width: "300px",
          background: "rgba(15, 23, 42, 0.85)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          border: isDragging ? "1px solid rgba(16, 185, 129, 0.6)" : "1px solid rgba(139, 92, 246, 0.3)",
          borderRadius: "12px",
          padding: "16px",
          boxShadow: isDragging 
            ? "0 15px 30px -5px rgba(0, 0, 0, 0.6), 0 0 20px rgba(16, 185, 129, 0.3)"
            : "0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 0 15px rgba(139, 92, 246, 0.2)",
          display: "flex",
          flexDirection: "column",
          gap: "10px",
          animation: position ? "none" : "tooltip-slide-in 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
          pointerEvents: "auto",
          cursor: "default",
          userSelect: "none"
        }}
      >
        {/* Sleek Drag Handle Navbar */}
        <div 
          onMouseDown={handleMouseDown}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "rgba(139, 92, 246, 0.15)",
            borderBottom: "1px solid rgba(139, 92, 246, 0.3)",
            margin: "-16px -16px 12px -16px",
            padding: "8px 12px",
            borderTopLeftRadius: "12px",
            borderTopRightRadius: "12px",
            cursor: isDragging ? "grabbing" : "grab",
            userSelect: "none"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            {/* Grab Grip Icon (6 dots) */}
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, 3px)",
              gap: "2px",
              opacity: 0.6
            }}>
              <div style={{ width: "3px", height: "3px", borderRadius: "50%", background: "#fff" }} />
              <div style={{ width: "3px", height: "3px", borderRadius: "50%", background: "#fff" }} />
              <div style={{ width: "3px", height: "3px", borderRadius: "50%", background: "#fff" }} />
              <div style={{ width: "3px", height: "3px", borderRadius: "50%", background: "#fff" }} />
              <div style={{ width: "3px", height: "3px", borderRadius: "50%", background: "#fff" }} />
              <div style={{ width: "3px", height: "3px", borderRadius: "50%", background: "#fff" }} />
            </div>
            <span style={{
              fontSize: "10px",
              fontWeight: 700,
              color: "#d8b4fe",
              textTransform: "uppercase",
              letterSpacing: "0.05em"
            }}>
              Guidance Console
            </span>
          </div>
          
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <div style={{
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              background: "#10b981",
              boxShadow: "0 0 8px #10b981",
              animation: "core-glow 1.2s infinite alternate ease-in-out"
            }} />
            <span style={{ fontSize: "9px", fontWeight: 600, color: "#a7f3d0", textTransform: "uppercase" }}>
              Active
            </span>
          </div>
        </div>

        {/* Tooltip Header Row */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{
            fontSize: "11px",
            fontWeight: "bold",
            color: "#c084fc",
            textTransform: "uppercase",
            letterSpacing: "0.05em"
          }}>
            Step {activeHint.step_number} of {activeHint.total_steps}
          </span>
          
          <span style={{
            background: "rgba(139, 92, 246, 0.2)",
            border: "1px solid rgba(139, 92, 246, 0.4)",
            color: "#d8b4fe",
            padding: "2px 8px",
            borderRadius: "20px",
            fontSize: "10px",
            fontWeight: 700,
            textTransform: "uppercase"
          }}>
            {activeHint.action}
          </span>
        </div>

        {/* Tooltip Body Instruction */}
        <p style={{
          margin: 0,
          fontSize: "13px",
          lineHeight: "1.5",
          color: "#f1f5f9",
          fontWeight: 500
        }}>
          {activeHint.description}
        </p>

        {/* Mini Coordinates Badge */}
        {hasBbox && (
          <div style={{
            fontSize: "10px",
            color: "#94a3b8",
            display: "flex",
            alignItems: "center",
            gap: "5px",
            fontFamily: "monospace",
            marginTop: "2px"
          }}>
            <span>📍</span>
            <span>[{x}, {y}, {w}, {h}]</span>
          </div>
        )}

        {/* Dynamic Navigation button in Overlay */}
        <div style={{
          display: "flex",
          justifyContent: "flex-end",
          marginTop: "6px"
        }}>
          <button
            onClick={async (e) => {
              e.stopPropagation();
              console.log("Overlay Next Step button clicked!");
              try {
                await emit("request-next-step");
              } catch(err) {
                console.error("Failed to emit request-next-step:", err);
              }
            }}
            style={{
              background: "linear-gradient(135deg, #10b981 0%, #8b5cf6 100%)",
              border: "none",
              borderRadius: "6px",
              color: "#ffffff",
              padding: "6px 14px",
              fontSize: "11px",
              fontWeight: 700,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "4px",
              boxShadow: "0 0 10px rgba(16, 185, 129, 0.3)",
              transition: "transform 0.15s ease, opacity 0.15s ease"
            }}
            onMouseOver={(e) => {
              (e.currentTarget as HTMLButtonElement).style.transform = "scale(1.03)";
              (e.currentTarget as HTMLButtonElement).style.opacity = "0.95";
            }}
            onMouseOut={(e) => {
              (e.currentTarget as HTMLButtonElement).style.transform = "scale(1)";
              (e.currentTarget as HTMLButtonElement).style.opacity = "1";
            }}
          >
            <span>{activeHint.step_number === activeHint.total_steps ? "Finish Guide ✓" : "Next Step →"}</span>
          </button>
        </div>
      </div>

      {/* Embedded CSS Animations */}
      <style>{`
        @keyframes dash-pulse {
          0% { stroke-dashoffset: 0; opacity: 0.8; }
          50% { stroke-dashoffset: 12; opacity: 1; }
          100% { stroke-dashoffset: 24; opacity: 0.8; }
        }
        @keyframes pulse-ring {
          0% { transform: scale(0.5); opacity: 1; }
          80%, 100% { transform: scale(2.5); opacity: 0; }
        }
        @keyframes core-glow {
          0% { transform: scale(0.9); opacity: 0.8; }
          100% { transform: scale(1.1); opacity: 1; }
        }
        @keyframes tooltip-slide-in {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
