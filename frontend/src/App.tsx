import { useRef } from "react";
import { EchoEditor } from "./components/EchoEditor";
import { VoiceRecorder } from "./components/VoiceRecorder";

export function App() {
  // TODO: get from auth context
  const userId = "demo-user-id";
  const editorInsertRef = useRef<((text: string) => void) | null>(null);

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
    </div>
  );
}
