"""Thin httpx wrapper over the Anthropic Messages API for structured
(tool-use) extraction calls.

CLAUDE.md locks httpx (not the `anthropic` SDK) as the stack's HTTP client,
so this is a small hand-rolled client rather than a pulled-in dependency.

Implements SCORING.md's retry policy for this step: retry only after a
schema-validation failure, one retry maximum, using the same fixed repair
message for every model — never retry because a semantic answer looks
wrong.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"

_REPO_ROOT = Path(__file__).resolve().parents[3]


class SchemaValidationFailure(Exception):
    """A tool-use response failed schema validation on the initial call and
    the one allowed retry (SCORING.md retry policy)."""


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_api_key() -> str:
    _load_dotenv(_REPO_ROOT / ".env")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set (checked the environment and a repo-root .env file)"
        )
    return key


@dataclass(frozen=True)
class ToolCallResponse:
    tool_use_id: str
    tool_input: dict[str, Any]
    raw_content: list[dict[str, Any]]
    input_tokens: int
    output_tokens: int


def _call_tool(
    *,
    model: str,
    system: str,
    messages: list[dict[str, Any]],
    tool_name: str,
    tool_description: str,
    input_schema: dict[str, Any],
    max_tokens: int,
    timeout: float,
) -> ToolCallResponse:
    response = httpx.post(
        ANTHROPIC_API_URL,
        json={
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "tools": [
                {
                    "name": tool_name,
                    "description": tool_description,
                    "input_schema": input_schema,
                }
            ],
            "tool_choice": {"type": "tool", "name": tool_name},
        },
        headers={
            "x-api-key": get_api_key(),
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    tool_use = next(block for block in data["content"] if block["type"] == "tool_use")
    usage = data.get("usage", {})
    return ToolCallResponse(
        tool_use_id=tool_use["id"],
        tool_input=tool_use["input"],
        raw_content=data["content"],
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
    )


_REPAIR_MESSAGE = (
    "Your previous tool call did not match the required schema. Validation error: "
    "{error}\n\nCall the tool again with corrected input that satisfies the schema "
    "exactly. Do not change any value you are confident about — only fix what the "
    "validation error identifies."
)


def call_tool_validated[T: BaseModel](
    *,
    model: str,
    system: str,
    user_content: str,
    tool_name: str,
    tool_description: str,
    input_schema: dict[str, Any],
    raw_model: type[T],
    max_tokens: int = 4096,
    timeout: float = 90.0,
) -> tuple[T, bool, int, int]:
    """Calls `tool_name`, validates the response against `raw_model`, and
    retries once (with a repair message) on validation failure.

    Returns (validated_result, retried, total_input_tokens, total_output_tokens).
    Raises SchemaValidationFailure if the retry also fails validation.
    """
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]
    first = _call_tool(
        model=model,
        system=system,
        messages=messages,
        tool_name=tool_name,
        tool_description=tool_description,
        input_schema=input_schema,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    try:
        return (
            raw_model.model_validate(first.tool_input),
            False,
            first.input_tokens,
            first.output_tokens,
        )
    except ValidationError as first_error:
        messages = [
            *messages,
            {"role": "assistant", "content": first.raw_content},
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": first.tool_use_id,
                        "is_error": True,
                        "content": _REPAIR_MESSAGE.format(error=str(first_error)),
                    }
                ],
            },
        ]
        retry = _call_tool(
            model=model,
            system=system,
            messages=messages,
            tool_name=tool_name,
            tool_description=tool_description,
            input_schema=input_schema,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        try:
            validated = raw_model.model_validate(retry.tool_input)
        except ValidationError as retry_error:
            raise SchemaValidationFailure(
                f"{tool_name} failed schema validation on the initial call and the "
                f"one allowed retry. Retry error: {retry_error}"
            ) from retry_error
        total_input = first.input_tokens + retry.input_tokens
        total_output = first.output_tokens + retry.output_tokens
        return validated, True, total_input, total_output
