"""Klient til Datafordelerens GraphQL-API med OAuth2 client credentials.

Datafordeleren tillader kun ét rodfelt pr. forespørgsel og ingen aliaser, så
hver entitetstype hentes med sin egen forespørgsel.
"""

import os
import re
import time
from datetime import datetime, timezone
from itertools import batched
from typing import Any

import httpx

from .modeller import Produktionsenhed, Virksomhed

TOKEN_URL = (
    "https://auth.datafordeler.dk/realms/distribution/protocol/openid-connect/token"
)
GRAPHQL_URL = "https://graphql.datafordeler.dk"

# Filtrering med "in" tillader højst 100 værdier
_MAKS_IN_LISTE = 100


class DatafordelerFejl(Exception):
    """GraphQL-fejl returneret af Datafordeleren."""


def _virkningstid() -> str:
    """Nuværende tidspunkt i Datafordelerens DafDateTime-format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class DatafordelerGraphQL:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_url: str = TOKEN_URL,
        graphql_url: str = GRAPHQL_URL,
        timeout: float = 60,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._graphql_url = graphql_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)
        self._token: str | None = None
        self._token_udløber = 0.0

    @classmethod
    def fra_miljøvariabler(cls) -> "DatafordelerGraphQL":
        """Opret klienten ud fra DATAFORDELER_* miljøvariabler."""
        return cls(
            client_id=os.environ["DATAFORDELER_CLIENT_ID"],
            client_secret=os.environ["DATAFORDELER_CLIENT_SECRET"],
            token_url=os.environ.get("DATAFORDELER_TOKEN_URL", TOKEN_URL),
            graphql_url=os.environ.get("DATAFORDELER_GRAPHQL_URL", GRAPHQL_URL),
        )

    def _hent_token(self) -> str:
        # Forny et minut før udløb, så tokenet ikke udløber midt i et kald
        if self._token and time.monotonic() < self._token_udløber - 60:
            return self._token

        response = self._client.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["access_token"]
        self._token_udløber = time.monotonic() + data["expires_in"]
        return self._token

    def forespørg(
        self, register: str, query: str, variabler: dict[str, Any] | None = None
    ) -> dict:
        """Send en GraphQL-forespørgsel til et register, fx "CVR/v2".

        Returns:
            dict: Indholdet af "data" i svaret.
        Raises:
            DatafordelerFejl: Hvis svaret indeholder GraphQL-fejl.
        """
        response = self._client.post(
            f"{self._graphql_url}/{register}",
            json={"query": query, "variables": variabler or {}},
            headers={"Authorization": f"Bearer {self._hent_token()}"},
        )
        if response.headers.get("content-type", "").startswith("application/graphql"):
            data = response.json()
            if data.get("errors"):
                beskeder = "; ".join(f["message"] for f in data["errors"])
                raise DatafordelerFejl(f"{register}: {beskeder}")
            return data["data"]

        response.raise_for_status()
        return response.json()["data"]

    def _alle_noder(
        self, register: str, query: str, variabler: dict[str, Any]
    ) -> list[dict]:
        """Hent alle noder fra en forespørgsel med ét rodfelt, side for side.

        Forespørgslen skal tage $after og returnere pageInfo og nodes.
        """
        noder: list[dict] = []
        after = None
        while True:
            data = self.forespørg(register, query, {**variabler, "after": after})
            forbindelse = next(iter(data.values()))
            noder.extend(forbindelse["nodes"])
            if not forbindelse["pageInfo"]["hasNextPage"]:
                return noder
            after = forbindelse["pageInfo"]["endCursor"]

    def _hent_cvr_navne(self, enheds_ider: list[str], tid: str) -> dict[str, str]:
        """Aktuelle navne for CVR-enheder, slået op på enhedens id."""
        navne: dict[str, str] = {}
        for ider in batched(enheds_ider, _MAKS_IN_LISTE):
            noder = self._alle_noder(
                "CVR/v2",
                """query($ider: [String!], $t: DafDateTime, $after: String) {
                  CVR_Navn(virkningstid: $t, after: $after,
                           where: {CVREnhedsId: {in: $ider}}) {
                    pageInfo { hasNextPage endCursor }
                    nodes { CVREnhedsId vaerdi sekvens }
                  }
                }""",
                {"ider": list(ider), "t": tid},
            )
            for node in sorted(noder, key=lambda n: n["sekvens"]):
                navne.setdefault(node["CVREnhedsId"], node["vaerdi"])
        return navne

    def hent_virksomhed(self, cvr: str) -> Virksomhed:
        """Hent en virksomhed med navn, status og produktionsenheder.

        Raises:
            ValueError: Hvis CVR-nummeret er ugyldigt eller ikke findes.
        """
        if not re.match(r"^\d{8}$", cvr):
            raise ValueError(
                f"Ugyldigt CVR-nummer format: {cvr}. CVR skal være 8 numeriske cifre."
            )
        tid = _virkningstid()

        virksomheder = self._alle_noder(
            "CVR/v2",
            """query($cvr: Long!, $t: DafDateTime, $after: String) {
              CVR_Virksomhed(virkningstid: $t, after: $after,
                             where: {CVRNummer: {eq: $cvr}}) {
                pageInfo { hasNextPage endCursor }
                nodes { id status }
              }
            }""",
            {"cvr": int(cvr), "t": tid},
        )
        if not virksomheder:
            raise ValueError(f"Ingen virksomhed fundet med CVR-nummer {cvr}")
        virksomhed = virksomheder[0]

        enheder = self._alle_noder(
            "CVR/v2",
            """query($cvr: Long!, $t: DafDateTime, $after: String) {
              CVR_Produktionsenhed(virkningstid: $t, after: $after,
                                   where: {tilknyttetVirksomhedsCVRNummer: {eq: $cvr}}) {
                pageInfo { hasNextPage endCursor }
                nodes { id pNummer status }
              }
            }""",
            {"cvr": int(cvr), "t": tid},
        )

        navne = self._hent_cvr_navne(
            [virksomhed["id"], *(e["id"] for e in enheder)], tid
        )
        return Virksomhed(
            cvr=cvr,
            navn=navne.get(virksomhed["id"], ""),
            status=virksomhed["status"],
            produktionsenheder=tuple(
                Produktionsenhed(
                    pnummer=str(e["pNummer"]),
                    navn=navne.get(e["id"]),
                    status=e["status"],
                )
                for e in enheder
            ),
        )
