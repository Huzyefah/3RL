"use client";

import { createContext, createElement, useContext, useEffect, useReducer, useState, type ReactNode } from "react";
import type { ActionView, BankStatus, IncidentSummary, Kpis, SentinelEvent, ServiceStatus, TraceStep } from "./types";

export type Connection = "connecting" | "open" | "reconnecting";

export interface StreamState {
  connection: Connection;
  synced: boolean; // a snapshot has been received
  services: Record<string, ServiceStatus>;
  serviceOrder: string[];
  banks: Record<string, BankStatus>;
  incidents: Record<string, IncidentSummary>;
  kpis: Kpis | null;
  traces: Record<string, TraceStep[]>; // incident_id → steps sorted by step
  actions: Record<string, ActionView>;
}

export const initialState: StreamState = {
  connection: "connecting",
  synced: false,
  services: {},
  serviceOrder: [],
  banks: {},
  incidents: {},
  kpis: null,
  traces: {},
  actions: {},
};

export type StreamAction = SentinelEvent | { type: "connection"; connection: Connection };

const byKey = <T,>(items: T[], key: (t: T) => string) => Object.fromEntries(items.map((i) => [key(i), i]));

function stripType<T extends { type: string }>(e: T): Omit<T, "type"> {
  const { type: _type, ...rest } = e;
  void _type;
  return rest;
}

/** Inserts or replaces a trace step (dedupe by step number), keeping the list ordered. */
export function mergeSteps(existing: TraceStep[] | undefined, incoming: TraceStep[]): TraceStep[] {
  const map = new Map((existing ?? []).map((s) => [s.step, s]));
  for (const s of incoming) map.set(s.step, s);
  return [...map.values()].sort((a, b) => a.step - b.step);
}

/** Pure reducer over SSE events. Unknown event types are ignored so the backend can add new ones safely. */
export function reduce(state: StreamState, event: StreamAction): StreamState {
  switch (event.type) {
    case "connection":
      return state.connection === event.connection ? state : { ...state, connection: event.connection };
    case "snapshot": {
      // Full resync (also sent after every reconnect). Traces are per-incident detail and survive resyncs.
      const actions = event.actions ? byKey(event.actions, (a) => a.id) : state.actions;
      return {
        ...state,
        synced: true,
        services: byKey(event.services, (s) => s.service),
        serviceOrder: event.services.map((s) => s.service),
        banks: byKey(event.banks, (b) => b.bank),
        incidents: byKey(event.incidents, (i) => i.id),
        kpis: event.kpis,
        actions,
      };
    }
    case "metric": {
      const svc = stripType(event) as ServiceStatus;
      const known = svc.service in state.services;
      return {
        ...state,
        services: { ...state.services, [svc.service]: svc },
        serviceOrder: known ? state.serviceOrder : [...state.serviceOrder, svc.service],
      };
    }
    case "bank": {
      const bank = stripType(event) as BankStatus;
      return { ...state, banks: { ...state.banks, [bank.bank]: bank } };
    }
    case "incident":
      return { ...state, incidents: { ...state.incidents, [event.incident.id]: event.incident } };
    case "trace": {
      const id = event.step.incident_id;
      return { ...state, traces: { ...state.traces, [id]: mergeSteps(state.traces[id], [event.step]) } };
    }
    case "action":
      return { ...state, actions: { ...state.actions, [event.action.id]: event.action } };
    case "kpis":
      return { ...state, kpis: event.kpis };
    default:
      return state;
  }
}

/**
 * Subscribes to the same-origin SSE stream. EventSource reconnects on its own and resends Last-Event-ID,
 * which the proxy forwards upstream; the server answers every (re)connect with a fresh snapshot.
 */
export function useSentinelStream(url = "/api/events"): StreamState {
  const [state, dispatch] = useReducer(reduce, initialState);
  const [generation, setGeneration] = useState(0);
  useEffect(() => {
    const es = new EventSource(url);
    es.onopen = () => dispatch({ type: "connection", connection: "open" });
    es.onerror = () => dispatch({ type: "connection", connection: "reconnecting" });
    es.onmessage = (msg) => {
      try {
        dispatch(JSON.parse(msg.data) as SentinelEvent);
      } catch {
        // ignore malformed frames
      }
    };
    // The browser retries transient drops itself, but gives up (CLOSED) on a non-200 such as a proxy 502.
    const watchdog = setInterval(() => {
      if (es.readyState === EventSource.CLOSED) setGeneration((g) => g + 1);
    }, 3000);
    return () => {
      clearInterval(watchdog);
      es.close();
    };
  }, [url, generation]);
  return state;
}

const StreamContext = createContext<StreamState>(initialState);

/** One EventSource for the whole app, shared by the header and every screen. */
export function SentinelStreamProvider({ children }: { children: ReactNode }) {
  const state = useSentinelStream();
  return createElement(StreamContext.Provider, { value: state }, children);
}

export const useStream = () => useContext(StreamContext);
