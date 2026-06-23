from introspection import get_schema, build_schema_summary

import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"

BOLA_PROMPT = """You are a GraphQL penetration tester specialising in Broken Object Level Authorisation (BOLA/IDOR).

The target's real schema is described below:
{schema}

Generate {n} attack test cases targeting BOLA vulnerabilities.
Rules:
- Use ONLY the query entry points listed above as top-level queries. Do not invent fields.
- Use ONLY the argument names each entry point actually accepts.
- Use ONLY field names listed under each object type.
- Attempt to access objects belonging to another user by manipulating ID-like arguments (try 2, 3, 999).
- Prioritise entry points returning sensitive fields (password, token, content, gqlquery).
- Every query must be valid, executable GraphQL. Never use "..." or placeholders.

Respond ONLY with a valid JSON array. No explanation. No markdown. No code fences.
Each object must have exactly these keys: id, attack_class, target_type, target_field, query, rationale, expected_indicator.

Example (format only; use the real schema above for actual queries):
[{{"id":"bola_001","attack_class":"BOLA","target_type":"UserObject","target_field":"password","query":"{{ users(id: 2) {{ username password }} }}","rationale":"Attempts horizontal access to another user's record via the users entry point","expected_indicator":"200 with another user's data"}}]
"""

RESOURCE_EXHAUSTION_PROMPT = """You are a GraphQL penetration tester specialising in resource exhaustion attacks.

The target's real schema is described below:
{schema}

Generate {n} attack test cases targeting resource exhaustion.
Techniques to use:
- Nested query depth abuse: follow real relationships between object types to nest deeply (e.g. an object that returns another object that returns the first). Use the fields listed under each type to chain them.
- Field duplication: repeat a real field many times in one query.
- Aliased query flooding: request the same real entry point many times using GraphQL aliases (a1: paste(...) a2: paste(...)).

Rules:
- Use ONLY the query entry points and field names from the schema above.
- A nested-depth case MUST actually be nested across real relationships, not a flat query.
- Every query must be valid, executable GraphQL. Never use "..." or placeholders.

Respond ONLY with a valid JSON array. No explanation. No markdown. No code fences.
Each object must have exactly these keys: id, attack_class, target_type, target_field, query, rationale, expected_indicator.
"""

def query_ollama(prompt: str) -> str:
    response = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2
        }
    })
    response.raise_for_status()
    return response.json()["response"]

def parse_llm_output(raw: str) -> list:
    raw = raw.strip()
    # Strip markdown fences if model ignores instructions
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue
    return json.loads(raw)

def generate_attack_queries(schema: dict, attack_class: str, n: int = 5) -> list:
    schema_str = build_schema_summary(schema)
    
    if attack_class == "BOLA":
        prompt = BOLA_PROMPT.format(schema=schema_str, n=n)
    elif attack_class == "resource_exhaustion":
        prompt = RESOURCE_EXHAUSTION_PROMPT.format(schema=schema_str, n=n)
    else:
        raise ValueError(f"Unknown attack class: {attack_class}")
    
    print(f"[*] Sending {attack_class} prompt to Llama 3...")
    raw = query_ollama(prompt)
    
    print(f"[*] Raw response received, parsing...")
    try:
        cases = parse_llm_output(raw)
        print(f"[+] Parsed {len(cases)} test cases")
        return cases
    except json.JSONDecodeError as e:
        print(f"[-] JSON parse failed: {e}")
        print(f"[!] Raw output was:\n{raw}")
        return []

if __name__ == "__main__":
    from introspection import get_schema

    schema = get_schema()
    
    bola_cases = generate_attack_queries(schema, "BOLA", n=5)
    re_cases = generate_attack_queries(schema, "resource_exhaustion", n=5)
    
    all_cases = bola_cases + re_cases
    
    with open("test_cases.json", "w") as f:
        json.dump(all_cases, f, indent=2)
    
    print(f"\n[+] Total test cases generated: {len(all_cases)}")
    print("[+] Saved to test_cases.json")