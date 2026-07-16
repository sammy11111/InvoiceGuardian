"""Direct tests for the $ref-inlining transform used to build tool schemas."""

from __future__ import annotations

from invoiceguardian.extraction.json_schema_utils import resolve_refs
from invoiceguardian.extraction.raw_schemas import RawContractExtraction


def _find_refs(node: object) -> bool:
    if isinstance(node, dict):
        if "$ref" in node:
            return True
        return any(_find_refs(v) for v in node.values())
    if isinstance(node, list):
        return any(_find_refs(v) for v in node)
    return False


def test_resolve_refs_inlines_a_simple_ref_and_drops_defs() -> None:
    schema = {
        "type": "object",
        "properties": {"source": {"$ref": "#/$defs/Source"}},
        "$defs": {
            "Source": {
                "type": "object",
                "properties": {"page": {"type": "integer"}},
            }
        },
    }
    resolved = resolve_refs(schema)

    assert "$defs" not in resolved
    assert resolved["properties"]["source"] == {
        "type": "object",
        "properties": {"page": {"type": "integer"}},
    }


def test_resolve_refs_merges_sibling_keys_alongside_a_ref() -> None:
    schema = {
        "properties": {
            "source": {"$ref": "#/$defs/Source", "description": "provenance"},
        },
        "$defs": {"Source": {"type": "object"}},
    }
    resolved = resolve_refs(schema)
    assert resolved["properties"]["source"] == {"type": "object", "description": "provenance"}


def test_resolve_refs_handles_nested_refs() -> None:
    schema = {
        "properties": {"outer": {"$ref": "#/$defs/Outer"}},
        "$defs": {
            "Outer": {"properties": {"inner": {"$ref": "#/$defs/Inner"}}},
            "Inner": {"type": "string"},
        },
    }
    resolved = resolve_refs(schema)
    assert resolved["properties"]["outer"]["properties"]["inner"] == {"type": "string"}
    assert not _find_refs(resolved)


def test_resolve_refs_on_real_pydantic_schema_leaves_no_refs() -> None:
    raw = RawContractExtraction.model_json_schema()
    assert _find_refs(raw)  # pydantic emits $defs/$ref by default
    resolved = resolve_refs(raw)
    assert not _find_refs(resolved)
    assert "$defs" not in resolved
    # A nested object property is fully inlined and still usable as a schema.
    rate_items = resolved["properties"]["rate_card"]["items"]
    assert rate_items["type"] == "object"
    assert "role" in rate_items["properties"]
