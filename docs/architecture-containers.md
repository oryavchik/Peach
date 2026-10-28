# Peach — container diagram (C4 level 2)

```mermaid
flowchart LR
    user[Person: Peach user]
    browser[Container: Next.js browser application\nCloudFront / private S3 static hosting]
    cognito[External system: Amazon Cognito\nLogin and ID tokens]
    parser[Container: Agenda parser Lambda\nPython / Anthropic SDK\nOutside VPC, no database access]
    bedrock[External system: Amazon Bedrock\nClaude Messages API]
    subgraph vpc[Default VPC — no NAT]
      api[Container: FastAPI Lambda\nAuthenticated API]
      db[(Container: Aurora PostgreSQL\nMeetings, final agenda, AI suggestion)]
      builder[Container: Report builder Lambda]
    end
    s3[Container: Reports S3 bucket]
    queue[Container: Report SQS queue + DLQ]
    schedule[Container: EventBridge Scheduler]
    mailer[Container: Report mailer Lambda\nOutside VPC]
    dispatch[Container: Request dispatcher Lambda\nOutside VPC]
    ses[External system: Amazon SES]
    user --> browser
    browser -->|Sign in / refresh| cognito
    browser -->|Parse: HTTPS POST + Cognito JWT| parser
    parser -->|Messages + record_agenda schema| bedrock
    browser -->|Save checked fields + original suggestion: HTTPS + JWT| api
    api -->|Ownership-scoped SQL transaction| db
    api -->|Personal request file via S3 gateway endpoint| s3
    s3 -->|requests/ ObjectCreated| dispatch
    dispatch --> queue
    schedule --> queue
    queue --> builder
    builder -->|Read meetings| db
    builder -->|CSV via gateway endpoint| s3
    s3 -->|reports/ ObjectCreated| mailer
    mailer -->|Email with CSV| ses
```

Only the parse path calls a model. Only the trusted API saves the checked agenda. Existing weekly reports keep their separate event-driven path.

## Optional free cloud demonstration (2026-10-28)

The owner requested no paid inference and no local model weights. The local
Next.js UI can instead call a loopback Python adapter, which verifies Cognito
and invokes `cohere/north-mini-code:free` through OpenRouter. Its server-side
API key is never sent to the browser. Only this free model and the free router
are allowed; quota exhaustion returns an error, without a paid fallback.
Save still uses the existing authenticated API. This alternative has not been
deployed to AWS and does not replace the assignment's Bedrock requirement.

```mermaid
flowchart LR
    local[Local Next.js browser UI :3000]
    adapter[Local Python parser adapter :8001\nCognito JWT validation, no database]
    free[OpenRouter\ncohere/north-mini-code:free]
    existing[Existing authenticated Lambda API]
    aurora[(Existing Aurora PostgreSQL)]
    local -->|Parse text + today + tz + JWT| adapter
    adapter -->|record_agenda tool, server API key| free
    free -->|Suggestion only| adapter
    adapter -->|Validated JSON| local
    local -->|Save checked fields + original suggestion| existing
    existing -->|Ownership-scoped SQL| aurora
```

Actual API measurements and semantic failures are recorded in
`docs/ai-evidence/FREE_EVALUATION.md`. No authenticated UI recording or
CloudWatch evidence is claimed for the local alternative.
