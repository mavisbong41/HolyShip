// Office context types for the Add-in's abstraction layer.
// These types decouple Office.js from UI components.

export interface MailContextItem {
  /** HolyShip-internal stable case id, if already resolved */
  holyshipCaseId: string | null;
  /** The Outlook item id (may not map directly to backend) */
  outlookItemId: string | null;
  /** Internet Message-ID header, more stable for cross-system matching */
  internetMessageId: string | null;
  /** Sender email address */
  sender: string | null;
  /** Email subject */
  subject: string | null;
  /** Best-effort Outlook read state, when exposed by the host */
  outlookReadState?: "READ" | "UNREAD" | "UNKNOWN";
  /** Outlook native categories/tags, when exposed by the host */
  outlookCategories?: string[];
  /** Current Outlook folder id, when exposed by the host */
  outlookFolderId?: string | null;
  /** Best-effort archive state, when exposed by the host */
  outlookArchived?: boolean | null;
}

export type MailContextLoadState = "loading" | "ready" | "unavailable";

export interface MailContextResult {
  state: MailContextLoadState;
  item: MailContextItem | null;
  error: string | null;
}

/** Contract every context provider must satisfy */
export interface MailContextProvider {
  getContext(): Promise<MailContextResult>;
}
