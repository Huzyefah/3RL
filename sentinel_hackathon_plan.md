add

# Project plan: "Sentinel", a pre-incident AIOps agent

**Problem statement:** PS-02 Proactive Anomaly Detection & Issue Prevention Agent
**Event:** atomcamp National AI Hackathon Finale, NIC Islamabad, October 20, 2026

## The pitch in one line

Sentinel predicts when a metric will breach its limit, not just when it already has. A small team of agents then argues about whether the alert is real, links it to past incidents, and opens a ticket with a root-cause guess before any user notices.

## Ideas built around the three scoring metrics

| Criterion                                    | Ideas                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Detection lead time**                      | 1. **Time-to-breach forecasting.** Fit a short-horizon trend model (Holt or EWMA slope) to each metric and alert when the _forecast_ will cross its threshold within N minutes. The alert says something like "latency will breach in ~12 min." 2. **Precursor mining.** In the CSV, find which metrics move first before rows flagged as incidents (for example, auth failures rise before error rate). Weight those leading signals higher.                                                           |
| **False positive rate**                      | 3. **Skeptic agent.** Before any action fires, an LLM agent tries to disprove the alert (normal daily pattern, a single noisy metric, or a known deploy window). The alert only escalates if the Skeptic can't explain it away. 4. **Multi-signal consensus.** Use a correlated anomaly score across several metrics instead of a single threshold. 5. **Feedback loop.** When on-call marks an alert "not useful," the system raises that metric's sensitivity threshold live.                         |
| **Root-cause summary quality**               | 6. **Evidence-cited RCA.** Each hypothesis carries a confidence score and points to specific metric windows and log lines. Unsupported claims aren't allowed. 7. **Historian agent.** Vector search over past incidents produces lines like "This looks 82% like INC-0042, which was fixed by restarting the auth pool." 8. **Pre-mortem ticket.** The ticket includes the hypothesis, blast radius (estimated users affected), a suggested runbook, and a "what happens if we ignore this" projection. |
| **Live scorecard (the main differentiator)** | 9. A dashboard panel that **scores the system against the dataset's incident flags in real time**: average lead time, precision/recall, and false positive rate with the Skeptic on vs. off. Judges see your evaluation metrics proven live.                                                                                                                                                                                                                                                            |
| **Safe autonomy**                            | 10. **Blast-radius policy.** Low-risk actions (alerts, tickets) run on their own. High-risk actions (scaling, restarts) need one-click approval from a Google Chat card. This matters for the "Agentic AI" and "Technical execution" scores.                                                                                                                                                                                                                                                            |

## Architecture (GCP)

```
Telemetry replayer / live demo app ──► Pub/Sub ──► Detector (Cloud Run)
                                                  stats: z-score, EWMA, forecast
                                                        │ anomaly event
                                                        ▼
                                   Orchestrator (Google ADK or LangGraph)
     ┌──────────────┬──────────────┬──────────────┬──────────────┐
  Investigator    Historian      Skeptic        Responder      Narrator
  (BigQuery,      (vector search (challenges    (tickets,      (Gemini or
  log queries)    past incidents) the alert)    Chat, scaling) GPT summary)
                                                        │
                        BigQuery (telemetry, incidents, agent decisions log)
                                                        │
                        Dashboard (Cloud Run): live feed, agent trace, scorecard
```

- **Ingestion:** a replayer streams the CSV rows into Pub/Sub at accelerated speed. This is real processing of real data, so tell the judges plainly that it is a replay to stay well clear of the "faking the demo" rule.
- **"Break it live" button:** a tiny demo service on Cloud Run with a fault-injection endpoint (latency or error spike). You press it on stage and Sentinel catches it live. This is the demo moment that wins.
- **LLMs:** Gemini on Vertex AI for summaries (it's the suggested stack), with the OpenAI key as a fallback.
- **Ticket sink:** a BigQuery "tickets" table shown in the UI, plus a Google Chat webhook for the on-call alert.

## Timeline

This assumes about 8 hours of build time; scale it to the actual window.

| Time      | Person A (backend/agents)                                          | Person B (data/UI/deploy)                                                           |
| --------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| 0:00–0:30 | Repo, GCP project, Pub/Sub, env vars                               | Inspect `ps02_system_telemetry.csv`: columns, incident flags, precursor patterns    |
| 0:30–2:00 | Detector service: rolling stats and time-to-breach forecast        | Replayer to Pub/Sub, BigQuery tables, seed past-incident store                      |
| 2:00–4:00 | Agent graph: Investigator, Skeptic, Historian, Responder, Narrator | Dashboard skeleton: live feed, alert cards, agent trace view                        |
| 4:00–5:00 | Actions: Chat webhook, tickets, approval flow                      | Scorecard: lead time, precision/recall, false positive rate with Skeptic on vs. off |
| 5:00–6:00 | Fault-injection demo app and end-to-end test                       | Deploy everything to Cloud Run, then test on the live URL                           |
| 6:00–7:00 | **Feature freeze.** Fix bugs, tune thresholds                      | Slides, architecture diagram, README, backup screen recording                       |
| 7:00+     | Rehearse the 7-minute pitch twice, then submit                     |                                                                                     |

Commit often. Judges may check the commit history.

**Cut order if you run behind:** feedback loop first, then approval flow, then the fault-injection app. Never cut the Skeptic or the scorecard; they map directly to the judging criteria.

## 7-minute pitch

1. **(1 min) Problem:** "Support teams find out about outages from angry users." Open with one number from the dataset, such as "the signals were visible X minutes early."
2. **(1 min) Solution:** walk through the five agents and the "predict, debate, act" flow on the diagram.
3. **(3 min) Live demo:** start the replay, watch an alert get predicted, the Skeptic kill a false positive, and the Historian match a past incident. Then press "break it live," and the ticket and Chat alert arrive. End on the scorecard.
4. **(1 min) Tech:** Pub/Sub, Cloud Run, BigQuery, Vertex Gemini, ADK.
5. **(1 min) Scale:** connectors for Cloud Monitoring, Datadog, and Prometheus, plus a multi-tenant SaaS for mid-size companies that pays per monitored service. Self-tuning thresholds mean no setup work for customers.

**Q&A prep:** be ready to explain how lead time is measured, why the Skeptic doesn't suppress real incidents (show its recall), and how costs behave at scale (agents only run on anomalies, not on every data point).

## Risks

- **Venue internet:** have a backup recording ready, labeled as a recording.
- **LLM latency during the demo:** cache nothing fake, but run Narrator calls asynchronously so the UI never freezes.
- **Unexpected dataset shape:** finish the 30-minute data inspection before you lock in the detector design.

## Submission checklist

- [ ] Live deployed link on GCP
- [ ] GitHub repository link with a short README
- [ ] Presentation slides (PDF or link)
- [ ] Architecture diagram showing the agents and how they interact
- [ ] Team name and all members' names
