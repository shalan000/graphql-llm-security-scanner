import requests
from graphql import build_client_schema, parse, validate
from graphql.error import GraphQLSyntaxError

# Standard introspection query in the exact shape build_client_schema expects.
FULL_INTROSPECTION = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types { ...FullType }
    directives { name locations args { ...InputValue } }
  }
}
fragment FullType on __Type {
  kind name
  fields(includeDeprecated: true) {
    name args { ...InputValue }
    type { ...TypeRef } isDeprecated deprecationReason
  }
  inputFields { ...InputValue }
  interfaces { ...TypeRef }
  enumValues(includeDeprecated: true) { name isDeprecated deprecationReason }
  possibleTypes { ...TypeRef }
}
fragment InputValue on __InputValue {
  name type { ...TypeRef } defaultValue
}
fragment TypeRef on __Type {
  kind name
  ofType { kind name ofType { kind name ofType { kind name
    ofType { kind name ofType { kind name ofType { kind name ofType { kind name } } } } } } }
}
"""


def fetch_client_schema(target, headers=None):
    """Fetch the target's schema in a form graphql-core can validate against."""
    headers = headers or {"Content-Type": "application/json"}
    resp = requests.post(target, json={"query": FULL_INTROSPECTION},
                         headers=headers, timeout=15)
    introspection = resp.json()["data"]
    return build_client_schema(introspection)


def validate_query(query_string, client_schema):
    """
    Return a result dict for one query:
      {valid: bool, level: 'ok'|'syntax'|'schema', errors: [str]}
    """
    # Level 1: can it even be parsed as GraphQL?
    try:
        ast = parse(query_string)
    except GraphQLSyntaxError as e:
        return {"valid": False, "level": "syntax", "errors": [str(e)]}

    # Level 2: does it match the real schema (fields/args exist)?
    errors = validate(client_schema, ast)
    if errors:
        return {"valid": False, "level": "schema",
                "errors": [str(e) for e in errors]}

    return {"valid": True, "level": "ok", "errors": []}


def validate_batch(test_cases, client_schema):
    """
    Take the list of generated test cases, validate each one's `query`,
    and return them annotated plus a summary count.
    """
    valid_count = 0
    annotated = []
    for case in test_cases:
        result = validate_query(case.get("query", ""), client_schema)
        case = dict(case)
        case["validation"] = result
        annotated.append(case)
        if result["valid"]:
            valid_count += 1

    summary = {
        "total": len(test_cases),
        "valid": valid_count,
        "invalid": len(test_cases) - valid_count,
    }
    return annotated, summary


if __name__ == "__main__":
    import json
    TARGET = "http://localhost:5013/graphql"
    HEADERS = {"Content-Type": "application/json", "X-DVGA-MODE": "Beginner"}

    print("[*] Fetching schema for validation...")
    schema = fetch_client_schema(TARGET, HEADERS)
    print("[+] Schema ready")

    with open("test_cases.json", "r", encoding="utf-8") as fh:
        cases = json.load(fh)

    annotated, summary = validate_batch(cases, schema)

    print(f"\n{'='*60}")
    print(f"VALIDATION RESULTS: {summary['valid']}/{summary['total']} valid "
          f"({summary['invalid']} invalid)")
    print(f"{'='*60}\n")

    for c in annotated:
        v = c["validation"]
        mark = "VALID  " if v["valid"] else f"INVALID({v['level']})"
        print(f"[{mark}] {c.get('id')}: {c.get('query')}")
        if not v["valid"]:
            print(f"           reason: {v['errors'][0]}")

    with open("test_cases_validated.json", "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "cases": annotated}, fh, indent=2)
    print(f"\n[+] Saved annotated results to test_cases_validated.json")