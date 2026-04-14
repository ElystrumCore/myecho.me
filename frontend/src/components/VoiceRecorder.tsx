/**
 * VoiceRecorder — capture audio, transcribe via Echo API, insert into editor.
 *
 * The flow: record → stop → upload to /api/echo/{userId}/voice →
 * get back raw transcript + polished version → show both →
 * owner picks one to insert into BlockNote.
 */

import { useState, useRef, useCallback } from "react";

interface VoiceRecorderProps {
  userId: string;
  onTranscript: (text: string) => void;
}

type RecordingState = "idle" | "recording" | "processing";

export function VoiceRecorder({ userId, onTranscript }: VoiceRecorderProps) {
  const [state, setState] = useState<RecordingState>("idle");
  const [duration, setDuration] = useState(0);
  const [rawTranscript, setRawTranscript] = useState<string | null>(null);
  const [polished, setPolished] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startRecording = useCallback(async () => {
    setError(null);
    setRawTranscript(null);
    setPolished(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm",
      });

      chunksRef.current = [];
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.start(1000); // collect in 1s chunks
      mediaRecorderRef.current = mediaRecorder;
      setState("recording");
      setDuration(0);

      timerRef.current = setInterval(() => {
        setDuration((d) => d + 1);
      }, 1000);
    } catch (err) {
      setError(
        "Microphone access denied. Check your browser permissions."
      );
    }
  }, []);

  const stopRecording = useCallback(async () => {
    if (!mediaRecorderRef.current) return;

    // Stop timer
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    // Stop recording and wait for final data
    const recorder = mediaRecorderRef.current;
    const audioPromise = new Promise<Blob>((resolve) => {
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        resolve(blob);
      };
    });

    recorder.stop();
    recorder.stream.getTracks().forEach((t) => t.stop());
    setState("processing");

    const audioBlob = await audioPromise;

    // Upload to Echo API
    const formData = new FormData();
    formData.append("file", audioBlob, "recording.webm");

    try {
      const res = await fetch(
        `/api/echo/${userId}/voice?polish=true`,
        { method: "POST", body: formData }
      );
      if (!res.ok) throw new Error(`Transcription failed: ${res.status}`);

      const data = await res.json();
      setRawTranscript(data.raw_transcript);
      setPolished(data.polished || null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Transcription failed"
      );
    } finally {
      setState("idle");
    }
  }, [userId]);

  const formatDuration = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  return (
    <div
      style={{
        border: "1px solid #222",
        borderRadius: "4px",
        padding: "1rem",
        marginBottom: "1rem",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "1rem",
          marginBottom: rawTranscript || error ? "1rem" : 0,
        }}
      >
        {state === "idle" && (
          <button
            onClick={startRecording}
            style={{
              background: "transparent",
              border: "1px solid #d4785c",
              color: "#d4785c",
              padding: "0.4rem 1rem",
              fontSize: "0.85rem",
              cursor: "pointer",
              borderRadius: "3px",
              fontFamily: "'Inter', sans-serif",
            }}
          >
            Record
          </button>
        )}
        {state === "recording" && (
          <>
            <button
              onClick={stopRecording}
              style={{
                background: "#d4785c",
                border: "none",
                color: "#0d0d0d",
                padding: "0.4rem 1rem",
                fontSize: "0.85rem",
                cursor: "pointer",
                borderRadius: "3px",
                fontFamily: "'Inter', sans-serif",
                fontWeight: 500,
              }}
            >
              Stop
            </button>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: "0.85rem",
                color: "#d4785c",
              }}
            >
              {formatDuration(duration)}
            </span>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: "#d4785c",
                animation: "pulse 1s infinite",
              }}
            />
          </>
        )}
        {state === "processing" && (
          <span style={{ color: "#808080", fontSize: "0.85rem" }}>
            Transcribing {formatDuration(duration)} of audio...
          </span>
        )}
        <span
          style={{
            marginLeft: "auto",
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: "0.7rem",
            color: "#555",
          }}
        >
          voice → text → echo
        </span>
      </div>

      {error && (
        <div style={{ color: "#d4785c", fontSize: "0.85rem" }}>{error}</div>
      )}

      {rawTranscript && (
        <div>
          {/* Polished version (preferred) */}
          {polished && (
            <div
              style={{
                background: "#111",
                borderLeft: "3px solid #6bbd7b",
                padding: "1rem",
                borderRadius: "0 4px 4px 0",
                marginBottom: "0.75rem",
              }}
            >
              <div
                style={{
                  fontSize: "0.7rem",
                  color: "#6bbd7b",
                  fontFamily: "'JetBrains Mono', monospace",
                  marginBottom: "0.5rem",
                }}
              >
                polished in your voice
              </div>
              <div
                style={{
                  fontSize: "0.9rem",
                  lineHeight: 1.6,
                  color: "#e0e0e0",
                  whiteSpace: "pre-wrap",
                }}
              >
                {polished}
              </div>
              <button
                onClick={() => {
                  onTranscript(polished);
                  setRawTranscript(null);
                  setPolished(null);
                }}
                style={{
                  marginTop: "0.5rem",
                  background: "transparent",
                  border: "1px solid #6bbd7b",
                  color: "#6bbd7b",
                  padding: "0.2rem 0.6rem",
                  fontSize: "0.75rem",
                  cursor: "pointer",
                  borderRadius: "3px",
                }}
              >
                Insert polished
              </button>
            </div>
          )}

          {/* Raw transcript */}
          <div
            style={{
              background: "#111",
              borderLeft: "3px solid #555",
              padding: "1rem",
              borderRadius: "0 4px 4px 0",
            }}
          >
            <div
              style={{
                fontSize: "0.7rem",
                color: "#555",
                fontFamily: "'JetBrains Mono', monospace",
                marginBottom: "0.5rem",
              }}
            >
              raw transcript
            </div>
            <div
              style={{
                fontSize: "0.85rem",
                lineHeight: 1.6,
                color: "#808080",
                whiteSpace: "pre-wrap",
              }}
            >
              {rawTranscript}
            </div>
            <button
              onClick={() => {
                onTranscript(rawTranscript);
                setRawTranscript(null);
                setPolished(null);
              }}
              style={{
                marginTop: "0.5rem",
                background: "transparent",
                border: "1px solid #333",
                color: "#808080",
                padding: "0.2rem 0.6rem",
                fontSize: "0.75rem",
                cursor: "pointer",
                borderRadius: "3px",
              }}
            >
              Insert raw
            </button>
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}
