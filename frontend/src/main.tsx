import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { registerSW } from "virtual:pwa-register";
import App from "./App";
import { queryClient } from "./lib/queryClient";
import { useAuth } from "./stores/auth";
import "./index.css";

// autoUpdate only swaps versions when the service worker notices a new
// build, which normally happens on navigation. Long-lived tabs went stale
// for hours after deploys — poll every 5 minutes so updates land on open
// tabs too.
registerSW({
  immediate: true,
  onRegisteredSW(_swUrl, registration) {
    if (registration) {
      setInterval(() => registration.update(), 5 * 60 * 1000);
    }
  },
});

useAuth.getState().restore();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
);
