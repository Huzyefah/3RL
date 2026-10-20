# Foresight: domain brief for the judge pitch

Written for: you, the presenter, as a 5-minute read before pitching to technical judges.
Data gathered by web search on 2026-10-20. Most cost figures come from vendor-sponsored surveys, so say "survey" or "estimate" on stage, never "fact". Source links are at the bottom.

---

## 1. The 30-second domain model

- **AIOps** = using statistics, ML and LLMs on operational telemetry (metrics, logs, traces) to cut alert noise, find root cause and automate response.
- **Reactive vs proactive.** Almost every tool today alerts *after* a threshold is crossed. Foresight alerts on the *forecast* of a breach.
- **Key terms judges may probe:**
  - **MTTD / MTTA / MTTR:** mean time to detect / acknowledge / resolve.
  - **Lead time:** minutes of warning before the incident. This is our headline metric (blueprint §6.4).
  - **Alert fatigue:** so many false pages that people stop reading them. Our "44% false alarms" number is about this.
  - **TTB (time-to-breach):** Holt trend forecast of when a metric crosses its limit.
  - **SLA / SLO:** the promised ack and resolve times. Our Follow-up agent enforces them.
  - **HITL:** human in the loop. **RCA:** root-cause analysis. **RAG:** retrieval over past incidents.
- **Fintech twist:** a payment or OTP outage is direct lost revenue plus regulatory exposure, and the login surface is under constant credential-stuffing attack. That is why we pair prediction with safe autonomous security containment.

## 2. The cost of failure (evidence-based, with caveats)

| Claim | Number | Source and caveat |
|---|---|---|
| Cost per minute of downtime, cross-industry | **$4,537/min**; avg incident 175 min, about $794K each; 25 high-priority incidents/yr, about $20M/yr per org | PagerDuty 2024, 500 IT leaders at 1,000+ employee firms (US/UK/AU). Vendor survey. |
| Same, large enterprises | **$14,056/min** average, **$23,750/min** for large enterprises | EMA 2024 (400+ IT pros), via BigPanda. Secondary citation. |
| The famous "$5,600/min" | Do **not** cite it | Credited to a 2014 Gartner blog post. EMA calls it an "urban legend", not a benchmark. Using it invites a gotcha. |
| Hourly cost, large firms | **97%** of 1,000+ employee enterprises put one hour above **$100K**; **41%** put it at **$1M to $5M+** | ITIC 2024, self-reported bands, not observed averages. |
| Outage cost distribution | **54-57%** say their last significant outage cost over **$100K**; **1 in 5** over **$1M** | Uptime Institute annual survey (54% in the 2025 report, 57% in the May 2026 release). |
| Global 2000 total | **~$400B/yr**, about $200M per company, about 9% of profits; share price drops **1-9%** after a downtime event, 79 days to recover | Splunk and Oxford Economics, June 2024. |
| Trust | **90%** of IT leaders say outages reduced customer trust | PagerDuty 2024. |
| Frequency trend | Customer-facing incidents up **43%** year on year | PagerDuty 2024. |
| Banking-specific, real event | CrowdStrike (Jul 2024): banking about **$1.15B** direct loss across the Fortune 500, second only to healthcare ($1.94B). Banking and healthcare were 57% of losses on 20% of revenue | Parametrix, **pre-event model**, not final claims. |
| Banking-specific, real event | **TSB 2018** migration outage: about **£330M** (£125M compensation, £49M fraud and ops, £122M extra IT help, £33M waived fees), about **80,000 customers lost** | TechRadar and trade press. £153M was recoverable from the supplier. |

**Useful bridge to our own number:** the blueprint's "USD 4,300/min value at risk" example sits right next to PagerDuty's $4,537/min. Say so: "our impact model lands within about 5% of the published cross-industry average."

**Illustrative ROI (our arithmetic, label it as such):** 25 incidents x 175 min x $4,537 is about $19.8M/yr. If earlier warning avoids or shortens even 20% of that, it is about $4M/yr, against a per-service SaaS fee. One avoided P1 pays for years.

## 3. The alert-noise problem (supports the "44% false alarms" line)

- Microsoft/Omdia State of the SOC 2026: **46%** of alerts are false positives; **42%** go uninvestigated.
- SANS 2025 Detection and Response survey: **73%** name false positives their top detection challenge.
- Vectra 2026: about **2,992 alerts/day** per organisation, **63%** unaddressed.
- Caveats: these are security-SOC figures from vendors. I found **no** SRE-specific on-call noise survey. Do not claim they are SRE numbers.
- **Our own number is different and stronger.** "44% false, 0 minutes lead time" is measured on the provided CSV (22 of 50 CRITICAL rows were not incidents). Present it as "on this dataset", with the industry figures as corroboration that the problem is general.

## 4. Market and gap

**Market size** (estimates vary wildly because definitions differ; quote a range):
- 2025: **$6.7B** (Global Market Insights) to **$11B** (Business Research Co.) to **$16B** (a gii.tw-listed report) to **$32.5B** (IMARC).
- Growth: **17-30% CAGR** depending on publisher; Technavio says 21% (2024-2029).
- Safe pitch line: "AIOps is a roughly $10B+ market growing about 20% a year, per several analyst estimates." Skip the outlier $645B (Allied) figure.

**Incumbents:** Dynatrace (Davis AI, topology-aware, the only one with explicit predictive AI in my results), BigPanda and Moogsoft (event correlation, noise reduction), PagerDuty (on-call and incident response), Datadog, Splunk ITSI, Elastic.

**The gap (my synthesis from the search, not a sourced claim, so frame it as our thesis):**
1. Most tools **reduce noise and speed up RCA after the fact**. "Prevent before the outage" is mostly marketing language.
2. Alert correlation (BigPanda, Moogsoft) and incident response (PagerDuty) are **separate products**. Foresight closes the loop in one system: signal, plan, act, verify.
3. **Safe autonomy is the unsolved trust problem.** Fintech buyers will not let an LLM touch production. Our answer, "the agent decides, a deterministic Policy Guard holds a veto, everything is reversible with TTL", is a real differentiator.
4. **Security and reliability are siloed** (SOC vs SRE). One platform that handles both a pool leak and credential stuffing is uncommon.

Expect the question "Dynatrace and Datadog already do this." Honest answer: they detect anomalies and root cause well. We differ on (a) forecasting time-to-breach as the alert trigger, (b) an adversarial Skeptic agent against false positives, (c) bounded autonomous action with audit and rollback, (d) fintech-specific impact and routing. We are a thin layer that can sit on top of their alerts via the webhook connector, not necessarily a replacement.

## 5. Regulatory tailwind (fintech angle)

- **EU DORA** (Digital Operational Resilience Act) applies from **17 Jan 2025**. Financial entities must classify and report significant ICT incidents and show operational resilience. Reported penalty ceiling is about 2% of annual turnover, but sources conflict, so verify against Regulation (EU) 2022/2554 before quoting.
- Our audit trail (`agent_traces`, `actions`, evidence IDs) and PCI-aware redaction map to this. Position it as "explainable, auditable AI ops" and do not claim compliance.
- Credential stuffing in finance: Akamai counted **3.4B** credential-stuffing attacks on financial services in 2020 (the freshest figure the search returned; it is old, so label the year).

## 6. Business model (from blueprint §21, tightened)

- **Pricing:** SaaS per monitored service per month, plus analytics seats, plus a premium tier for autonomous security containment.
- **Buyer:** CTO / Head of Platform or Risk. **Champion:** on-call SRE. **Budget line:** reliability and operational resilience, not a new "AI" budget.
- **Value metrics to sell on:** lead time, pre-emptive ratio, MTTR reduction, false alerts per day. Each maps to avoided loss.
- **Land and expand:** webhook connector on top of existing Datadog/Alertmanager alerts (low friction), then pre-approved runbook actions, then a cross-customer anonymised pattern library.
- **I found no sourced pricing benchmark.** Do not quote a price unless the team has decided one.

## 7. Technical points to be fluent on

- **Why forecast beats threshold:** thresholds fire at the breach (lead time 0). Holt trend on `value/threshold` gives `TTB = (0.95 - ratio_now) / slope`, gated by trend R² >= 0.6. Lead time is the minutes between our first alert and the incident.
- **Why not just ML:** only 3-15 points per service-metric in the CSV, so we synthesise dense series anchored on the real rows. **Say this proactively** (blueprint §2 transparency rule). The seeded script is in the repo, and we report only on held-out days (Aug 21-30).
- **Where LLMs are used:** Log Analyst (finds failure patterns metrics miss, e.g. an expired certificate), Skeptic, Investigator, Commander. Cheap statistical and ML layers only produce signals. LLMs run on under 1% of events (grouped candidates), which keeps cost down.
- **Agentic proof points:** goal, plan v1 to v2 re-plan after a Skeptic dispute, `schedule_recheck`, post-action verification.
- **Safety envelope:** shadow mode, TTL auto-expiry, verification with auto-rollback, circuit breaker, kill switch, unit-tested Policy Guard. Failure mode is "does nothing and pages a human", never "acts wrongly".
- **Degradation:** LLM fallback chain GPT to Gemini to deterministic template, so it degrades to classic alerting, never silence.

## 8. Likely judge questions and short answers

| Question | Answer |
|---|---|
| Is the data real? | The 500 rows are real anchors, never altered. Everything between is generated by a seeded committed script, and results are on held-out days. |
| Did you overfit? | Tuned on Aug 1-20, reported on Aug 21-30 only. |
| Won't the Skeptic hide a real outage? | It can downgrade, not suppress, a risk >= 0.85 on a Tier-0 service. |
| What if the LLM is wrong or down? | The guard enforces hard preconditions, and the fallback is deterministic alerting. |
| Why would a bank trust autonomy? | Reversible, capped, allow-listed, audited, and only non-breaking actions are automatic. Scaling, restart and rollback need a human click. |
| How is it different from Dynatrace or PagerDuty? | See section 4: forecast-triggered, adversarial false-positive filter, bounded autonomy, fintech impact model. |
| Market size? | Roughly $10B+ and about 20% CAGR across several analysts. Estimates vary. |

## 9. What to avoid saying

- "$5,600 per minute" as Gartner fact (see section 2).
- The SOC alert-noise figures as if they were SRE data.
- Any specific claim that competitors "can't predict". Say "predictive prevention is mostly positioning in the market, and we make it measurable".
- "DORA compliant". Say "designed to support DORA-style audit and incident reporting".
- Any scorecard number not produced by `run_eval.py`.

---

## Sources

- PagerDuty, [Customer-facing incidents up 43%, ~$800K per incident](https://investor.pagerduty.com/news/news-details/2024/PagerDuty-Survey-Reveals-Customer-Facing-Incidents-Increased-by-43-During-the-Past-Year-Each-Incident-Costs-Nearly-800000/default.aspx)
- BigPanda / EMA, [The rising costs of downtime](https://bigpanda.io/blog/it-outage-costs-2024) and [EMA eBook (the $5,600 "urban legend")](https://start.bigpanda.io/rs/778-UNI-965/images/EMA_Outage_BigPanda_eBook.pdf)
- ManageEngine summary of ITIC 2024, [how much an hour of downtime costs](https://www.manageengine.com/network-monitoring/tech-topics/how-much-an-hour-of-downtime-cost.html)
- Uptime Institute coverage, [Data Center Knowledge](https://www.datacenterknowledge.com/outages/data-center-outages-decline-for-fourth-straight-year-but-issues-persist) and [BusinessWire, May 2026](https://www.businesswire.com/news/home/20260513289344/en)
- Splunk / Oxford Economics, [Hidden Costs of Downtime](https://splunk.com/en_us/newsroom/press-releases/2024/conf24-splunk-report-shows-downtime-costs-global-2000-companies-400-billion-annually.html)
- Parametrix, [CrowdStrike to cost Fortune 500 $5.4B](https://www.parametrixinsurance.com/in-the-news/crowdstrike-to-cost-fortune-500-5-4-billion-insured-loss-range-of-540-million-to-1-08-billion)
- TSB, [TechRadar: £330m bill](https://www.techradar.com/news/tsb-hit-with-pound330m-bill-following-major-it-outage) and [Business Insurance: $431M](https://www.businessinsurance.com/article/20190204/STORY/912326509/Technical-outage-costs-TSB-Bank-$431-million)
- Alert fatigue, [SANS 2025 via Stamus](https://www.stamus-networks.com/blog/what-the-2025-sans-detection-response-survey-reveals-false-positives-alert-fatigue-are-worsening), [Vectra](https://vectra.ai/topics/alert-fatigue)
- AIOps market, [Technavio](https://www.technavio.com/report/ai-operations-(aiops)-market-industry-analysis), [Global Market Insights](https://www.gminsights.com/industry-analysis/aiops-market), [IMARC](https://www.imarcgroup.com/global-aiops-market)
- DORA, [Quo Intelligence explainer](https://quointelligence.eu/2025/02/dora-explained-scope-requirements-enforcement-deadlines/)
- Credential stuffing, [Help Net Security (Akamai 2021)](https://www.helpnetsecurity.com/2021/05/20/financial-services-credential-stuffing/)
