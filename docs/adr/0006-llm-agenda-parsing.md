# 0006 — Parse agendas on a separate, database-free Lambda

## Free cloud demonstration addendum (2026-10-28)

The owner additionally prohibited new AWS costs and requested a public,
non-local demonstration. A separate `cloudflare/` application now hosts the
agenda workflow on Workers static assets, a Worker API and D1. It does not call
or migrate the existing AWS services. The live URL and measured evidence are
in `docs/CLOUDFLARE_DEMO.md` and `docs/ai-evidence/CLOUDFLARE_EVALUATION.md`.

This demo uses a single-owner password, a signed HttpOnly Secure SameSite cookie,
an origin check, prepared owner-scoped SQL and the same agenda JSON schema/tool
contract. Original suggestions remain separate from user corrections. The
parser never executes a model-requested database write. Only the free Cohere
model is allowed, with a daily quota and manual fallback. Secrets are stored
as Worker Secrets. Runtime logs contain metadata, not pasted text or credentials.

This deliberately differs from the original Cognito/Aurora/Lambda/Bedrock
architecture; it demonstrates the lab workflow rather than migrating the
whole application or meeting every AWS-specific requirement. Existing AWS
resources remain running independently. Lecturer approval of this alternative
and a browser recording are still required.

## Context

Peach users receive agendas as multilingual emails and chat messages. The API and Aurora run inside a VPC without NAT. Model inference costs money and pasted text may contain malicious instructions. Existing meeting management, authentication and weekly reports must keep working.

## Decision

Use the Anthropic Messages API through Amazon Bedrock, with the model configured by PARSER_MODEL (the lab requests Claude Opus 5.5). A separate 512 MB, 30-second Lambda runs outside the VPC and has inference and logging permissions, with no database credentials or database/network permissions. Its public function URL verifies the same Cognito ID JWT before inference, limits input to 10,000 characters and permits browser requests from the deployed site only. CORS is not authentication.

The model calls record_agenda as a proposed data structure. Pydantic validates it, checks offset-aware dates and literal owners, and allows one repair of invalid fields. Prompt text is versioned. Ambiguous times and missing values stay null. Non-agendas return a clear error. No tool executes a database write.

The user reviews an editable form; suggested markers disappear field by field as values change. Save uses the existing authenticated API and checks meeting ownership in SQL. A nullable agenda JSONB column stores the final fields, while ai_suggestion keeps the original parsed structure, model, prompt version and usage. Confirmed title, start and duration update meeting metadata in that same transaction, so existing reports reflect the checked values. No report infrastructure changes are required.

## Alternatives

- Bedrock from the API through an interface endpoint: adds fixed hourly/AZ charges and couples inference failures to the database-serving process.
- Claude API directly: needs a separate secret and billing account instead of the existing IAM credentials and AWS billing.
- Regular expressions: cheap and deterministic but unsuitable for multilingual free-form agenda items, owners, tasks and relative dates.

## Consequences

Inference is optional: manual editing and saving work when Bedrock is unavailable. Cancel stops the browser request; it cannot guarantee cancellation of an already-running inference. Calls have finite timeouts, no hidden SDK retries, and at most one validation repair. Usage from both attempts is counted. Logs contain user sub, model, prompt version, token totals, latency, status and estimated USD; they exclude pasted text and parsed private agenda contents.

At the lab's regional Opus estimate ($4.40/$22 per million input/output tokens), cost is (input_tokens*4.4 + output_tokens*22)/1,000,000. Rates are configuration, not an AWS invoice. The $5 account-wide monthly AWS Budget emails a warning; it is neither real-time nor a spending cap. Account-wide scope also covers provider/Marketplace billing. Authentication and input size limit abuse but do not prevent a valid account from repeatedly spending money; production should add per-user/global quotas and narrow model access where IAM supports it. Schema validation cannot establish semantic truth or completely prevent prompt injection; the user's confirmation and scoped API write limit damage.

## Current rollout state

On 2026-10-28 the owner requested a free cloud alternative without local model
downloads. An optional `openrouter_free` provider adapts the same record_agenda
tool and validation flow to OpenRouter, allowing only `cohere/north-mini-code:free` (the default) or
`openrouter/free`. Parallel tool calls and reasoning are disabled. It never
selects paid models or falls back to Bedrock, and stores the actual selected
model in the response/log. The API key is server-side configuration. Quota or
availability errors preserve manual editing. Free inference is distinct from
existing AWS hosting costs. This is an alternative to, rather than completion
of, the lab's explicit Claude-on-Bedrock requirement; see ../FREE_AI.md.
No AWS configuration was changed by adding this alternative. Five live API tests on Cohere are recorded in
`docs/ai-evidence/FREE_EVALUATION.md`, with zero provider cost and documented
semantic failures. Local API health, unauthenticated 401 and frontend HTTP 200
were checked; authenticated UI/video and CloudWatch evidence remain unavailable. Downloaded Ollama binaries were removed.

The owner declined the paid model agreement on 2026-10-15. AI stays disabled by default in the UI, handler and plain parser; the disabled Lambda role explicitly denies inference. The agenda form and persistence remain usable. Live evaluations, a successful parse log and the AI screen recording are pending, rather than fabricated from unit-test mocks. Enabling paid inference requires a new explicit owner decision.
