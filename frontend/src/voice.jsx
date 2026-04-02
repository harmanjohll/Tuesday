import { useState, useRef } from "preact/hooks";

export function VoiceButton({ onTranscript, disabled }) {
  const [recording, setRecording] = useState(false);
  const mediaRecorder = useRef(null);
  const chunks = useRef([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunks.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks.current, { type: "audio/webm" });
        await transcribe(blob);
      };

      mediaRecorder.current = recorder;
      recorder.start();
      setRecording(true);
    } catch (err) {
      console.error("Microphone access denied:", err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorder.current?.state === "recording") {
      mediaRecorder.current.stop();
    }
    setRecording(false);
  };

  const transcribe = async (blob) => {
    const form = new FormData();
    form.append("audio", blob, "recording.webm");

    try {
      const res = await fetch("/voice/transcribe", { method: "POST", body: form });
      const data = await res.json();
      if (data.transcript) {
        onTranscript(data.transcript);
      }
    } catch (err) {
      console.error("Transcription failed:", err);
    }
  };

  const toggle = () => {
    if (recording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  return (
    <button
      class={`voice-btn ${recording ? "recording" : ""}`}
      onClick={toggle}
      disabled={disabled}
      aria-label={recording ? "Stop recording" : "Start recording"}
    >
      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
        {recording ? (
          <rect x="6" y="6" width="12" height="12" rx="2" />
        ) : (
          <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1 3.93c-3.94-.49-7-3.85-7-7.93h2c0 3.31 2.69 6 6 6s6-2.69 6-6h2c0 4.08-3.06 7.44-7 7.93V20h4v2H8v-2h4v-2.07z" />
        )}
      </svg>
    </button>
  );
}
