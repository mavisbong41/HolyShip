import type { MailContextProvider, MailContextResult } from "../types/context";

/**
 * OfficeCurrentMailContextProvider
 * Reads the current Outlook message context via Office.js.
 * Must be used only inside an Office.js initialised environment.
 */
export class OfficeCurrentMailContextProvider implements MailContextProvider {
  async getContext(): Promise<MailContextResult> {
    try {
      const item = Office.context?.mailbox?.item;
      if (!item) {
        return { state: "unavailable", item: null, error: "No mailbox item in context" };
      }

      // internetMessageId may not be synchronously available on all hosts
      let internetMessageId: string | null = null;
      try {
        if (typeof item.internetMessageId === "string") {
          internetMessageId = item.internetMessageId;
        }
      } catch {
        // not available in this host
      }

      const sender = item.from?.emailAddress ?? null;
      const subject = item.subject ?? null;
      const outlookItemId = item.itemId ?? null;

      return {
        state: "ready",
        item: {
          holyshipCaseId: null, // resolved by the identity adapter
          outlookItemId,
          internetMessageId,
          sender,
          subject,
        },
        error: null,
      };
    } catch (err) {
      return {
        state: "unavailable",
        item: null,
        error: err instanceof Error ? err.message : "Office context unavailable",
      };
    }
  }
}
