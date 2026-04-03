import { useState, useRef, useEffect } from "preact/hooks";

// Uses the browser's built-in Web Speech API for speech-to-text.
// No API key needed. Works in Chrome, Edge. Safari support is limited.

export function VoiceButton({ onTranscript, onListeningChange, disabled }) {
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef(null);

  useEffect(() => {
    return () => {
      // Cleanup on unmount
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
    };
  }, []);

  const isSupported = () => {
    return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  };

  const startListening = () => {
    if (!isSupported()) {
      alert(
        "Speech recognition isn't supported in this browser. Try Chrome or Edge."
      );
      return;
    }

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();

    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      if (transcript.trim()) {
        onTranscript(transcript.trim());
      }
    };

    recognition.onend = () => {
      setListening(false);
      onListeningChange?.(false);
    };

    recognition.onerror = (event) => {
      if (event.error !== "aborted") {
        console.error("Speech recognition error:", event.error);
      }
      setListening(false);
      onListeningChange?.(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
    onListeningChange?.(true);
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    setListening(false);
    onListeningChange?.(false);
  };

  const toggle = () => {
    if (listening) {
      stopListening();
    } else {
      startListening();
    }
  };

  return (
    <button
      class={`voice-btn ${listening ? "recording" : ""}`}
      onClick={toggle}
      disabled={disabled}
      aria-label={listening ? "Stop listening" : "Start listening"}
    >
      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
        {listening ? (
          <rect x="6" y="6" width="12" height="12" rx="2" />
        ) : (
          <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1 3.93c-3.94-.49-7-3.85-7-7.93h2c0 3.31 2.69 6 6 6s6-2.69 6-6h2c0 4.08-3.06 7.44-7 7.93V20h4v2H8v-2h4v-2.07z" />
        )}
      </svg>
    </button>
  );
}
