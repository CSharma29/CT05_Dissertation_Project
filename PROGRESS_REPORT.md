# CT05 Intelligent Contact Centre — Progress Report

**Project:** Dissertation — AI-powered intelligent contact centre on AWS
**Status:** Working end-to-end and deployed (verified 18 July 2026)
**Environment:** AWS account, region `ap-southeast-1`

## Summary

A serverless conversational contact centre is deployed and stable. A caller is
greeted by an Amazon Lex bot, verified against a customer record in DynamoDB,
and can then ask free-form questions that are answered by a large language
model, with conversation history persisted between turns. The full loop —
welcome → identity validation → verified Q&A → goodbye/close — has been tested
end to end in the deployed environment.

## Architecture

```
User → Amazon Lex bot → CT05_Handle_Conversation (Lambda)
                              │  validates user_id, tracks session state
                              ▼
                        DynamoDB CT05_Store_Context (per-user history)
                              │
                              ▼
                        CT05_Orchestrate_Conversation (Lambda)
                              │  builds prompt with prior context
                              ▼
                        LLM (Amazon Bedrock Claude — default;
                             Gemini / Anthropic API switchable)
```

All infrastructure is defined in CloudFormation (nested stacks: Lex bot,
both Lambdas, DynamoDB table, IAM roles) with packaging and deployment
scripts (`scripts/package.sh`, `deploy.sh`, `validate.sh`, `destroy.sh`).

## What has been achieved

1. **Infrastructure as Code** — the entire stack (Lex bot with four intents,
   two Lambda functions, DynamoDB table, IAM role and scoped permissions)
   deploys repeatably from CloudFormation templates.
2. **Identity validation** — `CT05_Handle_Conversation` verifies the caller's
   `user_id` via a DynamoDB query and marks the session verified through Lex
   session attributes.
3. **Conversational orchestration** — once verified, any utterance is routed
   to `CT05_Orchestrate_Conversation` (direct Lambda-to-Lambda invoke, since
   Lex V2 allows one code hook per alias), which calls the LLM and returns
   the answer to the user.
4. **Context persistence** — each exchange is summarised and written back to
   DynamoDB and carried in session attributes, so answers are informed by
   prior conversation.
5. **Provider-pluggable LLM layer** — the orchestrator supports three
   providers (Bedrock Claude, Google Gemini, Anthropic API) selected by
   environment variables, with no third-party SDKs in the deployment package
   (stdlib/boto3 only). This design directly supports the dissertation's
   model-comparison evaluation.
6. **Session lifecycle** — a CloseIntent ends the conversation cleanly with a
   goodbye message.
7. **Security review** — a permissions audit was carried out against the live
   account; IAM policies in CloudFormation are now scoped to the specific
   table, secret, and function ARNs rather than broad managed policies.
8. **Test plan** — `TEST_CASES.md` documents repeatable console/CLI test
   cases covering validation, Q&A, and close flows.

## Key design decisions

- **Bedrock as default LLM** — no API key/secret needed (IAM-based auth),
  keeps the whole solution inside AWS; other providers remain switchable for
  the comparative evaluation.
- **No pip-installed dependencies** — Lambda packages use only the Python
  standard library and boto3, keeping deployments small and reproducible.
- **DynamoDB schema** — `context_summary` is the table's sort key, allowing
  multiple summary items per user; lookups use `Query`.

## Remaining work

- Optional IAM cleanup: detach the two console-attached full-access managed
  policies from the Lambda execution role so it runs solely on the scoped
  CloudFormation grants.
- Dissertation evaluation and write-up: comparative testing across LLM
  providers using the built-in provider switch.
