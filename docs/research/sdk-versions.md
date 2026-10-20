# SDK versions and behaviours (research for Task 0.1)

Checked 2026-10-20. Versions come from the PyPI JSON API (`https://pypi.org/pypi/<pkg>/json`) and the npm registry (`https://registry.npmjs.org/<pkg>/latest`). Source for openai-agents behaviours: the GitHub `main` source (pyproject version 0.24.0, identical to the PyPI latest) https://github.com/openai/openai-agents-python and docs https://openai.github.io/openai-agents-python/ . UNVERIFIED = not confirmed.

## 1. Version pins

| Package | Latest | Requires | Source |
|---|---|---|---|
| openai-agents | 0.24.0 (uploaded 2026-10-15) | Python >=3.10 | PyPI |
| openai (Python) | 3.35.1 | >=3.10 | PyPI |
| google-genai | 2.31.0 (2026-10-14) | >=3.10 | PyPI |
| fastapi | 0.150.0 | >=3.10 | PyPI |
| pydantic | 2.14.1 | >=3.10 | PyPI |
| pytest | 9.1.1 | >=3.10 | PyPI |
| ruff | 0.17.1 | >=3.7 | PyPI |
| pyright | 1.1.414 | (PyPI wrapper; npm also 1.1.414) | PyPI / npm |
| next | 16.4.2 (dist-tag latest; `canary` 16.5.0-canary.19) | Node >=20.9.0 | npm |
| create-next-app | 16.4.2 | Node >=20.9.0 | npm |
| @playwright/test | 1.64.1 | Node >=20 | npm |
| @axe-core/playwright | 4.14.0 | **Node >=22.12.0** | npm |
| shadcn (CLI) | 4.22.1 | - | npm |
| goccy/bigquery-emulator | v0.8.1 (2026-06-13) | Docker image `ghcr.io/goccy/bigquery-emulator` | GitHub releases API |

Gotchas: the dev machine's default `python3` is 3.9 (Apple CLT), below the >=3.10 floor of the agent SDK; use a 3.11+ venv. Node must be >=22.12 for axe-core/playwright (UNVERIFIED which Node is installed locally).
openai-agents is pre-1.0 (0.x): pin exactly (`openai-agents==0.24.0`).

## 2. openai-agents (0.24.0), verified from source

| Topic | Finding (source file in repo `src/agents/`) |
|---|---|
| `Agent.as_tool()` | Params in order: `tool_name`, `tool_description`, `custom_output_extractor`, `is_enabled`, `on_stream`, `run_config`, `max_turns`, `hooks`, `previous_response_id`, `conversation_id`, `session`, `failure_error_function`, `needs_approval`, `parameters`, `input_builder`, `include_input_schema`, `on_stream_max_pending_events` (docs ref/agent). Runs `Runner.run(...)` for the nested agent with `max_turns` default `DEFAULT_MAX_TURNS = 10` (`agent.py`, `run_config.py`). |
| Nested hooks | Nested run is called with `hooks=hooks`, i.e. only the `hooks` arg given to `as_tool()` (default None). **The outer run's `RunHooks` are NOT propagated** into the nested agent run (`agent.py` ~L1044-1053). The outer `RunHooks.on_tool_start/on_tool_end` DO fire for the agent-tool call itself, and the nested agent's own `agent.hooks` (AgentHooks) fire inside the nested run. Nested run inherits `run_config` (so a fake `model_provider` propagates) via `ToolContext.run_config`. To observe nested tool calls, pass `hooks=` to `as_tool()` or set `agent.hooks`. |
| `output_type` | `Agent(output_type=PydanticModel)`; default schema is strict. For non-strict, pass `output_type=AgentOutputSchema(MyModel, strict_json_schema=False)` (`agent_output.py`: `__init__(self, output_type, strict_json_schema=True)`; strict failure raises UserError advising exactly this wrap). |
| `Model` ABC | `agents.models.interface.Model` abstract methods: `async get_response(system_instructions, input, model_settings, tools, output_schema, handoffs, tracing, *, previous_response_id, conversation_id, prompt) -> ModelResponse` and `stream_response(...same args...) -> AsyncIterator[TResponseStreamEvent]` (abstract too). Optional overrides: `close()`, `get_retry_advice()`, `_cleanup_on_run_end()`. |
| `ModelProvider` ABC | `get_model(self, model_name: str | None) -> Model` (abstract); optional `aclose()`. Use via `RunConfig(model_provider=MyProvider())` (docs /models/); default is `MultiProvider`. Per-agent: `Agent(model=<Model instance>)`. |
| `ModelResponse` | pydantic dataclass: `output: list[TResponseOutputItem]`, `usage: Usage`, `response_id: str | None` (no default, pass None), `request_id=None`, `raw_usage=None` (`items.py`). |
| Emitting a tool call from a fake Model | Return `ModelResponse(output=[ResponseFunctionToolCall(id="1", call_id="c1", type="function_call", name="<tool name>", arguments='{"json":"args"}')], usage=Usage(), response_id=None)` (class from `openai.types.responses`; this is exactly what the repo test helper `get_function_tool_call` in `tests/test_responses.py` builds). Final text: `ResponseOutputMessage(id="1", type="message", role="assistant", status="completed", content=[ResponseOutputText(text="...", type="output_text", annotations=[], logprobs=[])])`. For a structured `output_type`, the text must be the JSON string. Script a queue of such responses; the runner executes the tool and calls the model again. Implement `stream_response` by raising `NotImplementedError` if you never stream. |
| `RunHooks` | `RunHooksBase` async methods: `on_llm_start(context, agent, system_prompt, input_items)`, `on_llm_end(context, agent, response: ModelResponse)`, `on_agent_start(context: AgentHookContext, agent)`, `on_agent_end(context, agent, output)`, `on_handoff(context, from_agent, to_agent)`, `on_tool_start(context, agent, tool)`, `on_tool_end(context, agent, tool, result)` (`lifecycle.py`). Pass `Runner.run(..., hooks=MyRunHooks())`. |
| `AgentHooks` | `agent.hooks = ...`; methods `on_start(context, agent)`, `on_end(context, agent, output)`, `on_handoff(context, agent, source)`, `on_tool_start`, `on_tool_end`, `on_llm_start`, `on_llm_end` (same arg shapes). |
| `RunContextWrapper` | Generic wrapper (`run_context.py`) with `.context` (your object), `.usage`, `.turn_input`, `.tool_input`. Tools get it as first param (`RunContextWrapper[MyCtx]`) or a `ToolContext` subclass; not sent to the LLM. |
| `MaxTurnsExceeded` | `agents.exceptions.MaxTurnsExceeded(AgentsException)` with `.message`; raised when turns > `max_turns` (default 10; pass `Runner.run(max_turns=N)`). |
| Disable tracing | `from agents import set_tracing_disabled; set_tracing_disabled(True)` (docs /models/), or env `OPENAI_AGENTS_DISABLE_TRACING=1` (`true`/`1`, read once on first use, `tracing/provider.py`; manual call overrides env). Also `RunConfig(tracing_disabled=True)` exists: UNVERIFIED (grep did not confirm). |
| Output guardrails | They trip, not regenerate. Docs (guardrails.md "Tripwires"): runner "immediately raises" `OutputGuardrailTripwireTriggered` and halts; exception carries `guardrail_result` and `run_data.output_guardrail_results`. Output guardrails only run on the final agent's output. Regenerate loop must live in our orchestrator (consistent with plan S6). |

## 3. Next.js 16 (latest 16.4.2)

Source: https://nextjs.org/docs/app/guides/upgrading/version-16 (lastUpdated 2026-10-15).

| Change vs 15 | Detail |
|---|---|
| Runtime | Node >=20.9.0; TypeScript >=5.1; React 19.2 |
| `middleware.ts` -> `proxy.ts` | Rename file and export `proxy(request)`. `proxy` runs on `nodejs` runtime only (no `edge`). Config flags renamed e.g. `skipProxyUrlNormalize`. |
| Async request APIs | Sync access removed: `cookies()`, `headers()`, `draftMode()`, `params`, `searchParams` must be awaited (`params: Promise<...>` in pages/layouts/route handlers). Codemod: `npx @next/codemod@canary next-async-request-api .` |
| Turbopack | Default for `dev` and `build`; build FAILS if a custom `webpack` config exists (use `--webpack` to opt out). Config moved to top-level `turbopack`. |
| Lint | `next lint` removed, `next build` no longer lints; run ESLint (flat config; eslint-config-next@16 needs ESLint >=9) directly. |
| Caching | `experimental.ppr/dynamicIO/useCache` removed; opt in with top-level `cacheComponents`. `revalidateTag(tag, 'max')` needs 2nd arg. |
| Images | `minimumCacheTTL` default 4h, `qualities` default `[75]`, `imageSizes` drops 16, local query strings need `localPatterns.search`, `maximumRedirects` default 3. |
| Other | Parallel route slots require `default.js`; `serverRuntimeConfig`/`publicRuntimeConfig` and AMP removed; `next dev` outputs to `.next/dev`. |

### create-next-app (non-interactive)
Source: https://nextjs.org/docs/app/api-reference/cli/create-next-app . Flags: `--ts`, `--app`, `--tailwind`, `--eslint`, `--src-dir`, `--import-alias "@/*"`, `--use-npm|--use-pnpm`, `--skip-install`, `--disable-git`, `--turbopack` (default), `--no-react-compiler`-style `--no-*` negation, `--cache-components` (**default for App Router**), `--agents-md` (default), `--yes`.
Suggested: `npx create-next-app@16.4.2 web --ts --app --tailwind --eslint --src-dir --import-alias "@/*" --use-npm --disable-git --no-cache-components --yes`. (`--no-cache-components` follows the documented `--no-*` rule; UNVERIFIED by execution.) Reason: with Cache Components on, uncached dynamic data outside `<Suspense>` fails the build and route segment config interaction is UNVERIFIED; an SSE proxy route is simpler without it.

### SSE Route Handler recipe
Sources: https://nextjs.org/docs/app/guides/streaming ; https://nextjs.org/docs/app/api-reference/file-conventions/route ; https://nextjs.org/docs/app/api-reference/config/next-config-js/compress
- GET Route Handlers are dynamic by default since v15 (route.js version history). Still add `export const dynamic = 'force-dynamic'` and `export const runtime = 'nodejs'` (documented segment config; `force-dynamic` combined with Cache Components: UNVERIFIED, hence the `--no-cache-components` choice).
- `next.config.ts`: `compress: false` (documented; gzip can buffer chunks "before flushing", streaming guide). Add `headers()` entry `X-Accel-Buffering: no` (documented for Nginx-type proxies).
- Response: `new Response(stream, { headers: { 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-cache, no-transform', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no' } })`. (Only `X-Accel-Buffering` and the `Content-Type`/`X-Content-Type-Options` pattern are in the docs; the `Cache-Control` and `Connection` values are standard SSE practice, UNVERIFIED in Next docs.)
- Cancellation: handler receives a `NextRequest` (extends Web `Request`), so `request.signal` is the standard Web `AbortSignal`; pass it to the upstream `fetch(url, { signal: request.signal })` and close the stream on `abort`. Next docs do not describe `signal` explicitly: UNVERIFIED in Next docs.
- Verify with a script, not curl (`Accept-Encoding: identity`; curl needs `-N` and newlines). Safari buffers until 1024 bytes. CDNs/serverless may buffer (Cloud Run: UNVERIFIED).

## 4. Pub/Sub emulator
Source: https://docs.cloud.google.com/pubsub/docs/emulator
- Push subscriptions: supported; local plain-HTTP endpoints allowed, e.g. `http://[::1]:3000/messages` (production requires https).
- BigQuery subscriptions: "can be created, but don't send messages to BigQuery". Plan impact: the BQ-subscription path can only be shown live; in local/CI use a pull-subscriber writer or InMemoryBus.
- Also unsupported: `UpdateTopic`, `UpdateSnapshot`, IAM; no retention config; protobuf schemas unsupported (Avro ok).

## 5. goccy/bigquery-emulator (v0.8.1, beta)
Source: https://github.com/goccy/bigquery-emulator (README)
- Supported: datasets/tables/jobs/tabledata, GoogleSQL queries, load/extract jobs, **streaming inserts** (listed; behaviour not described: UNVERIFIED for edge cases), gRPC Storage read/write API, views, wildcard tables, JS UDFs; SQLite storage in memory or file; YAML seed.
- Unsupported: IAM, row access policies, copy jobs, external tables, table snapshots, **BigQuery ML**. So `AI.DETECT_ANOMALIES`, ARIMA_PLUS and `VECTOR_SEARCH`-style features: VECTOR_SEARCH support UNVERIFIED (not mentioned; assume absent).
- DDL: README has no DDL section; `CREATE FUNCTION` example and views shown; `CREATE TABLE` via SQL: UNVERIFIED (use the client `create_table` API).
- Python: `Client(project="test", credentials=AnonymousCredentials(), client_options=ClientOptions(api_endpoint="http://0.0.0.0:9050"))`. For DataFrame downloads pass `create_bqstorage_client=False` (gRPC is plaintext).
- Docker: `docker run -p 9050:9050 -p 9060:9060 ghcr.io/goccy/bigquery-emulator:latest --project=test` (REST 9050, gRPC 9060; Apple Silicon may need `--platform linux/x86_64`).

## 6. google-genai for Vertex
Sources: https://raw.githubusercontent.com/googleapis/python-genai/main/README.md and `google/genai/client.py` (main).
- Package `google-genai` 2.31.0, `from google import genai`.
- Vertex is now called "enterprise" in the SDK: `genai.Client(enterprise=True, project=PROJECT, location="global")`. The legacy `vertexai=True` is still accepted ("Legacy flag for `enterprise`"; conflicting values raise). Env: `GOOGLE_GENAI_USE_ENTERPRISE=true` (legacy `GOOGLE_GENAI_USE_VERTEXAI` still read; ENTERPRISE wins on conflict) + `GOOGLE_CLOUD_PROJECT` + `GOOGLE_CLOUD_LOCATION=global`, then `genai.Client()`.
- Pin note: if pinning an older google-genai, `vertexai=True` is the safe spelling; with 2.31.0 both work (UNVERIFIED on the exact release that introduced `enterprise`).
- Call: `client.models.generate_content(model="gemini-3.8-flash", contents=..., config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=Model))` (README shows `generate_content`; JSON-schema config not fetched: UNVERIFIED).
- Close with `client.close()`; async via `client.aio`.

## 7. shadcn CLI
Source: https://ui.shadcn.com/docs/cli . `npx shadcn@4.22.1 init -y -d` (`-d/--defaults` = `--template=next --preset=nova`; `-y` skips prompts); `npx shadcn@4.22.1 add button card -y` (`add` flags: `-o` overwrite, `-a` all, `--dry-run`). Package name is `shadcn` (not `@shadcn/ui`, which is a stale 0.0.4).
