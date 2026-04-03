import { useState, useRef, useEffect } from "preact/hooks";

// Always-on voice input using Web Speech API.
// Mic is ON by default. Restarts after each utterance.
// Mute button toggles mic. Pauses during TTS playback.

export function VoiceInput({ onTranscript, onListeningChange, paused }) {
  const [muted, setMuted] = useState(false);
  const [active, setActive] = useState(false);

  // Use refs for values that callbacks need (avoids stale closures)
  const mutedRef = useRef(false);
  const pausedRef = useRef(false);
  const recognitionRef = useRef(null);
  const restartTimerRef = useRef(null);
  const onTranscriptRef = useRef(onTranscript);
  const onListeningChangeRef = useRef(onListeningChange);

  // Keep refs in sync
  onTranscriptRef.current = onTranscript;
  onListeningChangeRef.current = onListeningChange;
  mutedRef.current = muted;
  pausedRef.current = paused;

  const isSupported =
    typeof window !== "undefined" &&
    !!(window.SpeechRecognition || window.webkitSpeechRecognition);

  const stopListening = () => {
    clearTimeout(restartTimerRef.current);
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch (e) {}
      recognitionRef.current = null;
    }
    setActive(false);
    onListeningChangeRef.current?.(false);
  };

  const startListening = () => {
    if (!isSupported || mutedRef.current || pausedRef.current) return;
    if (recognitionRef.current) return; // already running

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SR();
    rec.lang = "en-US";
    rec.interimResults = false;
    rec.continuous = false; // single utterance, then restart — more reliable than continuous
    rec.maxAlternatives = 1;

    rec.onresult = (event) => {
      const transcript = event.results[0]?.[0]?.transcript?.trim();
      if (transcript) {
        onTranscriptRef.current(transcript);
      }
    };

    rec.onstart = () => {
      setActive(true);
      onListeningChangeRef.current?.(true);
    };

    rec.onend = () => {
      setActive(false);
      onListeningChangeRef.current?.(false);
      recognitionRef.current = null;

      // Auto-restart unless muted or paused
      if (!mutedRef.current && !pausedRef.current) {
        restartTimerRef.current = setTimeout(startListening, 200);
      }
    };

    rec.onerror = (event) => {
      recognitionRef.current = null;
      setActive(false);
      onListeningChangeRef.current?.(false);

      // no-speech and aborted are normal — just restart
      if (event.error === "no-speech" || event.error === "aborted") {
        if (!mutedRef.current && !pausedRef.current) {
          restartTimerRef.current = setTimeout(startListening, 300);
        }
        return;
      }

      console.warn("Speech recognition error:", event.error);

      // Retry on recoverable errors
      if (event.error !== "not-allowed" && !mutedRef.current && !pausedRef.current) {
        restartTimerRef.current = setTimeout(startListening, 1000);
      }
    };

    recognitionRef.current = rec;
    try {
      rec.start();
    } catch (e) {
      recognitionRef.current = null;
    }
  };

  // React to mute changes
  useEffect(() => {
    if (muted) {
      stopListening();
    } else if (!paused) {
      startListening();
    }
  }, [muted]);

  // React to pause changes (TTS playing)
  useEffect(() => {
    if (paused) {
      stopListening();
    } else if (!muted) {
      // Wait 1.5s after TTS ends to avoid mic picking up speaker output
      restartTimerRef.current = setTimeout(startListening, 1500);
    }
  }, [paused]);

  // Initial start + cleanup
  useEffect(() => {
    if (!muted && !paused) {
      startListening();
    }
    return () => {
      clearTimeout(restartTimerRef.current);
      stopListening();
    };
  }, []);

  if (!isSupported) return null;

  return (
    <button
      class={`voice-btn ${active ? "listening" : ""} ${muted ? "muted" : ""}`}
      onClick={() => setMuted((m) => !m)}
      aria-label={muted ? "Unmute microphone" : "Mute microphone"}
    >
      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
        {muted ? (
          <path d="M19 11h-1.7c0 .74-.16 1.43-.43 2.05l1.23 1.23c.56-.98.9-2.09.9-3.28zM14.98 11.17c0-.06.02-.11.02-.17V5c0-1.66-1.34-3-3-3S9 3.34 9 5v.18l5.98 5.99zM4.27 3L3 4.27l6.01 6.01V11c0 1.66 1.33 3 2.99 3 .22 0 .44-.03.65-.08l1.66 1.66c-.71.33-1.5.52-2.31.52-3.03 0-5.7-2.52-5.7-5.6H5c0 3.41 2.72 6.23 6 6.72V20h2v-2.28c.89-.13 1.72-.44 2.46-.89L19.73 21 21 19.73 4.27 3z" />
        ) : (
          <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1 3.93c-3.94-.49-7-3.85-7-7.93h2c0 3.31 2.69 6 6 6s6-2.69 6-6h2c0 4.08-3.06 7.44-7 7.93V20h4v2H8v-2h4v-2.07z" />
        )}
      </svg>
    </button>
  );
}
