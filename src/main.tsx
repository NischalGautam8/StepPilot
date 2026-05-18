import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { Overlay } from "./components";

// Intercept transparent overlay window route
const isOverlay = 
  window.location.hash === "#/overlay" || 
  window.location.search.includes("window=overlay");

if (isOverlay) {
  // Inject global transparent style overrides immediately at entrypoint
  const styleEl = document.createElement("style");
  styleEl.id = "overlay-entrypoint-transparency";
  styleEl.innerHTML = `
    html, body, #root {
      background: transparent !important;
      background-color: transparent !important;
    }
  `;
  document.head.appendChild(styleEl);
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    {isOverlay ? <Overlay /> : <App />}
  </React.StrictMode>,
);
