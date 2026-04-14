/**
 * EchoEditor — BlockNote rich text editor wired to Echo's voice engine.
 *
 * The editor doesn't know it's writing as the user. It calls Echo's /assist
 * endpoint for every AI action, and Echo handles the voice. The owner writes,
 * selects text, triggers an AI action, and gets back text rewritten in their
 * StyleFingerprint.
 *
 * AI actions available via toolbar button or /ai slash command:
 * - Rewrite in my voice
 * - Continue this thought
 * - Make more direct / casual / formal
 * - Add evidence from expertise
 * - What would I say about [topic]
 * - Custom instruction
 */

import "@blocknote/core/fonts/inter.css";
import "@blocknote/mantine/style.css";

import { useCreateBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/mantine";
import { useState, useCallback } from "react";
import { assistInline } from "../api";

interface EchoEditorProps {
  userId: string;
  initialContent?: string;
  onSave?: (content: string) => void;
}

/**
 * AI assist actions shown in the editor toolbar.
 */
const AI_ACTIONS = [
  { key: "rewrite", label: "Rewrite in my voice" },
  { key: "continue", label: "Continue this thought" },
  { key: "more_direct", label: "Make more direct" },
  { key: "more_casual", label: "Make more casual" },
  { key: "more_formal", label: "Make more formal" },
  { key: "add_evidence", label: "Add evidence" },
  { key: "position", label: "What would I say about this" },
] as const;

export function EchoEditor({ userId, onSave }: EchoEditorProps) {
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResult, setAiResult] = useState<string | null>(null);
  const [selectedText, setSelectedText] = useState("");

  const editor = useCreateBlockNote();

  const handleAiAction = useCallback(
    async (action: string, instruction?: string) => {
      if (!selectedText && action !== "continue") {
        setAiResult("Select some text first, or use 'Continue this thought'.");
        return;
      }

      // For 'continue', use the full document content as context
      const text =
        action === "continue" && !selectedText
          ? // Get all blocks as markdown-ish text
            editor.document
              .map((block) => {
                if (block.type === "paragraph" && block.content) {
                  return (block.content as Array<{ type: string; text?: string }>)
                    .map((c) => c.text || "")
                    .join("");
                }
                return "";
              })
              .filter(Boolean)
              .join("\n\n")
          : selectedText;

      if (!text) {
        setAiResult("Nothing to work with — write something first.");
        return;
      }

      setAiLoading(true);
      setAiResult(null);

      try {
        const response = await assistInline(userId, text, action, instruction);
        setAiResult(response.result);
      } catch (err) {
        setAiResult(
          `Error: ${err instanceof Error ? err.message : "AI assist failed"}`
        );
      } finally {
        setAiLoading(false);
      }
    },
    [userId, selectedText, editor]
  );

  const handleSelectionChange = useCallback(() => {
    const selection = window.getSelection();
    setSelectedText(selection?.toString() || "");
  }, []);

  return (
    <div className="echo-editor">
      {/* AI assist toolbar */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "0.5rem",
          marginBottom: "1rem",
          paddingBottom: "1rem",
          borderBottom: "1px solid #222",
        }}
      >
        {AI_ACTIONS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => handleAiAction(key)}
            disabled={aiLoading}
            style={{
              background: "transparent",
              border: "1px solid #333",
              color: "#808080",
              padding: "0.3rem 0.7rem",
              fontSize: "0.8rem",
              cursor: aiLoading ? "wait" : "pointer",
              borderRadius: "3px",
              fontFamily: "'Inter', sans-serif",
            }}
          >
            {label}
          </button>
        ))}
        <button
          onClick={() => {
            const instruction = prompt("Custom instruction:");
            if (instruction) handleAiAction("custom", instruction);
          }}
          disabled={aiLoading}
          style={{
            background: "transparent",
            border: "1px solid #555",
            color: "#7eb8da",
            padding: "0.3rem 0.7rem",
            fontSize: "0.8rem",
            cursor: aiLoading ? "wait" : "pointer",
            borderRadius: "3px",
            fontFamily: "'Inter', sans-serif",
          }}
        >
          /ai custom...
        </button>
      </div>

      {/* AI result panel */}
      {(aiLoading || aiResult) && (
        <div
          style={{
            background: "#111",
            borderLeft: "3px solid #7eb8da",
            padding: "1rem",
            marginBottom: "1rem",
            borderRadius: "0 4px 4px 0",
            fontSize: "0.9rem",
            lineHeight: 1.6,
            whiteSpace: "pre-wrap",
          }}
        >
          {aiLoading ? (
            <span style={{ color: "#555" }}>Echo is thinking...</span>
          ) : (
            <>
              <div style={{ color: "#e0e0e0" }}>{aiResult}</div>
              <div
                style={{
                  marginTop: "0.5rem",
                  display: "flex",
                  gap: "0.5rem",
                }}
              >
                <button
                  onClick={() => {
                    if (aiResult) {
                      // Insert the AI result as a new paragraph at cursor
                      editor.insertBlocks(
                        [{ type: "paragraph", content: aiResult }],
                        editor.document[editor.document.length - 1],
                        "after"
                      );
                      setAiResult(null);
                    }
                  }}
                  style={{
                    background: "transparent",
                    border: "1px solid #6bbd7b",
                    color: "#6bbd7b",
                    padding: "0.2rem 0.6rem",
                    fontSize: "0.75rem",
                    cursor: "pointer",
                    borderRadius: "3px",
                  }}
                >
                  Insert below
                </button>
                <button
                  onClick={() => setAiResult(null)}
                  style={{
                    background: "transparent",
                    border: "1px solid #333",
                    color: "#555",
                    padding: "0.2rem 0.6rem",
                    fontSize: "0.75rem",
                    cursor: "pointer",
                    borderRadius: "3px",
                  }}
                >
                  Dismiss
                </button>
              </div>
              <div
                style={{
                  marginTop: "0.5rem",
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: "0.7rem",
                  color: "#555",
                }}
              >
                echo-generated
              </div>
            </>
          )}
        </div>
      )}

      {/* BlockNote editor */}
      <div
        onMouseUp={handleSelectionChange}
        onKeyUp={handleSelectionChange}
        style={{
          background: "#0d0d0d",
          borderRadius: "4px",
          minHeight: "400px",
        }}
      >
        <BlockNoteView editor={editor} theme="dark" />
      </div>

      {/* Save action */}
      {onSave && (
        <div style={{ marginTop: "1rem", textAlign: "right" }}>
          <button
            onClick={() => {
              const markdown = editor.document
                .map((block) => {
                  if (block.type === "paragraph" && block.content) {
                    return (block.content as Array<{ type: string; text?: string }>)
                      .map((c) => c.text || "")
                      .join("");
                  }
                  if (block.type === "heading" && block.content) {
                    const level = (block.props as { level?: number })?.level || 1;
                    const text = (block.content as Array<{ type: string; text?: string }>)
                      .map((c) => c.text || "")
                      .join("");
                    return "#".repeat(level) + " " + text;
                  }
                  return "";
                })
                .filter(Boolean)
                .join("\n\n");
              onSave(markdown);
            }}
            style={{
              background: "#7eb8da",
              color: "#0d0d0d",
              border: "none",
              padding: "0.5rem 1.5rem",
              fontSize: "0.9rem",
              cursor: "pointer",
              borderRadius: "3px",
              fontWeight: 500,
            }}
          >
            Save Draft
          </button>
        </div>
      )}
    </div>
  );
}
