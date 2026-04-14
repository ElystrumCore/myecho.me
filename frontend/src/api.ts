/**
 * Echo API client for the owner dashboard.
 */

const API_BASE = "/api";

interface AssistResponse {
  result: string;
  action: string;
}

interface GenerateResponse {
  entry_id: string;
  status: string;
  title: string;
}

interface DraftEntry {
  id: string;
  title: string;
  status: string;
  created_at: string;
}

/**
 * Inline editor AI assist — sends selected text + action to Echo's voice engine.
 * Every action runs through the user's StyleFingerprint.
 */
export async function assistInline(
  userId: string,
  text: string,
  action: string = "rewrite",
  instruction?: string
): Promise<AssistResponse> {
  const res = await fetch(`${API_BASE}/echo/${userId}/assist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, action, instruction }),
  });
  if (!res.ok) throw new Error(`Assist failed: ${res.status}`);
  return res.json();
}

/**
 * Generate a new journal post in the user's voice.
 */
export async function generatePost(
  userId: string,
  topic?: string
): Promise<GenerateResponse> {
  const res = await fetch(`${API_BASE}/echo/${userId}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });
  if (!res.ok) throw new Error(`Generate failed: ${res.status}`);
  return res.json();
}

/**
 * List pending drafts.
 */
export async function listDrafts(userId: string): Promise<DraftEntry[]> {
  const res = await fetch(`${API_BASE}/echo/${userId}/drafts`);
  if (!res.ok) throw new Error(`Drafts fetch failed: ${res.status}`);
  return res.json();
}

/**
 * Publish or archive a draft.
 */
export async function updateDraft(
  userId: string,
  entryId: string,
  action: "publish" | "archive"
): Promise<{ entry_id: string; status: string }> {
  const res = await fetch(
    `${API_BASE}/echo/${userId}/drafts/${entryId}?action=${action}`,
    { method: "PUT" }
  );
  if (!res.ok) throw new Error(`Draft update failed: ${res.status}`);
  return res.json();
}
