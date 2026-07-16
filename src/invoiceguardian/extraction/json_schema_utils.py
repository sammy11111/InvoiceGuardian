"""Inlines Pydantic's `$defs`/`$ref` output into a flat JSON schema.

Anthropic's tool `input_schema` is safest as a self-contained schema with no
`$ref` indirection, so this resolves Pydantic v2's default `$defs`-based
output before it's used as a tool schema.
"""

from __future__ import annotations

from typing import Any


def resolve_refs(schema: dict[str, Any]) -> dict[str, Any]:
    defs = schema.get("$defs", {})

    def _resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref_name = node["$ref"].rsplit("/", maxsplit=1)[-1]
                resolved = _resolve(defs[ref_name])
                extra = {k: v for k, v in node.items() if k != "$ref"}
                return {**resolved, **extra}
            return {k: _resolve(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [_resolve(v) for v in node]
        return node

    return _resolve(schema)
