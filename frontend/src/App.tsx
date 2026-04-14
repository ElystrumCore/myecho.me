import { useRef, useState } from "react";
import { EchoEditor } from "./components/EchoEditor";
import { VoiceRecorder } from "./components/VoiceRecorder";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function getInitialUserId() {
  if (typeof window === "undefined") {
    return import.meta.env.VITE_ECHO_USER_ID ?? "";
  }

  const params = new URLSearchParams(window.location.search);
  return params.get("user_id") ?? import.meta.env.VITE_ECHO_USER_ID ?? "";
}

export function App() {
  const [userId, setUserId] = useState(getInitialUserId);
  const editorInsertRef = useRef<((text: string) => void) | null>(null);
  const hasValidUserId = UUID_PATTERN.test(userId);

  return (
    <div
      style={{
        maxWidth: 800,
        margin: "0 auto",
        padding: "2rem",
        fontFamily: "'Inter', sans-serif",
      }}
    >
      <header style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "1.4rem", fontWeight: 400 }}>
          Echo Dashboard
        </h1>
        <p style={{ color: "#808080", fontSize: "0.9rem" }}>
          Write, speak, and collaborate with your Echo.
        </p>
      </header>

      <section
        style={{
          border: "1px solid #222",
          borderRadius: 4,
          padding: "1rem",
          marginBottom: "1rem",
        }}
      >
        <label
          htmlFor="echo-user-id"
          style={{
            display: "block",
            marginBottom: "0.5rem",
            fontSize: "0.8rem",
            color: "#808080",
          }}
        >
          Active user id
        </label>
        <input
          id="echo-user-id"
          value={userId}
          onChange={(event) => {
            setUserId(event.target.value.trim());
          }}
          placeholder="00000000-0000-0000-0000-000000000000"
          spellCheck={false}
          style={{
            width: "100%",
            background: "#111",
            border: "1px solid #333",
            color: "#e0e0e0",
            borderRadius: 3,
            padding: "0.65rem 0.75rem",
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: "0.8rem",
          }}
        />
        {!hasValidUserId && (
          <p style={{ marginTop: "0.75rem", color: "#d4785c", fontSize: "0.8rem" }}>
            Enter a real Echo user UUID, or set <code>VITE_ECHO_USER_ID</code> or
            <code>?user_id=...</code>, before using dashboard actions.
          </p>
        )}
      </section>

      {hasValidUserId && (
        <>
          <VoiceRecorder
            userId={userId}
            onTranscript={(text) => {
              if (editorInsertRef.current) {
                editorInsertRef.current(text);
              }
            }}
          />

          <EchoEditor
            userId={userId}
            onInsertRef={(fn) => {
              editorInsertRef.current = fn;
            }}
          />
        </>
      )}
    </div>
  );
}
