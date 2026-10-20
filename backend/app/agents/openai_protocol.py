"""Stateless Responses wire codec for the shared client; no tools execute here."""

import copy

REPLAY_ITEMS = "_openai_response_items"


def request_payload(
    model, messages, *, tools=(), json_mode=False, max_output_tokens=8192
):
    inputs = []
    for message in messages:
        role = message["role"]
        if role == "tool":
            inputs.append(
                {
                    "type": "function_call_output",
                    "call_id": message["tool_call_id"],
                    "output": message["content"],
                }
            )
        elif role == "assistant" and REPLAY_ITEMS in message:
            # Retain native calls and encrypted reasoning only in this request's
            # memory. Never store a response on the provider or render this state.
            inputs.extend(copy.deepcopy(message[REPLAY_ITEMS]))
        else:
            if message.get("content") is not None:
                inputs.append({"role": role, "content": message["content"]})
            for call in message.get("tool_calls", []):
                inputs.append(
                    {
                        "type": "function_call",
                        "call_id": call["id"],
                        "name": call["function"]["name"],
                        "arguments": call["function"]["arguments"],
                    }
                )
    payload = {
        "model": model,
        "input": inputs,
        "store": False,
        "reasoning": {"effort": "medium"},
        "include": ["reasoning.encrypted_content"],
        "max_output_tokens": max_output_tokens,
    }
    if tools:
        payload |= {
            "tools": [
                {"type": "function", **tool["function"], "strict": False}
                for tool in tools
            ],
            "tool_choice": "auto",
        }
        # strict:false preserves optional fields in the binding tool schemas.
        # The existing closed Pydantic registry strictly validates every call.
    if json_mode:
        payload["text"] = {"format": {"type": "json_object"}}
    return payload


def normalize_response(body):
    if not isinstance(body, dict) or body.get("status") != "completed":
        raise ValueError("INCOMPLETE_RESPONSE")
    output = body.get("output")
    if not isinstance(output, list) or not 1 <= len(output) <= 32:
        raise ValueError("INVALID_RESPONSE")
    calls, texts, replay = [], [], []
    for item in output:
        if not isinstance(item, dict):
            raise ValueError("INVALID_ITEM")
        kind = item.get("type")
        if item.get("status") not in (None, "completed"):
            raise ValueError("INCOMPLETE_ITEM")
        if kind == "reasoning":
            kept = {"type": kind, "summary": []}
            for key in ("id", "encrypted_content"):
                value = item.get(key)
                if value is not None:
                    if not isinstance(value, str):
                        raise ValueError("INVALID_REASONING_STATE")
                    kept[key] = value
            replay.append(kept)
        elif kind == "function_call":
            calls.append(
                {
                    "id": item["call_id"],
                    "type": "function",
                    "function": {
                        "name": item["name"],
                        "arguments": item["arguments"],
                    },
                }
            )
            replay.append(
                {
                    key: item[key]
                    for key in ("type", "id", "call_id", "name", "arguments", "status")
                    if key in item
                }
            )
        elif kind == "message":
            if item.get("role") != "assistant":
                raise ValueError("INVALID_ROLE")
            content = item.get("content")
            if not isinstance(content, list) or not 1 <= len(content) <= 32:
                raise ValueError("INVALID_CONTENT")
            kept_content = []
            for part in content:
                if (
                    not isinstance(part, dict)
                    or part.get("type") != "output_text"
                    or not isinstance(part.get("text"), str)
                ):
                    raise ValueError("INVALID_CONTENT")
                texts.append(part["text"])
                kept_content.append(
                    {"type": "output_text", "text": part["text"], "annotations": []}
                )
            kept = {
                key: item[key]
                for key in ("type", "id", "role", "status", "phase")
                if key in item
            }
            kept["content"] = kept_content
            replay.append(kept)
        else:
            # Hosted tools and other output types are outside our five-tool API.
            raise ValueError("UNSUPPORTED_OUTPUT")
    message = {"role": "assistant", "content": "".join(texts) or None}
    if calls:
        message["tool_calls"] = calls
    return {"choices": [{"message": message}]}, replay
