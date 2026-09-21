import type { MailContextProvider, MailContextResult } from "../types/context";

/**
 * OfficeCurrentMailContextProvider
 * Reads the current Outlook message context via Office.js.
 *
 * Deliberately avoids getSelectedItemsAsync: in New Outlook that API can return
 * the email the task pane was first opened for (not the currently selected one),
 * causing stale results.  mailbox.item is the reliable source for the item that
 * is currently displayed in the reading pane.
 */
export class OfficeCurrentMailContextProvider implements MailContextProvider {
  async getContext(): Promise<MailContextResult> {
    try {
      const mailbox = typeof Office !== "undefined" ? Office.context?.mailbox : undefined;
      if (!mailbox) {
        return { state: "unavailable", item: null, error: "No mailbox context" };
      }

      const item = mailbox.item;
      if (!item) {
        return { state: "unavailable", item: null, error: "No mailbox item in context" };
      }

      let internetMessageId: string | null = null;
      try {
        if (typeof item.internetMessageId === "string") {
          internetMessageId = item.internetMessageId;
        }
      } catch {
        // not available on all hosts
      }

      return {
        state: "ready",
        item: {
          holyshipCaseId: null,
          outlookItemId: item.itemId ?? null,
          internetMessageId,
          sender: item.from?.emailAddress ?? null,
          subject: item.subject ?? null,
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
