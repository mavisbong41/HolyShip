import React, { useMemo, useState } from "react";
import { Check, Mail, Send } from "lucide-react";
import { ApiError, generateReplyDraft, refineReplyDraft, sendReplyDraft } from "../api/client";
import type { ProductEmailDetail } from "../api/types";
import { displayValue, labelForField } from "../lib/labels";

type ReplyState = "REQUEST_INFORMATION" | "RESOLUTION_REPLY" | "NOT_AVAILABLE";

export function ReplyEmailSection({ detail }: { detail: ProductEmailDetail }): React.ReactElement {
  const policy = detail.reply_policy;
  const state: ReplyState = policy?.mode === "REQUEST_INFORMATION"
    ? "REQUEST_INFORMATION" : policy?.mode === "RESOLUTION_REPLY" ? "RESOLUTION_REPLY" : "NOT_AVAILABLE";
  const [subject, setSubject] = useState(`Re: ${detail.email.subject}`);
  const [draft, setDraft] = useState("");
  const [refinement, setRefinement] = useState("");
  const [busy, setBusy] = useState<"generate" | "refine" | "send" | null>(null);
  const [confirmSend, setConfirmSend] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const issueFields = useMemo(() => {
    const names = new Set([...(detail.comparison?.unresolved_fields || []), ...(detail.comparison?.mismatched_fields || [])]);
    return detail.comparison?.fields.filter((field) => names.has(field.field)) || [];
  }, [detail.comparison]);
  const errorMessage = (error: unknown, fallback: string) => error instanceof ApiError ? error.message : fallback;
  const generate = async () => {
    setBusy("generate"); setMessage(null); setConfirmSend(false); setSent(false);
    try { const result = await generateReplyDraft(detail.email.id); setDraft(result.draft || ""); }
    catch (error) { setMessage(errorMessage(error, "Could not generate reply.")); }
    finally { setBusy(null); }
  };
  const refine = async () => {
    if (!draft.trim() || !refinement.trim()) return;
    setBusy("refine"); setMessage(null);
    try { const result = await refineReplyDraft(detail.email.id, draft, refinement); setDraft(result.draft || draft); setRefinement(""); }
    catch (error) { setMessage(errorMessage(error, "Could not refine reply.")); }
    finally { setBusy(null); }
  };
  const send = async () => {
    if (!draft.trim()) return;
    if (!confirmSend) { setConfirmSend(true); return; }
    setBusy("send"); setMessage(null);
    try { await sendReplyDraft(detail.email.id, draft); setSent(true); setConfirmSend(false); }
    catch (error) { setMessage(errorMessage(error, "Could not send reply.")); }
    finally { setBusy(null); }
  };
  const requestInfo = state === "REQUEST_INFORMATION";
  const title = requestInfo ? "Information required" : state === "RESOLUTION_REPLY" ? "Ready to reply" : "Reply unavailable";
  const description = requestInfo ? "Missing / uncertain information must be confirmed before verification can continue."
    : state === "RESOLUTION_REPLY" ? "Verification is complete and no blocking issues remain." : policy?.reason || "Reply is unavailable for this case.";
  const statusLabel = requestInfo ? "Information Required" : state === "RESOLUTION_REPLY" ? "Ready to Reply" : "Reply Unavailable";
  return <div className="detail-section reply-email-section" aria-label="Reply Email">
    <div className="section-title-row reply-email-heading"><h3><Mail size={16} /> Reply Email</h3><span className={`badge ${state === "NOT_AVAILABLE" ? "badge-muted" : requestInfo ? "badge-warn" : "badge-good"}`}>{statusLabel}</span></div>
    <div className="reply-email-card">
      <strong>{title}</strong><p>{description}</p>
      {requestInfo ? <ul className="reply-required-list">
        {(policy?.missing_or_required_items || []).map((item) => <li key={item}><strong>Missing / uncertain:</strong> {item}</li>)}
        {issueFields.map((field) => <li key={`evidence-${field.field}`}><strong>Current evidence:</strong> {labelForField(field.field)} — BL shows “{displayValue(field.bl.raw ?? field.bl.canonical)}”</li>)}
        <li><strong>Reason:</strong> Cannot safely assume this value is correct</li>
      </ul> : state === "RESOLUTION_REPLY" ? <ul className="reply-required-list"><li><Check size={13} /> Comparison completed</li><li><Check size={13} /> No unresolved fields</li></ul> : null}
      {sent ? <div className="reply-success" role="status"><Check size={14} /> Reply sent</div> : <>
        {state === "NOT_AVAILABLE" ? <button type="button" className="btn-secondary" disabled>Generate Reply</button> : <button type="button" className="btn-secondary" disabled={busy !== null} onClick={() => void generate()}>{busy === "generate" ? "Generating…" : requestInfo ? "Generate Request Email" : "Generate Reply"}</button>}
        {draft && <div className="reply-draft-box"><span className="reply-draft-label">{requestInfo ? "Request for information" : "Resolution reply"}</span><label>Subject<input aria-label="Reply subject" value={subject} onChange={(event) => setSubject(event.target.value)} /></label><label>Email body<textarea aria-label="Reply draft" value={draft} onChange={(event) => setDraft(event.target.value)} rows={7} /></label><div className="reply-refine-row"><input aria-label="Refine instruction" placeholder="Optional refine instruction" value={refinement} onChange={(event) => setRefinement(event.target.value)} /><button type="button" className="btn-secondary" disabled={busy !== null || !refinement.trim()} onClick={() => void refine()}>{busy === "refine" ? "Refining…" : "Refine"}</button></div><button type="button" className="btn-primary" disabled={busy !== null || !draft.trim()} onClick={() => void send()}><Send size={14} />{busy === "send" ? "Sending…" : confirmSend ? "Confirm & Send" : "Send Reply"}</button></div>}
      </>}
      {message && <p className="reply-error" role="alert">{message}</p>}
    </div>
  </div>;
}
