"""A plain-prompt client for monitor models served behind an OpenAI-compatible chat endpoint.

The monitor stage sends one user message and reads back text. This client builds that request
(sampling, seed, thinking control), times it, retries transient transport failures, and returns the
dictionary the hierarchy code expects: ``text``, ``reasoning``, ``finish_reason``, ``usage`` and
``latency_seconds``. It never decides whether an answer is valid; that is the caller's rule.
See docs/system/monitor-client.md.
"""

import time
import urllib.error

from .inference import Client


class MonitorClient:
    def __init__(self, base_url, sampling, thinking=True, reasoning="default", timeout=3600,
                 api_key_env="MODEL_API_KEY", retries=2, sleep=time.sleep):
        self.http = Client(base_url, None, timeout, api_key_env)
        self.sampling, self.thinking, self.reasoning = dict(sampling), thinking, reasoning
        self.retries, self.sleep = retries, sleep
        self.model = None

    def check(self):
        """Ask the server what it serves; exactly one model is required. Returns provenance for the run manifest."""
        names = [item["id"] for item in self.http.request("/models")["data"]]
        if len(names) != 1:
            raise ValueError(f"Expected the server to serve exactly one model; it offers {names}")
        self.model = names[0]
        return {"base_url": self.http.base_url, "served_model": self.model}

    def body(self, prompt, seed):
        body = {"model": self.model, "stream": False, "seed": seed,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.sampling["temperature"], "top_p": self.sampling["top_p"],
                "max_tokens": self.sampling["max_tokens"]}
        if self.reasoning == "off":
            body["chat_template_kwargs"] = {"enable_thinking": False}
        elif self.reasoning in ("low", "medium", "high"):
            body["reasoning_effort"] = self.reasoning
        elif self.thinking:
            body["chat_template_kwargs"] = {"enable_thinking": True}
        return body

    def _post(self, body):
        for attempt in range(self.retries + 1):
            try:
                return self.http.request("/chat/completions", body)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                failure = error
            except RuntimeError as error:  # the shared client reports HTTP errors this way
                if "Inference HTTP 5" not in str(error) and "Inference HTTP 429" not in str(error):
                    raise
                failure = error
            if attempt == self.retries:
                raise failure
            self.sleep(2 ** attempt)

    def complete(self, prompt, seed):
        if self.model is None:
            raise RuntimeError("Call check() before complete()")
        started = time.monotonic()
        response = self._post(self.body(prompt, seed))
        elapsed = time.monotonic() - started
        choice = response["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""
        reasoning = message.get("reasoning_content")
        if reasoning is None:
            reasoning = message.get("reasoning")
        if reasoning is None and content.lstrip().startswith("<think>") and "</think>" in content:
            reasoning, content = content.lstrip()[len("<think>"):].split("</think>", 1)
        return {"text": content, "reasoning": reasoning, "finish_reason": choice.get("finish_reason"),
                "usage": response.get("usage"), "latency_seconds": elapsed, "served_model": response.get("model")}


def make_complete(monitor, reasoning="default", timeout=3600, base_url=None, **kwargs):
    """``(client, complete)`` for a registry :class:`~monitor_experiment.registry.Monitor`."""
    monitor.runnable()
    client = MonitorClient(base_url or monitor.base_url, monitor.sampling, monitor.thinking, reasoning, timeout, **kwargs)
    return client, client.complete
