// Mock sentinel-api for UI development and @fake E2E (no deps). Fictional data only; PKR figures are estimates.
//   node mock-api/server.mjs            → http://localhost:8090
//   GET  /healthz                        → {"status":"ok","service":"sentinel-api","env":"mock","csv_rows":500}
//   GET  /events                         → SSE (event: message, id: <seq>, data: <json>); snapshot first, 15 s heartbeat
//   GET  /incidents, /incidents/{id}     → IncidentSummary[] / {incident, rca, trace, actions}
//   POST /mock/reset                     → restarts the scripted BANK_C scenario (tests call this first)
import http from "node:http";

const PORT = Number(process.env.MOCK_PORT ?? 8090);
const INCIDENT_AT_MS = Number(process.env.MOCK_INCIDENT_AT_MS ?? 3000); // incident opens this long after (re)start
const STEP_EVERY_MS = 550; // 11 trace steps ≈ 6 s
const ETA_MIN = 11;
const INC_ID = "INC-2026-1020-004";
const ACTION_ID = "act-reroute-bank-c-01";

const SERVICES = [
  ["PaymentGateway", "PaymentGateway (wallet, IBFT, Raast, card)", "Payments", 0, 0.52, "latency_p99"],
  ["AuthService", "AuthService (login, sessions, device)", "Identity & Security", 0, 0.41, "connection_pool"],
  ["NotificationHub", "OTP & NotificationHub", "Digital Channels", 0, 0.33, "error_rate"],
  ["DataPipeline", "LedgerSync / Settlement (cut-off 16:00 PKT)", "Core Banking Ops", 0, 0.58, "queue_depth"],
  ["UserProfileService", "CustomerProfile / KYC", "Onboarding", 1, 0.29, "cpu_usage"],
  ["SearchAPI", "TransactionSearchAPI", "Digital Channels", 1, 0.37, "latency_p99"],
  ["AnalyticsDashboard", "FraudRiskAnalytics", "Risk & Compliance", 1, 0.46, "memory_usage"],
  ["ReportGenerator", "RegulatoryReporting", "Risk & Compliance", 2, 0.22, "disk_io"],
];
const BANKS = { BANK_A: 0.9935, BANK_B: 0.9921, BANK_C: 0.9902, BANK_D: 0.9944, BANK_E: 0.9917 };
const FLOOR = 0.97;

const band = (u) => (u >= 0.95 ? "CRITICAL" : u >= 0.75 ? "WARNING" : "NORMAL");
const round = (x, d = 4) => Number(x.toFixed(d));
const iso = (ms) => new Date(ms).toISOString();

let t0 = Date.now();
let seq = 0;
let s; // scenario state
const clients = new Set();

function freshState() {
  return {
    services: Object.fromEntries(
      SERVICES.map(([service, display, team, tier, u, metric]) => [service, { service, display, team, tier, u, band: band(u), metric }]),
    ),
    banks: Object.fromEntries(
      Object.entries(BANKS).map(([bank, sr]) => {
        const u = round((1 - sr) / (1 - FLOOR), 3);
        return [bank, { bank, success_rate: sr, u, band: band(u), rail: "IBFT" }];
      }),
    ),
    incident: null,
    trace: [],
    actions: {},
    kpis: { preempted_today: 3, median_lead_min: 14, fp_avoided: 5, open_p1p2: 0, autonomy_mode: "shadow" },
    nextStep: 0,
  };
}
s = freshState();

// ── SSE plumbing ──
function frame(data) {
  seq += 1;
  return `id: ${seq}\nevent: message\ndata: ${JSON.stringify(data)}\n\n`;
}
function broadcast(data) {
  const f = frame(data);
  for (const res of clients) res.write(f);
}
function snapshot() {
  return {
    type: "snapshot",
    services: Object.values(s.services),
    banks: Object.values(s.banks),
    incidents: s.incident ? [s.incident] : [],
    kpis: s.kpis,
    actions: Object.values(s.actions),
  };
}

// ── Scripted BANK_C scenario (FINAL_PLAN §14 beat 3:30) ──
function steps(openedAt) {
  const at = (k) => iso(openedAt + 400 + k * STEP_EVERY_MS);
  const st = (k, agent, kind, summary, extra = {}) => ({
    incident_id: INC_ID,
    step: k + 1,
    ts: at(k),
    agent,
    kind,
    tool: null,
    args: {},
    summary,
    evidence_id: null,
    tokens: 0,
    latency_ms: 0,
    ...extra,
  });
  return [
    st(0, "commander", "goal", "Goal: prevent BANK_C payment failures before the forecast SLO breach (~11 min).", { tokens: 412, latency_ms: 840 }),
    st(1, "commander", "plan", "Plan v1: confirm the BANK_C segment shift, forecast the breach, check recent changes on PaymentGateway.", {
      args: { version: 1, steps: ["get_segment_breakdown", "get_forecast", "get_change_events"] },
      tokens: 655,
      latency_ms: 1210,
    }),
    st(2, "investigator", "tool_call", "BANK_C success 98.0% vs 99.3% peer mean (binomial p < 0.001); other banks flat.", {
      tool: "get_segment_breakdown", args: { service: "PaymentGateway", segment: "bank", window_min: 30 }, evidence_id: "segment:3fa1c2d9", latency_ms: 96,
    }),
    st(3, "investigator", "tool_call", "Holt forecast: BANK_C success crosses the 97% floor in ~11 min at the current slope.", {
      tool: "get_forecast", args: { series: "payment_success_rate", segment: "bank=BANK_C" }, evidence_id: "forecast:7a1c0b33", latency_ms: 74,
    }),
    st(4, "skeptic", "challenge", "DISPUTED: salary-day surge is on the calendar and platform success is 98.6%. A load ramp would hit all banks; show BANK_C-specific failure codes.", {
      tool: "get_calendar", args: { verdict: "DISPUTED", date: "2026-10-20" }, evidence_id: "calendar:5d20e8a1", tokens: 538, latency_ms: 1630,
    }),
    st(5, "commander", "plan", "Plan v2: Skeptic disputed. Add BANK_C issuer response codes from logs and compare peer banks under the same surge.", {
      args: { version: 2, reason: "skeptic_disputed", steps: ["get_logs", "count_corroborating_signals"] }, tokens: 702, latency_ms: 1380,
    }),
    st(6, "investigator", "tool_call", "Log template 'RC=91 issuer unavailable' surging 7.4x baseline on BANK_C only for the last 12 min; peers at baseline.", {
      tool: "get_logs", args: { service: "PaymentGateway", filter: "bank=BANK_C", redacted: true }, evidence_id: "log:91ab02ee", latency_ms: 118,
    }),
    st(7, "skeptic", "challenge", "CONFIRMED: failure is bank-specific under a shared surge; the calendar does not explain RC=91.", {
      tool: "count_corroborating_signals", args: { verdict: "CONFIRMED", confidence: 0.81 }, evidence_id: "segment:3fa1c2d9", tokens: 489, latency_ms: 1270,
    }),
    st(8, "commander", "tool_call", "recall_similar: INC-0007 (84% similar), fixed by rerouting BANK_C IBFT via Raast for 40 min.", {
      tool: "recall_similar", args: { k: 3, cutoff: 0.7 }, evidence_id: "memory:c02d7e15", latency_ms: 41,
    }),
    st(9, "guard", "guard", "reroute_bank BANK_C → RAAST allowed as HITL: target rail healthy (u 0.31 over 5 min), idempotent, approval expires in 10 min.", {
      tool: "request_action", args: { verdict: "HITL", action: "reroute_bank", bank: "BANK_C", rail: "RAAST" }, evidence_id: "policy:aa41f9c0", latency_ms: 12,
    }),
    st(10, "commander", "verify", "Verification armed: after execution, BANK_C success must recover ≥ 50% of the gap within 60 s, or the guard rolls back and pages.", {
      args: { check_after_s: 60 }, tokens: 233, latency_ms: 520,
    }),
  ];
}

function incidentSummary(openedAt, status) {
  return {
    id: INC_ID,
    root_service: "PaymentGateway",
    segment_key: "bank=BANK_C",
    severity: "P1",
    headline: "BANK_C IBFT timeouts will breach SLO in ~11 min",
    status,
    eta_minutes: ETA_MIN,
    eta_at: iso(openedAt + ETA_MIN * 60_000),
    risk: 0.87,
    opened_at: iso(openedAt),
    pkr_at_risk_per_min: 1_250_000,
  };
}

function rca() {
  return {
    incident_id: INC_ID,
    goal: "Prevent BANK_C payment failures before the forecast breach",
    headline: "BANK_C IBFT timeouts will breach SLO in ~11 min",
    severity: "P1",
    root_cause_service: "PaymentGateway",
    affected_segment: "bank=BANK_C",
    eta_minutes: ETA_MIN,
    hypotheses: [
      {
        code: "RC-BANK",
        confidence: 0.82,
        statement: "BANK_C's switch is degrading: RC=91 issuer-unavailable responses rising for the last 12 min while peer banks stay at baseline.",
        evidence_ids: ["segment:3fa1c2d9", "log:91ab02ee", "forecast:7a1c0b33"],
      },
      {
        code: "RC-BENIGN",
        confidence: 0.12,
        statement: "Salary-day load surge (N1). Weakened: the surge is platform-wide but failures are confined to BANK_C.",
        evidence_ids: ["calendar:5d20e8a1"],
      },
      {
        code: "RC-DBPOOL",
        confidence: 0.06,
        statement: "PaymentGateway connection pool pressure. Unlikely: pool utilisation is flat and no deploy in the last 30 min.",
        evidence_ids: ["metric:0be4d7a2"],
      },
    ],
    similar_incidents: [
      { id: "INC-0007", similarity: 0.84, fix: "Rerouted BANK_C IBFT via Raast for 40 min" },
      { id: "INC-0019", similarity: 0.73, fix: "Bank partner restarted issuer switch; no reroute" },
    ],
    runbook_steps: [
      "Confirm Raast rail health (u < 0.75 over 5 min).",
      "Request HITL approval to reroute BANK_C IBFT → Raast.",
      "Notify BANK_C partner desk with the RC=91 evidence.",
      "Verify success recovers within 60 s; revert after the partner confirms a fix.",
    ],
    impact: { customers_affected_est: 4100, pkr_at_risk_per_min: 1_250_000, label: "estimate" },
    actions: [
      { type: "reroute_bank", params: { bank: "BANK_C", rail: "RAAST" }, rationale: "Same fix resolved INC-0007; Raast rail is healthy." },
      { type: "create_ticket", params: { team: "Payments" }, rationale: "Route to the root-cause owner." },
    ],
    summary_technical:
      "PaymentGateway segment bank=BANK_C: success 98.0% and falling, RC=91 issuer-unavailable at 7.4x baseline for 12 min, peers flat. Holt ETA to the 97% floor is ~11 min. Skeptic's salary-day dispute was refuted by plan v2. Recommend HITL reroute of BANK_C IBFT via Raast (INC-0007 precedent).",
    summary_business:
      "One partner bank (BANK_C) is starting to fail transfers. About 4,100 customers and roughly PKR 1.25M per minute are at risk (estimate) within ~11 minutes. Rerouting that bank's transfers through Raast fixed the same problem last time.",
    comms_draft: {
      in_app_banner: "Some transfers to BANK_C may take longer than usual. We are routing them through Raast; no action needed.",
      bank_partner_note: "NovaPay is seeing RC=91 issuer-unavailable responses from your IBFT switch for the last 12 min (7.4x baseline). We are temporarily routing via Raast. Please advise on switch health.",
    },
    if_ignored: "Projected SLO breach in ~11 min; then ~6% of BANK_C IBFT payments fail (estimate).",
    skeptic: {
      verdict: "CONFIRMED",
      confidence: 0.81,
      counter_evidence: ["Salary-day surge on the calendar (refuted: peers unaffected)", "Platform success still 98.6%"],
    },
    plan_versions: 2,
    generated_by: "llm",
    low_confidence: false,
  };
}

function rerouteAction(openedAt) {
  return {
    id: ACTION_ID,
    incident_id: INC_ID,
    type: "reroute_bank",
    params: { bank: "BANK_C", rail: "RAAST" },
    mode: "HITL",
    status: "pending",
    reason: "Raast rail healthy (u 0.31); same fix resolved INC-0007. Idempotent with one-click revert.",
    expires_at: iso(openedAt + 400 + 9 * STEP_EVERY_MS + 10 * 60_000),
  };
}

// ── Ticker: scripted events + jittered metrics ──
let lastMetric = 0;
function tick() {
  const now = Date.now();
  const el = now - t0;
  const openedAt = t0 + INCIDENT_AT_MS;

  if (!s.incident && el >= INCIDENT_AT_MS) {
    s.incident = incidentSummary(openedAt, "candidate");
    s.kpis = { ...s.kpis, open_p1p2: 1 };
    broadcast({ type: "incident", incident: s.incident });
    broadcast({ type: "kpis", kpis: s.kpis });
  }
  if (s.incident) {
    const all = steps(openedAt);
    while (s.nextStep < all.length && Date.parse(all[s.nextStep].ts) <= now) {
      const step = all[s.nextStep++];
      s.trace.push(step);
      broadcast({ type: "trace", step });
      if (step.step === 1) {
        s.incident = { ...s.incident, status: "investigating" };
        broadcast({ type: "incident", incident: s.incident });
      }
      if (step.kind === "guard") {
        const a = rerouteAction(openedAt);
        s.actions[a.id] = a;
        broadcast({ type: "action", action: a });
        s.incident = { ...s.incident, status: "awaiting_approval" };
        broadcast({ type: "incident", incident: s.incident });
      }
    }
  }

  if (now - lastMetric >= 1000) {
    lastMetric = now;
    // BANK_C degrades from ~1 s before the incident onwards; others jitter around baseline.
    const degrade = Math.min(1, Math.max(0, (el - (INCIDENT_AT_MS - 1000)) / 6000));
    for (const [bank, base] of Object.entries(BANKS)) {
      const target = bank === "BANK_C" ? base - degrade * 0.0152 : base;
      const sr = round(target + (Math.random() - 0.5) * 0.0012);
      const u = round((1 - sr) / (1 - FLOOR), 3);
      s.banks[bank] = { ...s.banks[bank], success_rate: sr, u, band: band(u) };
      broadcast({ type: "bank", ...s.banks[bank] });
    }
    for (const [service, , , , base] of SERVICES) {
      if (service !== "PaymentGateway" && Math.random() < 0.6) continue;
      const target = service === "PaymentGateway" ? base + degrade * 0.3 : base;
      const u = round(Math.max(0.05, target + (Math.random() - 0.5) * 0.06), 3);
      s.services[service] = { ...s.services[service], u, band: band(u) };
      broadcast({ type: "metric", ...s.services[service] });
    }
  }
}
setInterval(tick, 100);

// ── HTTP ──
function json(res, status, body) {
  res.writeHead(status, { "content-type": "application/json", "cache-control": "no-store" });
  res.end(JSON.stringify(body));
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url ?? "/", `http://localhost:${PORT}`);
  const path = url.pathname.replace(/\/$/, "") || "/";

  if (req.method === "GET" && path === "/healthz") return json(res, 200, { status: "ok", service: "sentinel-api", env: "mock", csv_rows: 500 });

  if (req.method === "GET" && path === "/events") {
    res.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache, no-transform", connection: "keep-alive", "x-accel-buffering": "no" });
    res.write("retry: 2000\n\n");
    res.write(frame(snapshot()));
    clients.add(res);
    const hb = setInterval(() => res.write(`: heartbeat ${Date.now()}\n\n`), 15_000);
    req.on("close", () => {
      clearInterval(hb);
      clients.delete(res);
    });
    return;
  }

  if (req.method === "GET" && path === "/incidents") return json(res, 200, s.incident ? [s.incident] : []);

  const m = path.match(/^\/incidents\/([^/]+)$/);
  if (req.method === "GET" && m) {
    const id = decodeURIComponent(m[1]);
    if (!s.incident || id !== s.incident.id) return json(res, 404, { error: "not_found", id });
    return json(res, 200, { incident: s.incident, rca: rca(), trace: s.trace, actions: Object.values(s.actions) });
  }

  if (req.method === "POST" && path === "/mock/reset") {
    t0 = Date.now();
    lastMetric = 0;
    s = freshState();
    broadcast(snapshot());
    return json(res, 200, { reset: true, incident_at_ms: INCIDENT_AT_MS });
  }

  json(res, 404, { error: "not_found", path });
});

server.listen(PORT, () => console.log(`mock sentinel-api on http://localhost:${PORT}`));
