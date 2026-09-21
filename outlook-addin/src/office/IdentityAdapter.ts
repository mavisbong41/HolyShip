import { findEmailByMessageId, getEmailDetail, searchEmailQueue } from "../api/client";
import type { MailContextProvider } from "../types/context";
import type { ProductEmailDetail } from "../types/product";

export type IdentityResolutionStrategy =
  | "internet_message_id"
  | "subject_search"
  | "not_resolved";

export interface IdentityResolutionResult {
  detail: ProductEmailDetail | null;
  strategy: IdentityResolutionStrategy;
  confidence: "high" | "low" | "none";
  limitationNote: string | null;
}

/**
 * IdentityAdapter
 *
 * Resolves the current Outlook message to a HolyShip backend case.
 *
 * Resolution order:
 * 1. Use internet_message_id (most reliable cross-system identifier).
 * 2. Fall back to subject search (lower confidence).
 * 3. Return not_resolved with a documented limitation note.
 *
 * LIMITATION (documented per AGENTS.md §19):
 * This branch does NOT implement real Microsoft Graph ingestion.
 * The backend does not yet have a dedicated lookup-by-message-id endpoint.
 * Resolution works best when the email was ingested via a source that
 * preserved the internet Message-ID header in external_message_id.
 * Live Outlook Graph identity linkage is deferred to the next branch.
 */
export class IdentityAdapter {
  constructor(private readonly contextProvider: MailContextProvider) {}

  async resolve(): Promise<IdentityResolutionResult> {
    const ctx = await this.contextProvider.getContext();

    if (ctx.state !== "ready" || !ctx.item) {
      return {
        detail: null,
        strategy: "not_resolved",
        confidence: "none",
        limitationNote:
          "Office context is not available. Run inside an Outlook Add-in environment.",
      };
    }

    const { internetMessageId, subject, sender } = ctx.item;

    // Strategy 1: internet_message_id
    if (internetMessageId) {
      try {
        const detail = await findEmailByMessageId(internetMessageId);
        if (detail) {
          return {
            detail,
            strategy: "internet_message_id",
            confidence: "high",
            limitationNote: null,
          };
        }
      } catch {
        // fall through to next strategy
      }
    }

    // Strategy 2: subject & sender search
    if ((subject && subject.trim().length > 0) || (sender && sender.trim().length > 0)) {
      try {
        // Strip common email prefixes like "RE: ", "FW: ", "Re: " etc.
        const cleanSubject = subject
          ? subject.replace(/^(re|fw|fwd|答复|转发)[:：_\s]+/i, "").trim()
          : "";

        // Try searching with clean subject first, then fallback to full subject, then sender
        let page = await searchEmailQueue(cleanSubject || subject?.trim() || sender?.trim() || "");
        if (page.items.length === 0 && cleanSubject && subject && cleanSubject !== subject.trim()) {
          page = await searchEmailQueue(subject.trim());
        }
        if (page.items.length === 0 && sender && sender.trim()) {
          page = await searchEmailQueue(sender.trim());
        }

        // Prioritize match on both subject AND sender, fallback to exact subject match, then sender match
        const exactMatch =
          page.items.find((item) => {
            const subjectMatches =
              Boolean(subject && item.subject.trim().toLowerCase() === subject.trim().toLowerCase()) ||
              Boolean(cleanSubject && item.subject.replace(/^(re|fw|fwd|答复|转发)[:：_\s]+/i, "").trim().toLowerCase() === cleanSubject.toLowerCase());
            const senderMatches =
              Boolean(sender && item.sender && item.sender.trim().toLowerCase() === sender.trim().toLowerCase());
            return subjectMatches && senderMatches;
          }) ||
          page.items.find((item) =>
            Boolean(subject && (
              item.subject.trim().toLowerCase() === subject.trim().toLowerCase() ||
              item.subject.replace(/^(re|fw|fwd|答复|转发)[:：_\s]+/i, "").trim().toLowerCase() === cleanSubject.toLowerCase()
            ))
          ) ||
          page.items.find((item) =>
            Boolean(sender && item.sender && item.sender.trim().toLowerCase() === sender.trim().toLowerCase())
          );

        const target = exactMatch || (page.items.length === 1 ? page.items[0] : null);

        if (target) {
          const detail = await getEmailDetail(target.id);
          return {
            detail,
            strategy: "subject_search",
            confidence: "low",
            limitationNote:
              "Matched by subject text and sender. Identity linkage is approximate until live Graph integration is complete.",
          };
        }

        if (page.items.length > 1) {
          return {
            detail: null,
            strategy: "not_resolved",
            confidence: "none",
            limitationNote:
              "Multiple emails matched the search query. Cannot determine which case corresponds to this message without a Message-ID match.",
          };
        }
      } catch {
        // fall through
      }
    }

    return {
      detail: null,
      strategy: "not_resolved",
      confidence: "none",
      limitationNote:
        "This email has not been found in HolyShip. It may not have been processed yet, or Graph identity linkage is required for accurate matching.",
    };
  }
}
