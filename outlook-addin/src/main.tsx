import React from "react";
import { createRoot } from "react-dom/client";
import "./styles/tokens.css";
import "./styles/pane.css";
import { TaskPane } from "./components/TaskPane";
import { OfficeCurrentMailContextProvider } from "./office/OfficeContextProvider";

const contextProvider = new OfficeCurrentMailContextProvider();

function mountApp(): void {
  const root = document.getElementById("root");
  if (!root) throw new Error("Root element not found");
  createRoot(root).render(
    <React.StrictMode>
      <TaskPane contextProvider={contextProvider} />
    </React.StrictMode>,
  );
}

// Office.js may not be loaded in local dev (no real Outlook runtime).
// Detect the environment and mount appropriately.
if (typeof Office !== "undefined" && typeof Office.onReady === "function") {
  Office.onReady(() => {
    mountApp();
  });
} else {
  // Local dev without Office runtime — mount immediately
  mountApp();
}
