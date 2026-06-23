import requests
import json

# Defaults are only a convenience for development. Override per target.
DEFAULT_TARGET = "http://localhost:5013/graphql"
DEFAULT_HEADERS = {"Content-Type": "application/json"}

# Full introspection query. This is standard GraphQL and works against any
# server that has introspection enabled. It pulls the query entry points with
# their arguments, plus every type and its fields.
INTROSPECTION_QUERY = """
{
  __schema {
    queryType { name }
    types {
      name
      kind
      fields {
        name
        args { name type { name kind ofType { name kind } } }
        type { name kind ofType { name kind } }
      }
    }
  }
}
"""


def get_schema(target=DEFAULT_TARGET, headers=None):
    """Ask any GraphQL target to describe itself. Returns the raw schema dict, or None."""
    headers = headers or DEFAULT_HEADERS
    print(f"[*] Requesting schema from {target}")
    try:
        resp = requests.post(target, json={"query": INTROSPECTION_QUERY},
                             headers=headers, timeout=15)
        data = resp.json()
        if "errors" in data:
            print(f"[-] Target returned errors: {data['errors']}")
            return None
        print("[+] Schema retrieved")
        return data["data"]["__schema"]
    except Exception as e:
        print(f"[-] Could not reach target: {e}")
        return None


def _type_name(type_ref):
    """GraphQL wraps types (NON_NULL, LIST). Unwrap to the underlying name."""
    if not type_ref:
        return "Unknown"
    return type_ref.get("name") or _type_name(type_ref.get("ofType"))


def extract_query_fields(schema):
    """
    Return the REAL query entry points for whatever target this schema came from.
    Each item: {name, args: [{name, type}], returns}.
    This is the list the LLM should build attacks from.
    """
    if not schema:
        return []
    query_type_name = (schema.get("queryType") or {}).get("name", "Query")
    fields = []
    for t in schema.get("types", []):
        if t.get("name") == query_type_name and t.get("fields"):
            for f in t["fields"]:
                fields.append({
                    "name": f["name"],
                    "args": [{"name": a["name"], "type": _type_name(a.get("type"))}
                             for a in (f.get("args") or [])],
                    "returns": _type_name(f.get("type")),
                })
    return fields


def extract_object_types(schema, limit_fields=12):
    """Return non-internal object types and their field names (the data shapes)."""
    if not schema:
        return []
    out = []
    for t in schema.get("types", []):
        name = t.get("name", "")
        if name.startswith("__"):           # skip GraphQL internals
            continue
        if t.get("kind") != "OBJECT":
            continue
        if not t.get("fields"):
            continue
        field_names = [f["name"] for f in t["fields"][:limit_fields]]
        out.append({"type": name, "fields": field_names})
    return out


def build_schema_summary(schema):
    """
    Produce a compact, prompt-ready text description of THIS target's schema.
    Generated from whatever schema is passed in, so it adapts to any target.
    """
    query_fields = extract_query_fields(schema)
    object_types = extract_object_types(schema)

    lines = ["AVAILABLE QUERY ENTRY POINTS (use ONLY these as top-level queries):"]
    if query_fields:
        for qf in query_fields:
            if qf["args"]:
                arg_str = ", ".join(f"{a['name']}: {a['type']}" for a in qf["args"])
            else:
                arg_str = "no arguments"
            lines.append(f"  - {qf['name']}({arg_str}) -> {qf['returns']}")
    else:
        lines.append("  (none found)")

    lines.append("")
    lines.append("OBJECT TYPES AND THEIR FIELDS (use these field names only):")
    for ot in object_types:
        lines.append(f"  - {ot['type']}: {', '.join(ot['fields'])}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Demo run against the default target. Swap target/headers for any other API.
    schema = get_schema()
    if schema:
        summary = build_schema_summary(schema)
        print("\n" + "=" * 60)
        print(summary)
        print("=" * 60)
        # Save it so the generator can read it
        with open("schema_summary.txt", "w", encoding="utf-8") as fh:
            fh.write(summary)
        print("\n[+] Saved prompt-ready summary to schema_summary.txt")