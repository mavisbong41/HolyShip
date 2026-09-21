import type { MailContextProvider, MailContextResult } from "../types/context";

/**
 * OfficeCurrentMailContextProvider
 * Reads the current Outlook message context via Office.js.
 * Must be used only inside an Office.js initialised environment.
 *
 * Strategy:
 * 1. Try getSelectedItemsAsync (Mailbox 1.13+) — reflects what is selected in the
 *    list view, which is what we want when the user clicks a different email.
 * 2. Fall back to mailbox.item — reflects the reading pane item.
 *
 * In New Outlook for Windows, mailbox.item can lag behind the list selection by
 * several seconds.  getSelectedItemsAsync is updated immediately on click.
 */
export class OfficeCurrentMailContextProvider implements MailContextProvider {
  async getContext(): Promise<MailContextResult> {
    try {
      const mailbox = typeof Office !== "undefined" ? Office.context?.mailbox : undefined;
      if (!mailbox) {
        return { state: "unavailable", item: null, error: "No mailbox context" };
      }

      // ── Primary path: getSelectedItemsAsync (Mailbox 1.13+) ───────────────
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
            // getSelectedItemsAsync result fields (Mailbox 1.13):
            // itemId, subject, hasAttachment, internetMessageId, conversationId, ...
            const outlookItemId: string | null = selected.itemId ?? null;
            const subject: string | null = selected.subject ?? null;
            const internetMessageId: string | null = selected.internetMessageId ?? null;
            // sender is NOT in getSelectedItemsAsync; fall through to mailbox.item for sender
            let sender: string | null = null;
            try {
              sender = mailbox.item?.from?.emailAddress ?? null;
            } catch {
              // optional
            }

            return {
              state: "ready",
              item: {
                holyshipCaseId: null,
                outlookItemId,
                internetMessageId,
                sender,
                subject,
              },
              error: null,
            };
          }
        } catch {
          // fall through to mailbox.item
        }
      }

      // ── Fallback path: mailbox.item (classic Outlook / older clients) ──────
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
        // not available
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
