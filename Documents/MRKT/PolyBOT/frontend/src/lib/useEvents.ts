"use client";

import { useEffect, useState } from "react";
import { API_URL } from "./api";

export interface BotEvent {
  type: string;
  payload: Record<string, unknown>;
  receivedAt: number;
}

/** Subscribe to the backend WebSocket event stream (plan D.7). */
export function useEvents(max = 50): BotEvent[] {
  const [events, setEvents] = useState<BotEvent[]>([]);

  useEffect(() => {
    const wsUrl = API_URL.replace(/^http/, "ws") + "/ws";
    let ws: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout>;

    const connect = () => {
      ws = new WebSocket(wsUrl);
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          setEvents((prev) =>
            [{ ...data, receivedAt: Date.now() }, ...prev].slice(0, max),
          );
        } catch {
          /* ignore malformed */
        }
      };
      ws.onclose = () => {
        retry = setTimeout(connect, 2000);
      };
    };

    connect();
    return () => {
      clearTimeout(retry);
      ws?.close();
    };
  }, [max]);

  return events;
}
