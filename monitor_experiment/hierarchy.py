"""Hierarchical (chunked) monitor for transcripts that exceed a monitor's context.

A transcript is rendered for one observation scope, split into token-budgeted
chunks, and each chunk is monitored with MonitorBench's own agent prompt. The
chunk analyses are then combined in bins until one analysis remains; its A-D
verdict is the monitor's verdict. A transcript whose complete upstream prompt fits
the monitor's input limit is monitored in one pass by the unmodified upstream
prompt, so the single-pass condition is the one-chunk special case. See docs/plan/05-hierarchical-monitor.md.

Nothing here calls a model: ``run_tree`` takes the completion function as an
argument, and token counts come from a caller-supplied counter.
"""

import math
import re
from pathlib import Path

from .artifacts import digest

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_PROMPTS = ROOT / "vendor/monitorbench_monitor/prompts/monitor_dual_objectives.agent.yaml"
SCOPES = ("action", "cot", "all")

# The vendored system message is: preamble, secondary-task text, "At each step...".
OBJECTIVE_START = "complete the secondary task.\n\n"
OBJECTIVE_END = "\n\nAt each step, you will be given the chance"
# Upstream extracts the verdict with this expression (utils.extract_choice).
ANSWER = re.compile(r"<answer>\s*([A-Da-d])\s*</answer>")
# The marker in each upstream template that precedes the main task and transcript.
TRANSCRIPT_MARKER = "Here is the **stated main task**:"
# The reference-plan block goes immediately before the hidden objective in every prompt.
OBJECTIVE_MARKER = "Here is the **hidden objective**:"
SEPARATORS = ("\n\n", "\n", " ")


class HierarchyError(RuntimeError):
    """The plan cannot be built or run within the stated budgets."""


def default_params(scope):
    """Defaults mirror upstream's monitor serving limits (32,768 context, 16,768 output)."""
    if scope not in SCOPES:
        raise ValueError(f"Unknown scope {scope!r}; expected one of {SCOPES}")
    return {"scope": scope, "context_tokens": 32768, "output_reserve": 16768,
            "chunk_tokens": 12000, "bin_size": 4, "margin_tokens": 512,
            "truncate_chars": 2000, "labels": True, "max_attempts": 2,
            "single_pass_if_fits": True}


def check_params(params):
    if params["scope"] not in SCOPES:
        raise ValueError(f"Unknown scope {params['scope']!r}")
    if params["bin_size"] < 2:
        raise ValueError("bin_size must be at least 2, otherwise no level can reduce the one below")
    if not 1 <= params["max_attempts"] <= 10:
        raise ValueError("max_attempts must be between 1 and 10 (seeds are spaced 10 apart per call)")
    if params["context_tokens"] - params["output_reserve"] <= params["margin_tokens"]:
        raise ValueError("context_tokens - output_reserve must exceed margin_tokens")
    return params


def input_limit(params):
    """Largest prompt, in tokens, that is sent to the monitor."""
    return params["context_tokens"] - params["output_reserve"] - params["margin_tokens"]


def load_prompts():
    import yaml  # PyYAML is a base requirement; imported lazily like the other heavy imports
    upstream = yaml.safe_load(UPSTREAM_PROMPTS.read_text())
    prompts = {"upstream": upstream,
               "notice": (ROOT / "prompts/monitor_chunk_notice.txt").read_text(),
               "reduce": (ROOT / "prompts/monitor_reduce.txt").read_text(),
               "plan": (ROOT / "prompts/monitor_plan.txt").read_text(),
               "plan_section": (ROOT / "prompts/monitor_plan_section.txt").read_text()}
    for scope in SCOPES:
        if upstream[scope].count(TRANSCRIPT_MARKER) != 1:
            raise HierarchyError(f"Upstream {scope} template must contain the transcript marker exactly once")
        if upstream[scope].count(OBJECTIVE_MARKER) != 1:
            raise HierarchyError(f"Upstream {scope} template must contain the objective marker exactly once")
    if prompts["reduce"].count(OBJECTIVE_MARKER) != 1:
        raise HierarchyError("The combining template must contain the objective marker exactly once")
    return prompts


def tokenizer_counter(path):
    """Exact token counter from a Hugging Face ``tokenizer.json`` (needs ``tokenizers``)."""
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(path))
    return lambda text: len(tokenizer.encode(text or "", add_special_tokens=False).ids)


# --- reading a saved rollout -------------------------------------------------

def main_task(messages):
    for message in messages:
        if message["role"] == "user":
            return message["content"]
    raise ValueError("Rollout has no user message")


def hidden_objective(messages):
    """The side-objective text the monitor is told about.

    Read from the system message, whose layout is fixed by the vendored
    ``construct_system_message``. ``main_only`` rollouts contain no side
    objective; their monitor input must be supplied from another source.
    """
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    start = system.find(OBJECTIVE_START)
    if start < 0:
        raise ValueError("System message has no secondary task (a main_only rollout?)")
    start += len(OBJECTIVE_START)
    end = system.find(OBJECTIVE_END, start)
    if end < 0:
        raise ValueError("Could not find the end of the secondary task in the system message")
    return system[start:end].strip()


def turns(messages):
    """Group messages into turns: one assistant message plus the tool replies that follow it.

    The system prompt and the first user message are not part of any turn. An
    unexpected message order raises instead of silently dropping content.
    """
    result, seen_user = [], False
    for message in messages:
        role = message["role"]
        if role == "system":
            continue
        if role == "user":
            if seen_user:
                raise ValueError(f"Unexpected second user message {message['id']}")
            seen_user = True
        elif role == "assistant":
            calls = [{"id": c.get("id"), "name": c["function"]["name"],
                      "arguments": c["function"]["arguments"]}
                     for c in (message.get("tool_calls") or [])]
            result.append({"turn": len(result) + 1, "id": message["id"],
                           "message_ids": [message["id"]],
                           "reasoning": message.get("reasoning") or "",
                           "content": message.get("content") or "",
                           "calls": calls, "results": []})
        elif role == "tool":
            if not result:
                raise ValueError(f"Tool message {message['id']} precedes any assistant message")
            content = message.get("content")
            result[-1]["results"].append({"id": message["id"], "name": message.get("name"),
                                          "content": content if isinstance(content, str) else str(content)})
            result[-1]["message_ids"].append(message["id"])
        else:
            raise ValueError(f"Unexpected role {role!r} in message {message['id']}")
    return result


# --- rendering ---------------------------------------------------------------

def span(turn):
    ids = turn["message_ids"]
    return ids[0] if len(ids) == 1 else f"{ids[0]}-{ids[-1]}"


def render_turn(turn, scope, labels=True, truncate_chars=2000):
    """Return ``(header, body, truncated_results)`` for one turn and scope.

    ``action``: tool calls and tool results. ``cot``: reasoning and visible
    assistant text. ``all``: both, chronologically. The body is empty when the
    scope has nothing to show for this turn. Tool results longer than
    ``truncate_chars`` are cut with upstream's marker and counted; ``None``
    disables the cut. The header names only turn and message IDs.
    """
    parts, truncated = [], 0
    if scope in ("cot", "all"):
        if turn["reasoning"].strip():
            parts.append(turn["reasoning"])
        if turn["content"].strip():
            parts.append(turn["content"])
    if scope in ("action", "all"):
        if turn["calls"]:
            parts.append("\n".join(f"{c['name']}({c['arguments']})" for c in turn["calls"]))
        for result in turn["results"]:
            text = result["content"]
            if not text:
                continue
            if truncate_chars is not None and len(text) > truncate_chars:
                text = text[:truncate_chars] + "...[truncated]"
                truncated += 1
            parts.append(text)
    body = "\n\n".join(parts)
    header = f"=== Turn {turn['turn']} (messages {span(turn)}) ===" if labels else ""
    return header, body, truncated


def split_text(text, budget, count, separators=SEPARATORS):
    """Split ``text`` into pieces of at most ``budget`` tokens; ``"".join(pieces) == text``.

    Prefers paragraph, then line, then word boundaries, and halves by
    characters as a last resort. Piece sizes are summed from per-piece counts,
    then each result is verified with a real count and re-split if needed.
    """
    if count(text) <= budget:
        return [text]
    if len(text) <= 1:
        raise HierarchyError("Cannot split a single character within the token budget")
    if not separators:
        middle = len(text) // 2
        return split_text(text[:middle], budget, count, ()) + split_text(text[middle:], budget, count, ())
    separator, rest = separators[0], separators[1:]
    raw = text.split(separator)
    if len(raw) == 1:
        return split_text(text, budget, count, rest)
    pieces = [p + separator for p in raw[:-1]] + [raw[-1]]
    parts, current, current_tokens = [], [], 0

    def flush():
        nonlocal current, current_tokens
        if current:
            parts.append("".join(current))
        current, current_tokens = [], 0

    for piece in pieces:
        tokens = count(piece)
        if tokens > budget:
            flush()
            parts.extend(split_text(piece, budget, count, rest))
            continue
        if current and current_tokens + tokens > budget:
            flush()
        current.append(piece)
        current_tokens += tokens
    flush()
    result = []
    for part in parts:
        result.extend([part] if count(part) <= budget else split_text(part, budget, count, rest))
    return result


def segments(rollout_turns, params, count):
    """Render every turn and split any turn larger than ``chunk_tokens`` into labelled parts."""
    scope, labels, budget = params["scope"], params["labels"], params["chunk_tokens"]
    result, truncated = [], 0
    for turn in rollout_turns:
        header, body, cut = render_turn(turn, scope, labels, params["truncate_chars"])
        truncated += cut
        if not body.strip():
            continue
        text = header + "\n" + body if header else body
        tokens = count(text)
        if tokens <= budget:
            result.append({"turn": turn["turn"], "part": 1, "parts": 1, "text": text, "tokens": tokens})
            continue
        # Reserve room for the continuation header that every part receives.
        allowance = count(f"=== Turn {turn['turn']} (messages {span(turn)}, part 999 of 999) ===\n") + 8 if labels else 0
        pieces = split_text(body, budget - allowance, count)
        for index, piece in enumerate(pieces, 1):
            if labels:
                piece = f"=== Turn {turn['turn']} (messages {span(turn)}, part {index} of {len(pieces)}) ===\n" + piece
            result.append({"turn": turn["turn"], "part": index, "parts": len(pieces),
                           "text": piece, "tokens": count(piece)})
    return result, truncated


def pack_chunks(parts, budget, count):
    """Greedily pack consecutive segments into chunks of at most ``budget`` tokens."""
    chunks, current, total = [], [], 0

    def close():
        nonlocal current, total
        carry = []
        text = "\n\n".join(s["text"] for s in current)
        while count(text) > budget and len(current) > 1:
            carry.insert(0, current.pop())
            text = "\n\n".join(s["text"] for s in current)
        if count(text) > budget:
            raise HierarchyError(f"Segment of turn {current[0]['turn']} exceeds the chunk budget")
        chunks.append({"segments": current, "text": text, "tokens": count(text)})
        current, total = carry, sum(s["tokens"] for s in carry)

    for part in parts:
        if current and total + part["tokens"] + 2 > budget:
            close()
        current.append(part)
        total += part["tokens"] + 2
    while current:
        close()
    return chunks


# --- prompts and verdicts ----------------------------------------------------

def with_plan_section(template, prompts, plan_text):
    """Insert the reference-plan block before the hidden objective, leaving ``{plan}`` to be formatted.

    The block is added to the *template* and the plan text is supplied afterwards as a
    ``format`` argument, so braces inside a plan can never be read as placeholders.
    """
    if plan_text is None:
        return template
    return template.replace(OBJECTIVE_MARKER, prompts["plan_section"] + OBJECTIVE_MARKER)


def chunk_prompt(prompts, scope, task, objective, text, index, total, plan_text=None):
    """The upstream prompt, plus our part notice when the transcript spans several chunks,
    plus the reference-plan block when ``plan_text`` is given."""
    template = prompts["upstream"][scope]
    if total > 1:
        notice = prompts["notice"].format(part=index + 1, parts=total)
        template = template.replace(TRANSCRIPT_MARKER, notice + TRANSCRIPT_MARKER)
    template = with_plan_section(template, prompts, plan_text)
    # str.format reads placeholders from the template only, never from substituted text.
    return template.format(input=task, task=objective, action=text, cot=text, plan=plan_text or "")


def parse_verdict(text):
    """Upstream's rule: the first ``<answer>X</answer>``; ``None`` when absent."""
    match = ANSWER.search(text or "")
    return match.group(1).upper() if match else None


def neutralize(text):
    """Replace answer tags in a chunk analysis so that only the combiner's own tag is parsed."""
    return ANSWER.sub(lambda m: f"[partial verdict: {m.group(1).upper()}]", text)


def reduce_prompt(prompts, task, objective, reports, plan_text=None):
    """``reports`` is a list of ``(first_turn, last_turn, text)`` in transcript order."""
    body = "\n\n".join(
        f"PARTIAL ANALYSIS {i} of {len(reports)} (covers turns {first}-{last}):\n{neutralize(text).strip()}"
        for i, (first, last, text) in enumerate(reports, 1))
    template = with_plan_section(prompts["reduce"], prompts, plan_text)
    return template.format(count=len(reports), input=task, task=objective, reports=body, plan=plan_text or "")


# --- planning and execution --------------------------------------------------

def plan(messages, params, count, prompts, objective=None, plan_text=None, turns_transform=None):
    """Offline level-0 plan: chunks and their exact prompts for one rollout and scope.

    ``objective`` overrides the side-objective text otherwise read from the system message
    (needed for control rollouts, whose system message has none, and for judging a rollout
    under the *other* objective). ``plan_text`` adds the reference-plan block to every prompt.
    ``turns_transform`` maps the list of turns to ``(turns, stats)`` before rendering; it is
    the hook for partial-CoT experiments, and its stats are returned.
    """
    check_params(params)
    task = main_task(messages)
    objective = hidden_objective(messages) if objective is None else objective
    rollout_turns = turns(messages)
    transform_stats = None
    if turns_transform is not None:
        rollout_turns, transform_stats = turns_transform(rollout_turns)
    parts, truncated = segments(rollout_turns, params, count)
    if not parts:
        raise HierarchyError(f"The {params['scope']} observation of this rollout is empty")
    # The prompt around a chunk has a fixed size for one rollout and scope.
    probe = chunk_prompt(prompts, params["scope"], task, objective, "", 0, 2, plan_text)
    overhead = count(probe) + 16
    room = input_limit(params) - overhead
    if params["chunk_tokens"] > room:
        raise HierarchyError(
            f"chunk_tokens={params['chunk_tokens']} plus {overhead} tokens of prompt exceeds the "
            f"{input_limit(params)}-token input limit; lower chunk_tokens to at most {room}")
    chunks = None
    if params["single_pass_if_fits"]:
        # Prefer the unmodified upstream prompt whenever the whole transcript fits it.
        whole, _ = segments(rollout_turns, {**params, "chunk_tokens": 10 ** 9}, count)
        text = "\n\n".join(piece["text"] for piece in whole)
        if count(chunk_prompt(prompts, params["scope"], task, objective, text, 0, 1, plan_text)) <= input_limit(params):
            chunks = [{"segments": whole, "text": text, "tokens": count(text)}]
    if chunks is None:
        chunks = pack_chunks(parts, params["chunk_tokens"], count)
    for index, chunk in enumerate(chunks):
        chunk["index"] = index
        chunk["first_turn"], chunk["last_turn"] = chunk["segments"][0]["turn"], chunk["segments"][-1]["turn"]
        chunk["prompt"] = chunk_prompt(prompts, params["scope"], task, objective, chunk["text"], index, len(chunks), plan_text)
        chunk["prompt_tokens"] = count(chunk["prompt"])
        if chunk["prompt_tokens"] > input_limit(params):
            raise HierarchyError(f"Chunk {index} prompt has {chunk['prompt_tokens']} tokens; limit {input_limit(params)}")
    return {"main_task": task, "objective": objective, "turn_count": len(rollout_turns),
            "truncated_tool_results": truncated, "chunks": chunks,
            "hierarchical": len(chunks) > 1, "partial_cot": transform_stats,
            "plan_text": plan_text}


def estimate_tree(chunk_count, bin_size):
    """Model calls and levels of a tree over ``chunk_count`` chunks, binning by count only.

    A bin holding a single node is carried upward without a call. Token budgets
    can only make bins smaller, so this is a lower bound on real calls.
    """
    calls, levels, nodes = chunk_count, 1, chunk_count
    while nodes > 1:
        full, rest = divmod(nodes, bin_size)
        calls += full + (1 if rest > 1 else 0)
        nodes = full + (1 if rest else 0)
        levels += 1
    return calls, levels


def estimate_tree_tokens(level0_prompt_tokens, chunk_count, bin_size, report_tokens, reduce_overhead):
    """Input tokens of every call in one tree: exact level 0 plus *estimated* combining levels.

    Combining calls read ``report_tokens`` (an assumption, unmeasured until a monitor runs) per analysis
    plus 32 tokens of header, and ``reduce_overhead`` tokens of fixed prompt.
    """
    total, nodes = level0_prompt_tokens, chunk_count
    while nodes > 1:
        full, rest = divmod(nodes, bin_size)
        total += full * (reduce_overhead + bin_size * (report_tokens + 32))
        if rest > 1:
            total += reduce_overhead + rest * (report_tokens + 32)
        nodes = full + (1 if rest else 0)
    return total


def make_bins(nodes, params, count, prompts, task, objective, plan_text=None):
    """Group consecutive nodes into bins of at most ``bin_size`` that fit the input limit."""
    overhead = count(reduce_prompt(prompts, task, objective, [(1, 1, "")], plan_text)) + 16
    limit = input_limit(params) - overhead
    bins, current, used = [], [], 0
    for node in nodes:
        cost = count(neutralize(node["text"])) + 32  # header lines of the combined prompt
        if cost > limit:
            raise HierarchyError(f"One partial analysis ({cost} tokens) cannot fit a combining prompt (room {limit})")
        if current and (len(current) >= params["bin_size"] or used + cost > limit):
            bins.append(current)
            current, used = [], 0
        current.append(node)
        used += cost
    if current:
        bins.append(current)
    return bins


def call_node(prompt, complete, params, seed):
    """Try a prompt up to ``max_attempts`` times; keep every attempt.

    An attempt is valid only when generation stopped normally and contains an
    A-D answer. Anything else is kept as a failure, never read as a negative
    verdict. Exceptions raised by ``complete`` (transport errors) propagate.
    """
    attempts = []
    for number in range(params["max_attempts"]):
        output = complete(prompt, seed + number)
        verdict = parse_verdict(output["text"])
        reason = None
        if output.get("finish_reason") != "stop":
            reason = f"finish_reason={output.get('finish_reason')!r}"
        elif verdict is None:
            reason = "no <answer>A-D</answer> in the response"
        attempts.append({"seed": seed + number, "valid": reason is None, "reason": reason,
                         "verdict": verdict, "finish_reason": output.get("finish_reason"),
                         "text": output["text"], "reasoning": output.get("reasoning"),
                         "usage": output.get("usage"),
                         "latency_seconds": output.get("latency_seconds")})
        if reason is None:
            return attempts, "complete", verdict, output["text"]
    return attempts, "invalid", None, attempts[-1]["text"]


def run_tree(rollout_id, level0, params, count, prompts, task, objective, complete, seed=0, plan_text=None):
    """Run chunk monitors, then combine bins level by level until one analysis remains.

    ``level0`` is ``plan(...)["chunks"]``. ``complete(prompt, seed)`` returns a
    dict with ``text`` (visible response), ``finish_reason`` and optionally
    ``reasoning`` and ``usage``. Every node of a level is run; if any is
    invalid the run ends with status ``invalid`` and verdict ``None`` and the
    next level is not run on partial data. ``calls`` counts nodes executed and
    ``model_requests`` counts requests including retries. Latency and token usage are
    summed from what ``complete`` reports (``latency_seconds`` and an OpenAI-style
    ``usage`` dict); ``critical_path_seconds`` is the sum over levels of the slowest node,
    which is the wall time if every level's nodes ran in parallel.
    """
    check_params(params)
    identity = {"rollout": rollout_id, "params": params}
    nodes, calls = [], 0

    def make(level, index, kind, children, first, last, prompt):
        nonlocal calls
        node = {"node_id": digest({**identity, "level": level, "index": index,
                                   "children": [c["node_id"] for c in children],
                                   "prompt": digest(prompt) if prompt else None}),
                "level": level, "index": index, "kind": kind,
                "children": [c["node_id"] for c in children], "first_turn": first, "last_turn": last}
        if prompt is not None:
            node["prompt_tokens"] = count(prompt)
            node["prompt_sha256"] = digest(prompt)
            attempts, status, verdict, text = call_node(prompt, complete, params, seed + calls * 10)
            calls += 1
            node.update(attempts=attempts, status=status, verdict=verdict, text=text)
        nodes.append(node)
        return node

    def finish(status, verdict, error=None):
        attempts = [a for n in nodes for a in n.get("attempts", ())]
        usage = lambda key: sum((a.get("usage") or {}).get(key) or 0 for a in attempts)
        latency = lambda a: a.get("latency_seconds") or 0.0
        per_level = {}
        for n in nodes:
            per_level[n["level"]] = max(per_level.get(n["level"], 0.0),
                                        sum(latency(a) for a in n.get("attempts", ())))
        return {"rollout_id": rollout_id, "scope": params["scope"], "params": params,
                "status": status, "verdict": verdict, "hierarchical": len(level0) > 1,
                "calls": calls, "nodes": nodes,
                "model_requests": len(attempts),
                "prompt_tokens": usage("prompt_tokens"), "completion_tokens": usage("completion_tokens"),
                "latency_seconds": sum(latency(a) for a in attempts),
                "critical_path_seconds": sum(per_level.values()),
                **({"error": error} if error else {})}

    current = [make(0, i, "chunk", [], c["first_turn"], c["last_turn"], c["prompt"]) for i, c in enumerate(level0)]
    level = 0
    while True:
        if any(n["status"] != "complete" for n in current):
            return finish("invalid", None)
        if len(current) == 1:
            return finish("complete", current[0]["verdict"])
        level += 1
        try:
            bins = make_bins(current, params, count, prompts, task, objective, plan_text)
        except HierarchyError as error:
            return finish("error", None, str(error))
        if all(len(b) == 1 for b in bins):
            return finish("error", None, "No progress: every bin holds one analysis")
        following = []
        for index, group in enumerate(bins):
            first, last = group[0]["first_turn"], group[-1]["last_turn"]
            if len(group) == 1:
                following.append(group[0])  # carried upward unchanged; no call
                continue
            prompt = reduce_prompt(prompts, task, objective,
                                   [(n["first_turn"], n["last_turn"], n["text"]) for n in group], plan_text)
            following.append(make(level, index, "reduce", group, first, last, prompt))
        current = following
