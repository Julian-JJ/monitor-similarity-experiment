"""The monitor client against a real local HTTP server (no network, no model)."""

import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

from monitor_experiment.monitor_client import MonitorClient, make_complete
from monitor_experiment.registry import Registry, RegistryError

SAMPLING = {"temperature": 0.6, "top_p": 0.9, "max_tokens": 100}


class Server:
    """Serves scripted /models and /chat/completions replies and records every request."""

    def __init__(self, models=("served-model",), replies=None):
        self.requests, self.models = [], models
        self.replies = list(replies or [])
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send(self, status, payload):
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                outer.requests.append(("GET", self.path, None, dict(self.headers)))
                self.send(200, {"data": [{"id": m} for m in outer.models]})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(("POST", self.path, body, dict(self.headers)))
                status, payload = outer.replies.pop(0) if outer.replies else (200, ok())
                self.send(status, payload)

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/v1"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


def ok(content="analysis <answer>A</answer>", reasoning="thinking...", finish="stop", extra=None):
    message = {"role": "assistant", "content": content}
    if reasoning is not None:
        message["reasoning_content"] = reasoning
    message.update(extra or {})
    return {"model": "served-model", "choices": [{"message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7}}


class ClientTests(unittest.TestCase):
    def test_check_requires_exactly_one_served_model(self):
        with Server(models=("a", "b")) as s:
            with self.assertRaisesRegex(ValueError, "exactly one model"):
                MonitorClient(s.url, SAMPLING).check()
        with Server() as s:
            info = MonitorClient(s.url, SAMPLING).check()
            self.assertEqual(info["served_model"], "served-model")

    def test_request_body_and_parsed_reply(self):
        with Server() as s:
            client = MonitorClient(s.url, SAMPLING)
            client.check()
            out = client.complete("PROMPT TEXT", seed=42)
            body = s.requests[-1][2]
            self.assertEqual(s.requests[-1][1], "/v1/chat/completions")
            self.assertEqual(body["messages"], [{"role": "user", "content": "PROMPT TEXT"}])
            self.assertEqual((body["model"], body["seed"], body["temperature"], body["top_p"], body["max_tokens"]),
                             ("served-model", 42, 0.6, 0.9, 100))
            self.assertFalse(body["stream"])
            self.assertEqual(body["chat_template_kwargs"], {"enable_thinking": True})
            self.assertNotIn("tools", body)
            self.assertEqual(out["text"], "analysis <answer>A</answer>")
            self.assertEqual(out["reasoning"], "thinking...")
            self.assertEqual(out["finish_reason"], "stop")
            self.assertEqual(out["usage"], {"prompt_tokens": 11, "completion_tokens": 7})
            self.assertGreaterEqual(out["latency_seconds"], 0)

    def test_thinking_and_effort_controls(self):
        with Server() as s:
            for reasoning, expect_template, expect_effort in (("default", {"enable_thinking": True}, None),
                                                              ("off", {"enable_thinking": False}, None),
                                                              ("high", None, "high")):
                client = MonitorClient(s.url, SAMPLING, reasoning=reasoning)
                client.check()
                client.complete("p", 1)
                body = s.requests[-1][2]
                self.assertEqual(body.get("chat_template_kwargs"), expect_template)
                self.assertEqual(body.get("reasoning_effort"), expect_effort)
            client = MonitorClient(s.url, SAMPLING, thinking=False)
            client.check()
            client.complete("p", 1)
            self.assertNotIn("chat_template_kwargs", s.requests[-1][2])

    def test_reasoning_can_arrive_in_the_content_or_in_a_differently_named_field(self):
        replies = [(200, ok("<think>inner</think>final <answer>B</answer>", reasoning=None)),
                   (200, ok("text", reasoning=None, extra={"reasoning": "alt field"})),
                   (200, ok("plain", reasoning=None)),
                   (200, ok(None, reasoning="only thinking", finish="length"))]
        with Server(replies=replies) as s:
            client = MonitorClient(s.url, SAMPLING)
            client.check()
            first, second, third, fourth = (client.complete("p", 0) for _ in range(4))
        self.assertEqual((first["reasoning"], first["text"]), ("inner", "final <answer>B</answer>"))
        self.assertEqual(second["reasoning"], "alt field")
        self.assertIsNone(third["reasoning"])
        self.assertEqual((fourth["text"], fourth["finish_reason"]), ("", "length"))

    def test_complete_before_check_is_an_error(self):
        with self.assertRaisesRegex(RuntimeError, "check"):
            MonitorClient("http://127.0.0.1:1/v1", SAMPLING).complete("p", 0)

    def test_transient_server_errors_are_retried_with_backoff(self):
        naps = []
        replies = [(503, {"error": "busy"}), (500, {"error": "oops"}), (200, ok())]
        with Server(replies=replies) as s:
            client = MonitorClient(s.url, SAMPLING, sleep=naps.append)
            client.check()
            self.assertEqual(client.complete("p", 0)["text"], "analysis <answer>A</answer>")
            self.assertEqual(naps, [1, 2])
            self.assertEqual(sum(1 for r in s.requests if r[0] == "POST"), 3)

    def test_persistent_failures_and_client_errors_are_raised(self):
        with Server(replies=[(500, {})] * 3) as s:
            client = MonitorClient(s.url, SAMPLING, sleep=lambda _: None)
            client.check()
            with self.assertRaisesRegex(RuntimeError, "HTTP 500"):
                client.complete("p", 0)
        with Server(replies=[(400, {"error": "bad request"})]) as s:
            client = MonitorClient(s.url, SAMPLING, sleep=lambda _: None)
            client.check()
            with self.assertRaisesRegex(RuntimeError, "HTTP 400"):
                client.complete("p", 0)
            self.assertEqual(sum(1 for r in s.requests if r[0] == "POST"), 1, "a 400 is not retried")

    def test_an_unreachable_server_is_retried_then_raised(self):
        naps = []
        client = MonitorClient("http://127.0.0.1:9/v1", SAMPLING, sleep=naps.append, timeout=2)
        client.model = "m"
        with self.assertRaises(OSError):
            client.complete("p", 0)
        self.assertEqual(naps, [1, 2])

    def test_api_key_is_sent_only_when_set(self):
        with Server() as s:
            with patch.dict(os.environ, {"MODEL_API_KEY": "sekret"}):
                MonitorClient(s.url, SAMPLING).check()
            self.assertEqual(s.requests[-1][3].get("Authorization"), "Bearer sekret")
            with patch.dict(os.environ, {}, clear=True):
                MonitorClient(s.url, SAMPLING).check()
            self.assertNotIn("Authorization", s.requests[-1][3])

    def test_make_complete_refuses_placeholders_and_uses_registry_settings(self):
        registry = Registry.load()
        with self.assertRaises(RegistryError):
            make_complete(registry.monitor("gemma-large"))
        with Server() as s:
            client, complete = make_complete(registry.monitor("qwen3-14b"), base_url=s.url)
            client.check()
            complete("p", 3)
            body = s.requests[-1][2]
            self.assertEqual((body["temperature"], body["top_p"], body["max_tokens"]), (0.6, 0.9, 16768))


if __name__ == "__main__":
    unittest.main()
