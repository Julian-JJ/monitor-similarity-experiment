# Jev 1.14 — API and long-input pilot

Check the hosted interface, request identity and acceptance of short and long real inputs before production.

## How we ran it

Run representative full inputs, shared chunks and available Qwen summaries through jev-1.14.0; enable long-context mode for full CoT and Combined.

| Request type | Completed | Notes |
|---|---:|---|
| Full inputs | 6 | Shortest and longest examples in each view |
| Chunks | 57 | Shared prepared chunks |
| Summary inputs | 5 | One additional case blocked by incomplete Qwen summaries |

The 68 completed requests passed the pilot audit (job 34391510, 1:52). The longest accepted input was 229,506 Jev tokens. These responses were reused in production, not counted as extra samples. This checks execution and input acceptance, not an independent accuracy estimate.

Sources: [api-smoke-audit.json](../../../jev/api-smoke-audit.json) · [client.py](../../../jev/client.py)
