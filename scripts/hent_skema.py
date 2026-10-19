"""Hent GraphQL-skemaet via introspection og gem det i schema.json."""

import json
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

INTROSPECTION = """
query {
  __schema {
    queryType { name }
    types {
      kind name description
      fields { name description args { name type { ...T } } type { ...T } }
      inputFields { name type { ...T } }
      enumValues { name description }
    }
  }
}
fragment T on __Type {
  kind name ofType { kind name ofType { kind name ofType { kind name } } }
}
"""

token = httpx.post(
    os.environ["DATAFORDELER_TOKEN_URL"],
    data={
        "grant_type": "client_credentials",
        "client_id": os.environ["DATAFORDELER_CLIENT_ID"],
        "client_secret": os.environ["DATAFORDELER_CLIENT_SECRET"],
    },
).json()["access_token"]

svar = httpx.post(
    os.environ["DATAFORDELER_GRAPHQL_URL"],
    json={"query": INTROSPECTION},
    headers={"Authorization": f"Bearer {token}"},
    timeout=60,
)
print("HTTP", svar.status_code)
if svar.status_code != 200 or "errors" in svar.json():
    print(svar.text[:2000])
    sys.exit(1)

skema = svar.json()["data"]["__schema"]
with open("schema.json", "w") as f:
    json.dump(skema, f, indent=1, ensure_ascii=False)

typer = {t["name"]: t for t in skema["types"]}
rod = typer[skema["queryType"]["name"]]
print(len(skema["types"]), "typer,", len(rod["fields"]), "rodfelter")
for felt in rod["fields"]:
    print(" ", felt["name"])
