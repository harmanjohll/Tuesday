import { render } from "preact";
import { App } from "./app.jsx";
import "./style.css";

// Register service worker for PWA
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

render(<App />, document.getElementById("app"));
