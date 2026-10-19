# Monitor client

Code: [`monitor_experiment/monitor_client.py`](../../monitor_experiment/monitor_client.py), reusing the HTTP layer of
[`monitor_experiment/inference.py`](../../monitor_experiment/inference.py). Tests: `tests/test_monitor_client.py`, which runs the client
against a real local HTTP server (so actual request and response bytes are exercised) with scripted replies.

The client sends one **user message** to an OpenAI-compatible `/chat/completions` endpoint and returns a dictionary:
`text` (the visible reply), `reasoning` (the model's thinking, if the server returns it), `finish_reason`, `usage` (the server's token counts),
`latency_seconds` and `served_model`. It never judges validity: whether a reply counts is the caller's rule (a normal stop and an A–D answer).

## Request

`{"model": <what /models reports>, "messages": [{"role": "user", ...}], "stream": false, "seed", "temperature", "top_p", "max_tokens"}`
with sampling from the registry (temperature 0.6, top-p 0.9, 16,768 tokens, upstream's monitor settings). Thinking and effort:

| Cell `reasoning` | Added to the request |
| --- | --- |
| `default`, thinking monitor | `chat_template_kwargs: {enable_thinking: true}` |
| `default`, non-thinking monitor | nothing |
| `off` | `chat_template_kwargs: {enable_thinking: false}` |
| `low` / `medium` / `high` | `reasoning_effort: <level>` |

The `reasoning_effort` field is the OpenAI-style name; **whether the serving stack accepts it for GPT-OSS is unverified** and is a pilot item.

## `check()`

Asks `/models` and requires exactly one served model (one server serves one monitor); the name is then used in requests and recorded in the
run manifest. The command-line tool warns if the served model's name does not contain the registered model's short name, and refuses
`--base-url` together with several monitors.

## Retries and errors

Connection errors, timeouts, HTTP 5xx and 429 are retried up to twice with waits of 1 s and 2 s, then raised. Other HTTP errors (such as 400)
are raised immediately. A raised transport error is **not** a verdict: the runner leaves that unit unwritten and it reruns on resume. API keys are read
from the `MODEL_API_KEY` environment variable and sent only if set.

## Reasoning in the reply

The reasoning is taken from `reasoning_content`, else `reasoning`, else (if the content starts with `<think>…</think>`) from the content, which
is then stripped of it. Without a closing tag the content is left as is; such a reply is truncated and will be invalid anyway.
