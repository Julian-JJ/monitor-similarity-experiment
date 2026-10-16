"""Standard-library client for a vLLM-compatible chat endpoint."""

import copy
import json
import os
import urllib.error
import urllib.request


class ProtocolError(RuntimeError):
    def __init__(self, message, raw_response=None):
        super().__init__(message)
        self.raw_response = raw_response


def normalize(response):
    choice = response["choices"][0]
    original = choice["message"]
    content = original.get("content")
    if content is None:
        content = ""
    if not isinstance(content, str):
        raise ProtocolError("Expected assistant content to be a string or null")
    reasoning = original.get("reasoning_content")
    if reasoning is None:
        reasoning = original.get("reasoning")
    if reasoning is not None and not isinstance(reasoning, str):
        raise ProtocolError("Expected assistant reasoning to be a string or null")
    # Parsed reasoning, including an empty string, is authoritative. Only
    # interpret raw delimiters when no parsed field exists and content starts
    # with an explicit reasoning block. Inline or closing-only tags are text.
    if reasoning is None and content.lstrip().startswith("<think>"):
        block = content.lstrip()[len("<think>"):]
        if "</think>" not in block:
            raise ProtocolError("Unclosed reasoning block; likely truncated generation")
        reasoning, content = block.split("</think>", 1)
        reasoning = reasoning.strip()
    calls = copy.deepcopy(original.get("tool_calls") or [])
    for i, call in enumerate(calls):
        call.setdefault("id", f"call_{response.get('id', 'response')}_{i}")
        call.setdefault("type", "function")
        if not isinstance(call["function"]["arguments"], str):
            call["function"]["arguments"] = json.dumps(call["function"]["arguments"])
    if not calls and "<tool_call>" in content:
        raise ProtocolError("Unparsed tool call: start vLLM with --tool-call-parser hermes")
    return {"role": "assistant", "content": content, "reasoning": reasoning,
            "tool_calls": calls, "finish_reason": choice.get("finish_reason")}


class Client:
    def __init__(self, base_url, model, timeout=600, api_key_env="MODEL_API_KEY"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.api_key_env = api_key_env

    def request(self, path, body=None):
        headers = {"Content-Type": "application/json"}
        key = os.environ.get(self.api_key_env)
        if key:
            headers["Authorization"] = "Bearer " + key
        request = urllib.request.Request(self.base_url + path, headers=headers,
            data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as result:
                return json.load(result)
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")[:2000]
            raise RuntimeError(f"Inference HTTP {error.code}: {detail}") from error

    def check(self):
        names = [item["id"] for item in self.request("/models")["data"]]
        if names != [self.model]:
            raise ValueError(f"Expected exactly the recorded model {self.model!r}; endpoint offers {names}")
        return {"base_url": self.base_url, "served_model": self.model}

    def complete(self, messages, tools, settings, seed):
        # Qwen3's native template does not replay earlier reasoning. Keep it in
        # artifacts, but send only visible content and calls in conversation history.
        history = [{k: copy.deepcopy(v) for k, v in message.items()
                    if k in ("role", "content", "tool_calls", "tool_call_id", "name")
                    and not (k == "tool_calls" and not v)} for message in messages]
        body = {"model": self.model, "messages": history, "stream": False,
                "temperature": settings["temperature"], "top_p": settings["top_p"],
                "max_tokens": settings["max_tokens"], "seed": seed,
                "top_k": settings.get("top_k", 20), "min_p": settings.get("min_p", 0.0),
                "chat_template_kwargs": {"enable_thinking": True}}
        if tools:
            body.update(tools=tools, tool_choice="auto", parallel_tool_calls=False)
        response = self.request("/chat/completions", body)
        try:
            if response.get("model") != self.model:
                raise ProtocolError("Response model does not match the recorded serving configuration")
            return normalize(response), response
        except (KeyError, TypeError, IndexError, ProtocolError) as error:
            raise ProtocolError(str(error), response) from error
