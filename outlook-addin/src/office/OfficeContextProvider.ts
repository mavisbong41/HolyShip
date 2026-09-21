import type { MailContextProvider, MailContextResult } from "../types/context";

/**
 * OfficeCurrentMailContextProvider
 * Reads the current Outlook message context via Office.js.
 * Must be used only inside an Office.js initialised environment.
 */
export class OfficeCurrentMailContextProvider implements MailContextProvider {
  async getContext(): Promise<MailContextResult> {
    try {
      const mailbox = typeof Office !== "undefined" ? Office.context?.mailbox : undefined;
      if (!mailbox) {
        return { state: "unavailable", item: null, error: "No mailbox item in context" };
      }

      // Check if getSelectedItemsAsync is available (Mailbox 1.13+) for active item in list
      let selectedItem: { itemId?: string; subject?: string } | null = null;
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

      // internetMessageId may not be synchronously available on all hosts
      let internetMessageId: string | null = null;
      try {
        if (typeof item?.internetMessageId === "string") {
          internetMessageId = item.internetMessageId;
        }
      } catch {
        // not available in this host
      }

      const sender = item?.from?.emailAddress ?? null;
      const outlookItemId = (selectedItem?.itemId && selectedItem.itemId !== item?.itemId)
        ? selectedItem.itemId
        : (item?.itemId ?? selectedItem?.itemId ?? null);
      const subject = (selectedItem?.itemId && item?.itemId && selectedItem.itemId !== item.itemId && selectedItem.subject)
        ? selectedItem.subject
        : (item?.subject ?? selectedItem?.subject ?? null);

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
