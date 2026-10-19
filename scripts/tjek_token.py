"""Hent et OAuth2-token fra Datafordeleren og vis kun metadata (aldrig tokenet)."""

import base64
import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

svar = httpx.post(
    os.environ["DATAFORDELER_TOKEN_URL"],
    data={
        "grant_type": "client_credentials",
        "client_id": os.environ["DATAFORDELER_CLIENT_ID"],
        "client_secret": os.environ["DATAFORDELER_CLIENT_SECRET"],
    },
)
print("HTTP", svar.status_code)

data = svar.json()
if svar.status_code != 200:
    print({k: v for k, v in data.items() if k in ("error", "error_description")})
    raise SystemExit(1)

print({k: v for k, v in data.items() if "token" not in k or k == "token_type"})

payload = data["access_token"].split(".")[1]
claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
print("claims:", sorted(claims))
print("aud:", claims.get("aud"), "| scope:", claims.get("scope"))
