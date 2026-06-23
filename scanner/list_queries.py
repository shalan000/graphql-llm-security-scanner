import requests

TARGET = "http://localhost:5013/graphql"
HEADERS = {"Content-Type": "application/json", "X-DVGA-MODE": "Beginner"}

# This asks DVGA: "what query fields (doors) do you actually have?"
QUERY = """
{
  __schema {
    queryType {
      fields {
        name
        args { name }
      }
    }
  }
}
"""

r = requests.post(TARGET, json={"query": QUERY}, headers=HEADERS)
data = r.json()

fields = data["data"]["__schema"]["queryType"]["fields"]
print(f"DVGA has {len(fields)} real query fields (doors):\n")
for f in fields:
    arg_names = [a["name"] for a in f["args"]]
    args = ", ".join(arg_names) if arg_names else "no arguments"
    print(f"  {f['name']}({args})")