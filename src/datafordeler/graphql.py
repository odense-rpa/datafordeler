"""Klient til Datafordelerens GraphQL-API med OAuth2 client credentials.

Datafordeleren tillader kun ét rodfelt pr. forespørgsel og ingen aliaser, så
hver entitetstype hentes med sin egen forespørgsel.
"""

import re
import time
from datetime import datetime, timezone
from itertools import batched
from typing import Any

import httpx

from .modeller import Person, Produktionsenhed, Virksomhed

TOKEN_URL = (
    "https://auth.datafordeler.dk/realms/distribution/protocol/openid-connect/token"
)
GRAPHQL_URL = "https://graphql.datafordeler.dk"

CPR_REGISTER = "CPR/custom/PublicSector/v2"
CVR_REGISTER = "CVR/v2"

# Filtrering med "in" tillader højst 100 værdier
_MAKS_IN_LISTE = 100

# Beskyttelser skal altid vælges på personer og relaterede personer.
# Lister filtreret med where skal også vælge status, ellers matcher filteret intet.
_BESKYTTELSER = "beskyttelser { beskyttelsestype status virkningfra virkningtil }"
_ADRESSE = """status virkningfra
  cprAdresse { cprkommunekode cprvejkode vejadresseringsnavn husnummer etage
               sidedoer postnummer postdistrikt }"""
_PERSON_QUERY = f"""query($pnr: String!) {{
  CPRCustom_PublicSectorPerson(input: {{personnummer: {{personnummer: {{eq: $pnr}}}}}}) {{
    nodes {{
      status foedselsdato
      {_BESKYTTELSER}
      navne(where: {{status: {{eq: "aktuel"}}}}) {{ status fornavne mellemnavn efternavn }}
      adresseoplysninger(where: {{status: {{eq: "aktuel"}}}}) {{ {_ADRESSE} }}
      civilstande(where: {{status: {{eq: "aktuel"}}}}) {{
        status civilstandstype aegtefaelle {{ personnummer {_BESKYTTELSER} }}
      }}
      boern {{
        barn {{ personnummer {_BESKYTTELSER} adresseoplysninger {{ {_ADRESSE} }} }}
      }}
      foraeldremyndighedsoplysninger {{
        virkningtil foraeldremyndig {{ personnummer {_BESKYTTELSER} }}
      }}
    }}
  }}
}}"""


class DatafordelerFejl(Exception):
    """GraphQL-fejl returneret af Datafordeleren."""


def _virkningstid() -> str:
    """Nuværende tidspunkt i Datafordelerens DafDateTime-format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class DatafordelerGraphQL:
    """Klient til Datafordelerens GraphQL-API.

    Args:
        client_id: Client id fra Datafordelerens administrationsportal.
        client_secret: Client secret til samme IT-system.
    """

    def __init__(self, client_id: str, client_secret: str, timeout: float = 60):
        self._client_id = client_id
        self._client_secret = client_secret
        self._client = httpx.Client(timeout=timeout)
        self._token: str | None = None
        self._token_udløber = 0.0

    def _hent_token(self) -> str:
        # Forny et minut før udløb, så tokenet ikke udløber midt i et kald
        if self._token and time.monotonic() < self._token_udløber - 60:
            return self._token

        response = self._client.post(
            TOKEN_URL,
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

    def _send(self, metode: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send et kald med token. Ved 401 hentes et nyt token, og kaldet prøves igen.

        Tokenet kan være ugyldigt før beregnet udløb, fx efter rotation af secret
        eller hvis maskinen har været i dvale.
        """
        for forsøg in range(2):
            response = self._client.request(
                metode,
                url,
                headers={"Authorization": f"Bearer {self._hent_token()}"},
                **kwargs,
            )
            if response.status_code != 401 or forsøg == 1:
                return response
            self._token = None
        return response

    def forespørg(
        self, register: str, query: str, variabler: dict[str, Any] | None = None
    ) -> dict:
        """Send en GraphQL-forespørgsel til et register, fx "CVR/v2".

        Returns:
            dict: Indholdet af "data" i svaret.
        Raises:
            DatafordelerFejl: Hvis svaret indeholder GraphQL-fejl.
        """
        response = self._send(
            "POST",
            f"{GRAPHQL_URL}/{register}",
            json={"query": query, "variables": variabler or {}},
        )
        if response.headers.get("content-type", "").startswith("application/graphql"):
            data = response.json()
            if data.get("errors"):
                beskeder = "; ".join(f["message"] for f in data["errors"])
                raise DatafordelerFejl(f"{register}: {beskeder}")
            return data["data"]

        response.raise_for_status()
        return response.json()["data"]

    def hent_skema(self, register: str) -> str:
        """Hent GraphQL-skemaet (SDL) for et register, fx "CVR/v2"."""
        response = self._send("GET", f"{GRAPHQL_URL}/{register}/schema")
        response.raise_for_status()
        return response.text

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
                CVR_REGISTER,
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
            CVR_REGISTER,
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
            CVR_REGISTER,
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

    def hent_person(self, cpr: str) -> Person:
        """Hent en person fra CPR med aktuelt navn, adresse og familierelationer.

        Raises:
            ValueError: Hvis CPR-nummeret er ugyldigt eller ikke findes.
        """
        if not re.match(r"^\d{10}$", cpr):
            raise ValueError(
                "Ugyldigt CPR-nummer format. CPR skal være 10 numeriske cifre."
            )
        data = self.forespørg(CPR_REGISTER, _PERSON_QUERY, {"pnr": cpr})
        noder = data["CPRCustom_PublicSectorPerson"]["nodes"]
        if not noder:
            raise ValueError("Ingen person fundet med det angivne CPR-nummer")
        return Person.fra_graphql(cpr, noder[0])
