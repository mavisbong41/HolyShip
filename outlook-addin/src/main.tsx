import React from "react";
import { createRoot } from "react-dom/client";
import "./styles/tokens.css";
import "./styles/pane.css";
import { TaskPane } from "./components/TaskPane";
import { OfficeCurrentMailContextProvider } from "./office/OfficeContextProvider";
import { FakeCurrentMailContextProvider } from "./office/FakeContextProvider";
import { demoCases } from "./lib/demoCases";

function getInitialDemoKey(): string | null {
  const params = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
  const hasOffice = typeof Office !== "undefined" && typeof Office.context?.mailbox !== "undefined";

  // Standalone browser dev or explicitly requested demo mode:
  if (!hasOffice || params?.has("preview") || params?.has("fake") || params?.has("demo")) {
    const demoParam = params?.get("demo");
    if (demoParam && demoParam in demoCases) {
      return demoParam;
    }
    return "mismatchReview";
  }
  return null;
}

function getContextProvider() {
  const params = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
  const isPreview = params ? (params.has("preview") || params.has("fake") || params.has("demo")) : false;
  const hasOffice = typeof Office !== "undefined" && typeof Office.context?.mailbox !== "undefined";

  if (!hasOffice || isPreview) {
    const subject = params?.get("subject") || undefined;
    const internetMessageId = params?.get("messageId") || undefined;
    const outlookReadState = (params?.get("read") as any) || undefined;
    const outlookFolderId = params?.get("folder") || undefined;
    return new FakeCurrentMailContextProvider({
      subject,
      internetMessageId,
      outlookReadState,
      outlookFolderId,
    });
  }

  return new OfficeCurrentMailContextProvider();
}

function mountApp(): void {
  const root = document.getElementById("root");
  if (!root) throw new Error("Root element not found");
  createRoot(root).render(
    <React.StrictMode>
      <TaskPane
        contextProvider={getContextProvider()}
        initialDemoKey={getInitialDemoKey()}
      />
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
