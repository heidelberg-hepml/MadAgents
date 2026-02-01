import json
import os
from typing import Any, Optional

from madagents.backend.messages import (
    _is_ai_message,
    _is_tool_message,
    _message_additional_kwargs,
    _message_content,
    _message_name,
    _message_response_metadata,
    _message_tool_call_id,
    _message_usage_metadata,
)

#########################################################################
## Pricing and cost estimation #########################################
#########################################################################

PRICING_ENV_VAR = "MADAGENTS_PRICING_JSON"

DEFAULT_PRICING_TABLE = {
    "gpt-5": {
        "input_per_1m": 1.25,
        "cached_input_per_1m": 0.125,
        "output_per_1m": 10.0,
    },
    "gpt-5.1": {
        "input_per_1m": 1.25,
        "cached_input_per_1m": 0.125,
        "output_per_1m": 10.0,
    },
    "gpt-5.2": {
        "input_per_1m": 1.75,
        "cached_input_per_1m": 0.175,
        "output_per_1m": 14.0,
    },
    "gpt-5-mini": {
        "input_per_1m": 0.25,
        "cached_input_per_1m": 0.025,
        "output_per_1m": 2.0,
    },
    "gpt-5-nano": {
        "input_per_1m": 0.05,
        "cached_input_per_1m": 0.005,
        "output_per_1m": 0.4,
    },
    "web_search": {"tool_calls_per_1k": 10.0},
}


def _load_pricing_table() -> dict:
    pricing = {k: dict(v) for k, v in DEFAULT_PRICING_TABLE.items()}
    raw = os.environ.get(PRICING_ENV_VAR)
    if not raw:
        return pricing
    try:
        overrides = json.loads(raw)
    except Exception:
        return pricing
    if not isinstance(overrides, dict):
        return pricing
    for key, value in overrides.items():
        if not isinstance(value, dict):
            continue
        merged = dict(pricing.get(key, {}))
        merged.update(value)
        pricing[key] = merged
    return pricing


def _normalize_model_key(model: Optional[str], pricing: dict) -> Optional[str]:
    if not isinstance(model, str) or not model.strip():
        return None
    normalized = model.strip()
    if normalized.startswith("gpt-5") and "mini" in normalized:
        normalized = "gpt-5-mini"
    elif normalized.startswith("gpt-5") and "nano" in normalized:
        normalized = "gpt-5-nano"
    if normalized in pricing:
        return normalized
    candidates = [key for key in pricing.keys() if normalized.startswith(key)]
    if candidates:
        return max(candidates, key=len)
    return None


def _usage_input_tokens(usage: dict) -> Optional[int]:
    input_tokens = usage.get("input_tokens")
    if isinstance(input_tokens, (int, float)) and input_tokens >= 0:
        return int(input_tokens)
    total_tokens = usage.get("total_tokens")
    output_tokens = usage.get("output_tokens")
    if (
        isinstance(total_tokens, (int, float))
        and isinstance(output_tokens, (int, float))
        and total_tokens >= output_tokens
    ):
        return int(total_tokens - output_tokens)
    return None


def _usage_output_tokens(usage: dict) -> Optional[int]:
    output_tokens = usage.get("output_tokens")
    if isinstance(output_tokens, (int, float)) and output_tokens >= 0:
        return int(output_tokens)
    return None


def _usage_cache_read_tokens(usage: dict) -> int:
    details = usage.get("input_token_details") or {}
    if not isinstance(details, dict):
        return 0
    cache_read = details.get("cache_read", 0)
    if isinstance(cache_read, (int, float)) and cache_read >= 0:
        return int(cache_read)
    return 0


def _iter_tool_calls_from_content(content: Any) -> list[dict]:
    if not isinstance(content, list):
        return []
    calls = []
    for part in content:
        part_type = None
        if isinstance(part, dict):
            part_type = part.get("type")
        else:
            part_type = getattr(part, "type", None)
        if part_type in {"function_call", "tool_call"}:
            if isinstance(part, dict):
                name = part.get("name") or part.get("tool_name")
                call_id = part.get("call_id") or part.get("id")
            else:
                name = getattr(part, "name", None) or getattr(part, "tool_name", None)
                call_id = getattr(part, "call_id", None) or getattr(part, "id", None)
            calls.append({"name": name, "call_id": call_id})
    return calls


def _init_cost_breakdown() -> dict:
    return {
        "cached_input_cost_usd": 0.0,
        "input_cost_usd": 0.0,
        "output_cost_usd": 0.0,
        "output_reasoning_cost_usd": 0.0,
        "output_actual_cost_usd": 0.0,
        "web_search_cost_usd": 0.0,
    }


def _merge_cost_breakdown(base: dict, other: dict) -> dict:
    merged = dict(base)
    for key, value in other.items():
        if isinstance(value, (int, float)):
            merged[key] = merged.get(key, 0.0) + float(value)
    return merged


def _estimate_cost_for_batch(
    messages: list,
    pricing: dict,
    allow_missing_usage: bool = False,
) -> tuple[Optional[dict], bool]:
    costs = _init_cost_breakdown()
    web_search_call_ids: set[str] = set()
    web_search_anon_calls = 0

    for msg in messages:
        if _is_ai_message(msg):
            response_metadata = _message_response_metadata(msg)
            model = None
            if isinstance(response_metadata, dict):
                model = response_metadata.get("model") or response_metadata.get("model_name")
            # No model means we can't price this AIMessage; treat as zero-cost.
            if isinstance(model, str) and model.strip():
                usage = _message_usage_metadata(msg)
                if usage is None:
                    if allow_missing_usage:
                        return _init_cost_breakdown(), True
                    return None, False
                model_key = _normalize_model_key(model, pricing)
                if model_key is None:
                    return None, False
                rates = pricing.get(model_key) or {}
                input_rate = rates.get("input_per_1m")
                cached_rate = rates.get("cached_input_per_1m")
                output_rate = rates.get("output_per_1m")
                if not all(isinstance(v, (int, float)) for v in [input_rate, cached_rate, output_rate]):
                    return None, False
                input_tokens = _usage_input_tokens(usage)
                output_tokens = _usage_output_tokens(usage)
                if input_tokens is None or output_tokens is None:
                    return None, False
                cache_read = _usage_cache_read_tokens(usage)
                non_cached_input = max(input_tokens - cache_read, 0)
                cached_input_cost = (cache_read * float(cached_rate)) / 1_000_000.0
                input_cost = (non_cached_input * float(input_rate)) / 1_000_000.0
                output_cost = (output_tokens * float(output_rate)) / 1_000_000.0
                reasoning_tokens = 0
                output_details = usage.get("output_token_details") or {}
                if isinstance(output_details, dict):
                    reasoning_tokens = output_details.get("reasoning", 0)
                if not isinstance(reasoning_tokens, (int, float)) or reasoning_tokens < 0:
                    reasoning_tokens = 0
                reasoning_tokens = min(int(reasoning_tokens), output_tokens)
                actual_tokens = max(output_tokens - reasoning_tokens, 0)
                output_reasoning_cost = (reasoning_tokens * float(output_rate)) / 1_000_000.0
                output_actual_cost = (actual_tokens * float(output_rate)) / 1_000_000.0
                costs["cached_input_cost_usd"] += cached_input_cost
                costs["input_cost_usd"] += input_cost
                costs["output_cost_usd"] += output_cost
                costs["output_reasoning_cost_usd"] += output_reasoning_cost
                costs["output_actual_cost_usd"] += output_actual_cost

            for call in _iter_tool_calls_from_content(_message_content(msg)):
                name = call.get("name")
                if name != "web_search":
                    continue
                call_id = call.get("call_id")
                if call_id:
                    if call_id not in web_search_call_ids:
                        web_search_call_ids.add(call_id)
                else:
                    web_search_anon_calls += 1
        elif _is_tool_message(msg):
            name = _message_name(msg)
            if name != "web_search":
                continue
            call_id = _message_tool_call_id(msg)
            if call_id:
                if call_id not in web_search_call_ids:
                    web_search_call_ids.add(call_id)
            else:
                web_search_anon_calls += 1

    web_search_calls = len(web_search_call_ids) + web_search_anon_calls
    if web_search_calls > 0:
        tool_rates = pricing.get("web_search") or {}
        tool_rate = tool_rates.get("tool_calls_per_1k")
        if not isinstance(tool_rate, (int, float)):
            return None, False
        costs["web_search_cost_usd"] += web_search_calls * (float(tool_rate) / 1000.0)

    return costs, False


def _estimate_cost_from_state(
    values: dict,
) -> tuple[Optional[float], Optional[str], Optional[dict], Optional[dict]]:
    """
    Compute a run's estimated cost from state values.

    Returns (total_cost, note, breakdown, by_agent_breakdown).
    """
    if not isinstance(values, dict):
        return None, None, None, None
    messages = values.get("messages") or []
    if not isinstance(messages, list):
        return None, None, None, None

    agents_messages = values.get("agents_messages") or {}
    full_messages_map = {
        "orchestrator": values.get("orchestrator_full_messages") or {},
        "planner": values.get("planner_full_messages") or {},
        "plan_updater": values.get("plan_updater_full_messages") or {},
        "reviewer": values.get("reviewer_full_messages") or {},
    }
    pricing = _load_pricing_table()

    seen_message_ids: set[tuple[str, str]] = set()
    total_costs = _init_cost_breakdown()
    plan_updater_costs = _init_cost_breakdown()
    by_agent_costs: dict[str, dict] = {}
    plan_updater_missing = False

    for msg in messages:
        if not _is_ai_message(msg):
            continue
        agent_name = _message_name(msg)
        additional_kwargs = _message_additional_kwargs(msg)
        message_id = additional_kwargs.get("message_id") if isinstance(additional_kwargs, dict) else None
        if not agent_name:
            return None, None, None, None
        if not message_id:
            if agent_name == "plan_updater":
                plan_updater_missing = True
                continue
            return None, None, None, None
        key = (agent_name, message_id)
        if key in seen_message_ids:
            continue
        seen_message_ids.add(key)

        if agent_name == "plan_updater" and plan_updater_missing:
            continue

        batch = None
        agent_batches = agents_messages.get(agent_name)
        if isinstance(agent_batches, dict):
            batch = agent_batches.get(message_id)
        if batch is None and agent_name in full_messages_map:
            full_messages = full_messages_map.get(agent_name)
            if isinstance(full_messages, dict):
                full_msg = full_messages.get(message_id)
                if full_msg:
                    batch = [full_msg]
        if not isinstance(batch, list) or not batch:
            if agent_name == "plan_updater":
                plan_updater_missing = True
                continue
            return None, None, None, None

        if agent_name == "plan_updater":
            batch_costs, missing_usage = _estimate_cost_for_batch(
                batch,
                pricing,
                allow_missing_usage=True,
            )
            if batch_costs is None:
                return None, None, None, None
            if missing_usage:
                plan_updater_missing = True
                plan_updater_costs = _init_cost_breakdown()
            elif not plan_updater_missing:
                plan_updater_costs = _merge_cost_breakdown(plan_updater_costs, batch_costs)
        else:
            batch_costs, _ = _estimate_cost_for_batch(batch, pricing)
            if batch_costs is None:
                return None, None, None, None
            total_costs = _merge_cost_breakdown(total_costs, batch_costs)
            existing_agent_costs = by_agent_costs.get(agent_name, _init_cost_breakdown())
            by_agent_costs[agent_name] = _merge_cost_breakdown(existing_agent_costs, batch_costs)

    if not plan_updater_missing:
        total_costs = _merge_cost_breakdown(total_costs, plan_updater_costs)
        if any(value for value in plan_updater_costs.values()):
            existing_agent_costs = by_agent_costs.get("plan_updater", _init_cost_breakdown())
            by_agent_costs["plan_updater"] = _merge_cost_breakdown(existing_agent_costs, plan_updater_costs)
    note = "plan_updater not included" if plan_updater_missing else None
    total_cost = (
        total_costs["cached_input_cost_usd"]
        + total_costs["input_cost_usd"]
        + total_costs["output_cost_usd"]
        + total_costs["web_search_cost_usd"]
    )
    return total_cost, note, total_costs, by_agent_costs
