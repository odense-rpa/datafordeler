"""Hent GraphQL-skemaer fra Datafordeleren og gem dem i docs/skema.

Introspection er slået fra, men skemaet kan hentes med GET <endpoint>/schema.

Brug:
    uv run python scripts/hent_skema.py
    uv run python scripts/hent_skema.py CVR/v2 CPR/custom/PublicSector/v3
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

from datafordeler import DatafordelerGraphQL
from datafordeler.graphql import CPR_REGISTER, CVR_REGISTER

SKEMA_MAPPE = Path(__file__).parent.parent / "docs" / "skema"

load_dotenv()

klient = DatafordelerGraphQL.fra_miljøvariabler()
for register in sys.argv[1:] or [CPR_REGISTER, CVR_REGISTER]:
    skema = klient.hent_skema(register)
    fil = SKEMA_MAPPE / f"{register.replace('/', '_').lower()}.graphql"
    fil.write_text(skema)
    print(
        f"{register}: {len(skema)} tegn -> {fil.relative_to(SKEMA_MAPPE.parent.parent)}"
    )
