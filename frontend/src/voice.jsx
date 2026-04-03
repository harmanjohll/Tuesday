import { useState, useRef, useEffect, useCallback } from "preact/hooks";

// Always-on voice input using Web Speech API in continuous mode.
// Mic stays hot by default. Automatically restarts after each utterance.
// Mute button toggles mic on/off. Default: ON.

export function VoiceInput({ onTranscript, onListeningChange, paused }) {
  const [muted, setMuted] = useState(false);
  const [active, setActive] = useState(false);
  const recognitionRef = useRef(null);
  const shouldListenRef = useRef(true);
  const restartTimerRef = useRef(null);

  const isSupported = () =>
    !!(window.SpeechRecognition || window.webkitSpeechRecognition);

  const startListening = useCallback(() => {
    if (!isSupported() || muted || recognitionRef.current) return;

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();

    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.continuous = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      // Get the latest result
      const last = event.results[event.results.length - 1];
      if (last.isFinal) {
        const transcript = last[0].transcript.trim();
        if (transcript) {
          onTranscript(transcript);
        }
      }
    };

    recognition.onstart = () => {
      setActive(true);
      onListeningChange?.(true);
    };

    recognition.onend = () => {
      setActive(false);
      onListeningChange?.(false);
      recognitionRef.current = null;

      // Auto-restart if not muted and not paused
      if (shouldListenRef.current && !muted) {
        restartTimerRef.current = setTimeout(() => {
          startListening();
        }, 300);
      }
    };

    recognition.onerror = (event) => {
      if (event.error === "aborted" || event.error === "no-speech") {
        // Normal — just restart
        return;
      }
      console.warn("Speech recognition error:", event.error);
      recognitionRef.current = null;
      setActive(false);
      onListeningChange?.(false);

      // Retry after errors (except not-allowed)
      if (event.error !== "not-allowed" && shouldListenRef.current && !muted) {
        restartTimerRef.current = setTimeout(() => {
          startListening();
        }, 1000);
      }
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch (e) {
      // Already started or other issue
      recognitionRef.current = null;
    }
  }, [muted, onTranscript, onListeningChange]);

  const stopListening = useCallback(() => {
    clearTimeout(restartTimerRef.current);
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch (e) {}
      recognitionRef.current = null;
    }
    setActive(false);
    onListeningChange?.(false);
  }, [onListeningChange]);

  // Start/stop based on mute state
  useEffect(() => {
    shouldListenRef.current = !muted;
    if (muted) {
      stopListening();
    } else {
      startListening();
    }
    return () => {
      shouldListenRef.current = false;
      stopListening();
    };
  }, [muted, startListening, stopListening]);

  // Pause/resume when Tuesday is thinking (avoid picking up TTS audio)
  useEffect(() => {
    if (paused) {
      stopListening();
    } else if (!muted) {
      // Small delay before restarting to avoid picking up end of TTS
      restartTimerRef.current = setTimeout(() => {
        startListening();
      }, 500);
    }
  }, [paused, muted, startListening, stopListening]);

  const toggleMute = () => {
    setMuted((m) => !m);
  };

  if (!isSupported()) {
    return null; // Don't show anything if not supported
  }

  return (
    <button
      class={`voice-btn ${active ? "listening" : ""} ${muted ? "muted" : ""}`}
      onClick={toggleMute}
      aria-label={muted ? "Unmute microphone" : "Mute microphone"}
    >
      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
        {muted ? (
          // Muted mic icon (mic with slash)
          <g>
            <path d="M19 11h-1.7c0 .74-.16 1.43-.43 2.05l1.23 1.23c.56-.98.9-2.09.9-3.28zM14.98 11.17c0-.06.02-.11.02-.17V5c0-1.66-1.34-3-3-3S9 3.34 9 5v.18l5.98 5.99zM4.27 3L3 4.27l6.01 6.01V11c0 1.66 1.33 3 2.99 3 .22 0 .44-.03.65-.08l1.66 1.66c-.71.33-1.5.52-2.31.52-3.03 0-5.7-2.52-5.7-5.6H5c0 3.41 2.72 6.23 6 6.72V20h2v-2.28c.89-.13 1.72-.44 2.46-.89L19.73 21 21 19.73 4.27 3z" />
          </g>
        ) : (
          // Active mic icon
          <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1 3.93c-3.94-.49-7-3.85-7-7.93h2c0 3.31 2.69 6 6 6s6-2.69 6-6h2c0 4.08-3.06 7.44-7 7.93V20h4v2H8v-2h4v-2.07z" />
        )}
      </svg>
    </button>
  );
}
