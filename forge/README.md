# Forge

Forge is a lightweight FastAPI proxy that sits between Roo Code and a GPT-OSS backend.
It fixes unreliable tool-calling responses by simplifying tool schemas, repairing malformed
JSON, and retrying automatically when the model returns an empty response.

## What it does

| Problem | Fix |
|---------|-----|
| Too many tools confuse the model | Cap tool count (default: 8), strip optional params |
| Verbose descriptions waste context | Truncate descriptions to 100 chars |
| Model returns malformed JSON arguments | Detect and repair: trailing commas, missing brackets, truncated output |
| Model returns empty response | Retry up to 2 times with exponential backoff (1s, 2s) |
| Upstream takes too long | Configurable timeout (default: 60s), returns 504 on breach |
| Auth headers missing | Inject `X-USER-EMAIL` from CLI arg or env var |

## Install

```bash
cd forge
pip install -r requirements.txt
```

## Run

```bash
python forge.py \
  --target https://your-gpt-oss-server/v1 \
  --port 8080 \
  --header "X-USER-EMAIL:you@company.com" \
  --timeout 60 \
  --max-tools 8
```

Point Roo Code at `http://localhost:8080/v1` instead of the upstream server directly.

## Configuration

All options can be set via CLI flags or environment variables:

| CLI flag | Env var | Default | Description |
|----------|---------|---------|-------------|
| `--target` | `FORGE_TARGET` | `http://localhost:11434/v1` | Upstream base URL |
| `--port` | `FORGE_PORT` | `8080` | Port Forge listens on |
| `--header KEY:VALUE` | `FORGE_USER_EMAIL` | _(empty)_ | Custom header to inject |
| `--timeout` | `FORGE_TIMEOUT` | `60` | Upstream timeout in seconds |
| `--max-tools` | `FORGE_MAX_TOOLS` | `8` | Max tools forwarded per request |

## Proxied endpoints

| Endpoint | Behaviour |
|----------|-----------|
| `POST /v1/chat/completions` | Full proxy with tool simplification, JSON repair, retry |
| `GET /v1/models` | Transparent passthrough (for Roo Code model discovery) |

## Test

```bash
pytest test_forge.py -v
```

No real server required — all upstream calls are mocked.

## Log format

```
[HH:MM:SS] → POST /v1/chat/completions (tools: 5)
[HH:MM:SS] ← 200 (tool_call: read_file)
[HH:MM:SS] ↺ empty response, retrying (1/2)
[HH:MM:SS] ← 200 (content: 142 chars [repaired])
```
