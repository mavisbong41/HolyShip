import type { MailContextProvider, MailContextResult } from "../types/context";

/**
 * OfficeCurrentMailContextProvider
 * Reads the current Outlook message context via Office.js.
 *
 * In New Outlook for Windows, when a taskpane is open, user selection in the
 * message list updates getSelectedItemsAsync (Mailbox 1.13+) immediately,
 * whereas mailbox.item can remain fixed to the item opened first.
 * We query getSelectedItemsAsync first, falling back to mailbox.item.
 */
export class OfficeCurrentMailContextProvider implements MailContextProvider {
  async getContext(): Promise<MailContextResult> {
    try {
      const mailbox = typeof Office !== "undefined" ? Office.context?.mailbox : undefined;
      if (!mailbox) {
        return { state: "unavailable", item: null, error: "No mailbox context" };
      }

      let selectedItem: { itemId?: string; subject?: string; internetMessageId?: string } | null = null;
      if (typeof (mailbox as any).getSelectedItemsAsync === "function") {
        try {
          const selected = await new Promise<any>((resolve) => {
            (mailbox as any).getSelectedItemsAsync((asyncResult: any) => {
              if (
                asyncResult &&
                asyncResult.status === Office.AsyncResultStatus.Succeeded &&
                Array.isArray(asyncResult.value) &&
                asyncResult.value.length > 0
              ) {
                resolve(asyncResult.value[0]);
              } else {
                resolve(null);
              }
            });
          });
          if (selected) {
            selectedItem = selected;
          }
        } catch {
          // fallback to mailbox.item
        }
      }

      const item = mailbox.item;
      if (!item && !selectedItem) {
        return { state: "unavailable", item: null, error: "No mailbox item in context" };
      }

      let internetMessageId: string | null = null;
      try {
        if (typeof selectedItem?.internetMessageId === "string") {
          internetMessageId = selectedItem.internetMessageId;
        } else if (typeof item?.internetMessageId === "string") {
          internetMessageId = item.internetMessageId;
        }
      } catch {
        // not available on all hosts
      }

      const outlookItemId = selectedItem?.itemId || item?.itemId || null;
      const subject = selectedItem?.subject || item?.subject || null;
      const sender = item?.from?.emailAddress || null;
      const outlookReadState = typeof (item as any)?.isRead === "boolean"
        ? ((item as any).isRead ? "READ" : "UNREAD")
        : "UNKNOWN";
      let outlookCategories: string[] = [];
      try {
        const categoriesApi = (item as any)?.categories;
        if (categoriesApi && typeof categoriesApi.getAsync === "function") {
          outlookCategories = await new Promise<string[]>((resolve) => {
            categoriesApi.getAsync((asyncResult: any) => {
              if (asyncResult?.status === Office.AsyncResultStatus.Succeeded && Array.isArray(asyncResult.value)) {
                resolve(asyncResult.value.map((entry: any) => String(entry?.displayName ?? entry)).filter(Boolean));
              } else {
                resolve([]);
              }
            });
          });
        }
      } catch {
        outlookCategories = [];
      }
      const outlookFolderId = typeof (item as any)?.parentFolderId === "string"
        ? (item as any).parentFolderId
        : null;

      return {
        state: "ready",
        item: {
          holyshipCaseId: null,
          outlookItemId,
          internetMessageId,
          sender,
          subject,
          outlookReadState,
          outlookCategories,
          outlookFolderId,
          outlookArchived: null,
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
