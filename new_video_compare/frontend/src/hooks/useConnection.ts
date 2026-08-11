import { useState, useEffect } from "react";

export function useConnection() {
  const [backendStatus, setBackendStatus] = useState<"connected" | "disconnected" | "checking">("checking");
  const [wsStatus, setWsStatus] = useState<"connected" | "disconnected" | "checking">("checking");

  useEffect(() => {
    checkBackendStatus();
    setupWebSocket();
  }, []);

  const checkBackendStatus = async () => {
    try {
      const response = await fetch("/health");
      if (response.ok) {
        setBackendStatus("connected");
      } else {
        setBackendStatus("disconnected");
      }
    } catch (error) {
      setBackendStatus("disconnected");
    }
  };

  const setupWebSocket = () => {
    try {
      const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      let wsHost = window.location.host;
      if (window.location.port === "3000" || window.location.port === "3001") {
        const backendPort = parseInt(window.location.port) + 5001;
        wsHost = `127.0.0.1:${backendPort}`;
      }
      const ws = new WebSocket(`${wsProtocol}//${wsHost}/ws/connect`);

      ws.onopen = () => {
        setWsStatus("connected");
        console.log("WebSocket connected");
      };

      ws.onclose = () => {
        setWsStatus("disconnected");
        console.log("WebSocket disconnected");
      };

      ws.onerror = () => {
        setWsStatus("disconnected");
      };
    } catch (error) {
      setWsStatus("disconnected");
    }
  };

  return { backendStatus, wsStatus };
}
