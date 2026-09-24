import type { MailContextItem, MailContextProvider, MailContextResult } from "../types/context";

/**
 * FakeCurrentMailContextProvider
 * Used in tests and local UI dev to simulate Office.js context.
 */
export class FakeCurrentMailContextProvider implements MailContextProvider {
  private readonly result: MailContextResult;

  constructor(item?: Partial<MailContextItem> | null, error?: string) {
    if (error) {
      this.result = { state: "unavailable", item: null, error };
    } else if (item === null) {
      this.result = { state: "unavailable", item: null, error: "No item" };
    } else {
      this.result = {
        state: "ready",
        item: {
          holyshipCaseId: item?.holyshipCaseId ?? null,
          outlookItemId: item?.outlookItemId ?? "fake-outlook-id-001",
          internetMessageId: item?.internetMessageId ?? "<fake-msg-id@example.com>",
          sender: item?.sender ?? "shipper@example.com",
          subject: item?.subject ?? "Draft BL for BKG-20240501 for checking",
          outlookReadState: item?.outlookReadState ?? "UNREAD",
          outlookCategories: item?.outlookCategories ?? ["BL_COMPARISON"],
          outlookFolderId: item?.outlookFolderId ?? "inbox",
          outlookArchived: item?.outlookArchived ?? false,
        },
        error: null,
      };
    }
  }

  async getContext(): Promise<MailContextResult> {
    return this.result;
  }
}
