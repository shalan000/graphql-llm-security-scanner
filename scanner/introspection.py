import requests
import json

TARGET = "http://localhost:5013/graphql"

HEADERS = {
    "Content-Type": "application/json",
    "X-DVGA-MODE": "Beginner"
}

INTROSPECTION_QUERY = """
{
  __schema {
    types {
      name
      fields {
        name
        type {
          name
        }
      }
    }
  }
}
"""

def get_schema(target=TARGET):
    print(f"[*] Sending introspection query to {target}")
    try:
        response = requests.post(
            target,
            json={"query": INTROSPECTION_QUERY},
            headers=HEADERS
        )
        data = response.json()
        if "errors" in data:
            print(f"[-] Error: {data['errors']}")
            return None
        print("[+] Schema retrieved successfully!")
        return data
    except Exception as e:
        print(f"[-] Failed: {e}")
        return None

if __name__ == "__main__":
    schema = get_schema()
    if schema:
        types = schema["data"]["__schema"]["types"]
        print(f"\n[+] Found {len(types)} types in schema:")
        for t in types:
            if not t["name"].startswith("__"):
                print(f"    - {t['name']}")