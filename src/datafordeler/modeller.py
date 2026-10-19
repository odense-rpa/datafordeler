"""Typede modeller for data fra Datafordeleren.

Modellerne dækker de felter, som odense-rpa processerne faktisk bruger. De
udfyldes fra GraphQL-svar, når skemaet er på plads.
"""

from dataclasses import dataclass, field
from datetime import date

ODENSE_KOMMUNEKODE = "461"


def _uden_foranstillede_nuller(værdi: str | None) -> str | None:
    """Fjern foranstillede nuller, fx "012" -> "12". Tom streng bliver None."""
    if værdi is None:
        return None
    renset = værdi.strip().lstrip("0")
    return renset or None


@dataclass(frozen=True)
class Navn:
    fornavne: str
    efternavn: str
    mellemnavn: str | None = None

    @property
    def fuldt_navn(self) -> str:
        return " ".join(
            d for d in (self.fornavne, self.mellemnavn, self.efternavn) if d
        )


@dataclass(frozen=True)
class Adresse:
    """En persons CPR-adresse.

    husnummer, etage og kommunekode gemmes uden foranstillede nuller.
    sidedoer gemmes som i CPR, da SBSIP-formatet bruger den uændret.
    """

    vejadresseringsnavn: str
    husnummer: str | None
    postnummer: str
    postdistrikt: str
    kommunekode: str | None = None
    vejkode: str | None = None
    etage: str | None = None
    sidedoer: str | None = None
    gyldig_fra: date | None = None

    @property
    def er_ukendt(self) -> bool:
        return self.postdistrikt.strip().lower() == "ukendt"

    @property
    def har_fast_bopæl(self) -> bool:
        """Vejkoder 9900-9999 bruges i CPR til personer uden fast bopæl."""
        if self.vejkode is None or not self.vejkode.isdigit():
            return True
        return not 9900 <= int(self.vejkode) <= 9999

    def bor_i_kommune(self, kommunekode: str = ODENSE_KOMMUNEKODE) -> bool:
        return self.kommunekode == _uden_foranstillede_nuller(kommunekode)

    def formateret(self) -> str:
        """Adressen på én linje, fx "Vejnavn 12, 2 tv, 5000 Odense C"."""
        gade = " ".join(p for p in (self.vejadresseringsnavn, self.husnummer) if p)
        detalje = " ".join(
            p for p in (self.etage, _uden_foranstillede_nuller(self.sidedoer)) if p
        )
        by = " ".join(p for p in (self.postnummer, self.postdistrikt) if p)
        return ", ".join(p for p in (gade, detalje, by) if p)

    def sbsip_linjer(self, navn: str) -> list[str]:
        """Adresselinjer til sbsip send_digital_post: navn, gade og postnr + by."""
        postnr_by = f"{self.postnummer} {self.postdistrikt}"
        if self.er_ukendt:
            return [navn, self.vejadresseringsnavn, postnr_by]

        gade = f"{self.vejadresseringsnavn} {self.husnummer or ''}".rstrip()
        if self.etage:
            gade = f"{gade}, {self.etage}."
        if self.sidedoer:
            gade = f"{gade} {self.sidedoer}"
        return [navn, gade, postnr_by]

    def samme_adresse(self, anden: "Adresse") -> bool:
        """Sammenlign på kommune, vejkode, husnummer, etage og dør."""
        return (
            self.kommunekode,
            self.vejkode,
            self.husnummer,
            self.etage,
            self.sidedoer,
        ) == (
            anden.kommunekode,
            anden.vejkode,
            anden.husnummer,
            anden.etage,
            anden.sidedoer,
        )


@dataclass(frozen=True)
class Barn:
    cpr: str
    foedselsdato: date
    adresse: Adresse | None = None

    def alder(self, på_dato: date | None = None) -> int:
        dato = på_dato or date.today()
        før_fødselsdag = (dato.month, dato.day) < (
            self.foedselsdato.month,
            self.foedselsdato.day,
        )
        return dato.year - self.foedselsdato.year - før_fødselsdag


@dataclass(frozen=True)
class Person:
    """En person fra CPR med de oplysninger processerne bruger."""

    cpr: str
    status: str
    navn: Navn | None = None
    adresse: Adresse | None = None
    aegtefaelle_cpr: str | None = None
    boern: tuple[Barn, ...] = field(default_factory=tuple)
    foraeldremyndighed: tuple[str, ...] = field(default_factory=tuple)

    @property
    def er_død(self) -> bool:
        return self.status == "doed"

    @property
    def bor_i_danmark(self) -> bool:
        return self.status == "bopael_i_danmark"

    def sbsip_adresse(self) -> tuple[list[str], str]:
        """Adresselinjer og postnummer til sbsip send_digital_post.

        Raises:
            ValueError: Hvis personen ikke har en aktuel adresse.
        """
        if self.adresse is None:
            raise ValueError(f"Ingen aktuel adresse for CPR-nummer {self.cpr}")
        navn = self.navn.fuldt_navn if self.navn else ""
        return self.adresse.sbsip_linjer(navn), self.adresse.postnummer

    def hjemmeboende_børn_under_18(self, på_dato: date | None = None) -> list[Barn]:
        """Børn under 18 år, som bor på samme adresse som personen."""
        if self.adresse is None:
            return []
        return [
            barn
            for barn in self.boern
            if barn.alder(på_dato) < 18
            and barn.adresse is not None
            and barn.adresse.samme_adresse(self.adresse)
        ]


@dataclass(frozen=True)
class Produktionsenhed:
    pnummer: str
    navn: str | None = None
    status: str | None = None

    @property
    def er_aktiv(self) -> bool:
        return (self.status or "").lower() == "aktiv"


@dataclass(frozen=True)
class Virksomhed:
    cvr: str
    navn: str
    status: str
    produktionsenheder: tuple[Produktionsenhed, ...] = field(default_factory=tuple)

    @property
    def er_aktiv(self) -> bool:
        return self.status.lower() == "aktiv"

    def find_produktionsenhed(self, pnummer: str) -> Produktionsenhed | None:
        return next(
            (p for p in self.produktionsenheder if p.pnummer == str(pnummer)), None
        )
