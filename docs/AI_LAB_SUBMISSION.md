# Agenda parsing lab — implementation and remaining evidence

Status (2026-10-15): the user explicitly declined the Bedrock model agreement and asked to leave AI OFF. No agreement was accepted. Do not describe the AI portion as completed or submit unit-test mock responses as actual model outputs.

## Implemented

- Plain validated parser, one schema-repair attempt, configurable Claude model, literal-owner validation, token/cost aggregation.
- Database-free Cognito-authenticated Lambda, 10,000-character limit, clear errors, private-data-free structured logs.
- Isolated infra/ai.yml, no VPC/NAT/database credentials, restricted CORS, $5 monthly account-wide email budget.
- PARSER_ENABLED=false by default. The handler and plain parser refuse inference while off. The CloudFormation role explicitly denies CreateInference while off; the frontend disables Parse and keeps the editable form available.
- Meeting agenda editor, per-field suggested markers, cancellation, original suggestion retained independently from corrections.
- Authenticated ownership-scoped API saves final agenda and original suggestion in nullable JSONB columns. Confirmed title/time/duration feed the unchanged existing report queries.
- ADR: docs/adr/0006-llm-agenda-parsing.md; C4 container diagram: docs/architecture-containers.md.

## Local checks

`make up`, `make migrate`, `make test`, `make lint`.

For host tools: `cd backend && uv sync`; `make llm-hello` and `make parse TEXT="..."` intentionally exit without calling a model while AI is off. A local AWS login profile needs the dev botocore[crt] extra, already locked in this project. No permanent AWS credentials are stored in code.

In the deployed app, open Meetings and click Agenda beside a meeting. Add an agenda item and action item, edit fields, Save agenda, then reload. Null title/start/duration keep existing meeting metadata. Current AI state is shown visibly.

## Actual AWS access checks

A Nova Micro Converse hello succeeded (10 input / 53 output tokens) before the user disabled AI. The requested Opus 5.5 Messages hello returned 403: model unavailable for this account. A factual educational use-case form was submitted successfully (HTTP 201). Bedrock still reported agreementAvailability=NOT_AVAILABLE. Accepting the model agreement was rejected by automatic approval review, then explicitly declined by the user. No model agreement was accepted and no additional inference was requested after that decision.

## Evidence still required before submitting the full AI lab

1. The user must separately choose whether to approve paid Bedrock access. Do not enable PARSER_ENABLED or accept any model agreement automatically.
2. With explicit approval and working model access, deploy the parser with ParserEnabled=true, build the frontend with NEXT_PUBLIC_AGENDA_PARSER_ENABLED=true and its function URL. Rates must match the selected model.
3. Run the five inputs in docs/ai-evidence/inputs.json through the deployed signed-in screen. Store actual returned JSON, tokens, USD estimate and measured latency in the table below. Do not fill this from unit mocks or expected values.
4. Record at most 45 seconds: open a meeting, paste, Parse, correct one suggested field, Save, show success. No connected automated browser was available during implementation. The user can record this after enabling AI.
5. Copy one real successful CloudWatch agenda_parsed JSON line, with model, prompt_version, input_tokens, output_tokens, latency_ms and cost_usd. A disabled response is not a successful parse log.

| # | Input | JSON produced | Correct fields | Invented values | Tokens in/out | USD | Latency |
|---|---|---|---|---|---|---|---|
| 1 | Ukrainian pricing sync | Not run: AI disabled | Not measured | Not measured | — | — | — |
| 2 | English email | Not run: AI disabled | Not measured | Not measured | — | — | — |
| 3 | Relative/ambiguous dates | Not run: AI disabled | Not measured | Not measured | — | — | — |
| 4 | Shopping list | Not run: AI disabled | Not measured | Not measured | — | — | — |
| 5 | Injected owner instruction | Not run: AI disabled | Not measured | Not measured | — | — | — |

## Written answers — design rationale, not measured model results

1. No claim can be made about which of the five model outputs failed until the evaluation is run. The intended handling of “after lunch” is starts_at=null, because a schema alone cannot detect invented but syntactically valid times. The prompt explains this; the review UI allows corrections. Keep invented values separate from wrong date resolution or missing fields.
2. The injection input has not been evaluated against a live model. The prompt treats pasted text as untrusted data. Even if the model follows an injected owner instruction, it only returns a suggestion. The parser has no database credentials; saving needs the authenticated user's explicit confirmation, and the API enforces ownership. Literal-owner validation catches owners absent from the input, but cannot catch an injected email that appears inside the input itself.
3. Actual cost per successful parse has not been measured. For measured average cost C, 20 organisations × 30 agendas/week × 52/12 = 2,600 parses/month, costing approximately 2,600C. A $7.30/month interface endpoint costs the same as C≈$0.00281 per parse; the endpoint is an additional network charge, not a substitute for inference. For example only, 1,500 input and 500 output tokens at configured regional Opus rates cost $0.0176, or $45.76/month at that workload. Replace this example with actual averages from the logs.
4. Build a consented, anonymised evaluation set from the 500 original suggestions and final checked agendas. Have humans verify the corrected references, especially relative dates. Split into development and held-out sets; retain each original pasted input, its today/tz and model/prompt settings securely when permitted, because saved structured fields alone cannot reproduce a parse. Run v1 and v2 on the same held-out inputs and compare per-field accuracy, null accuracy, owner/task extraction, date resolution, invention rate, validation failure rate, cost and latency. Use the same model version and report sample size and uncertainty. User corrections are useful feedback, but untouched fields are not proof of correctness.

Budget alerts may be delayed and are not a hard spending cap. The budget covers the account, so existing infrastructure can trigger it as well. Authentication and input size limits do not prevent abuse by a valid account; add server-side per-user/global quotas before broader production usage.

## Deployed version

The manual agenda UI is published at https://d2u4q6uy2ofop2.cloudfront.net/meetings (click Agenda beside a meeting). API migration 0005 completed. The separate parser stack peach-ai exists in its explicitly disabled state, and the requested $5 account-wide budget is configured. Deployment and test evidence is in docs/ai-evidence/deployment-checks.txt. A $5 warning can be triggered by existing infrastructure too; creating the warning does not enable model billing.
