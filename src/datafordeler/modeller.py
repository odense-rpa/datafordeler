"""Typede modeller for data fra Datafordeleren.

Modellerne dækker de felter, som odense-rpa processerne faktisk bruger. De
udfyldes fra GraphQL-svar via fra_graphql().
"""

from dataclasses import dataclass, field
from datetime import date

ODENSE_KOMMUNEKODE = "461"
NAVNE_OG_ADRESSEBESKYTTELSE = "navne_og_adresse"


def _uden_foranstillede_nuller(værdi: str | None) -> str | None:
    """Fjern foranstillede nuller, fx "012" -> "12". Tom streng bliver None."""
    if værdi is None:
        return None
    renset = værdi.strip().lstrip("0")
    return renset or None


def _dato(værdi: str | None) -> date | None:
    return date.fromisoformat(værdi[:10]) if værdi else None


def _fødselsdato_fra_cpr(cpr: str) -> date:
    """Fødselsdato ud fra CPR-nummeret efter CPR-kontorets århundrederegel."""
    dag, måned, år, løbenr = int(cpr[0:2]), int(cpr[2:4]), int(cpr[4:6]), int(cpr[6])
    if løbenr <= 3:
        århundrede = 1900
    elif løbenr in (4, 9):
        århundrede = 2000 if år <= 36 else 1900
    else:
        århundrede = 2000 if år <= 57 else 1800
    return date(århundrede + år, måned, dag)


def _aktive_beskyttelser(beskyttelser: list[dict]) -> tuple[str, ...]:
    i_dag = date.today()
    return tuple(
        b["beskyttelsestype"]
        for b in beskyttelser
        if (b.get("status") or "").lower() == "aktuel"
        and (_dato(b.get("virkningtil")) or date.max) > i_dag
    )


@dataclass(frozen=True)
class Navn:
    fornavne: str
    efternavn: str
    mellemnavn: str | None = None

    @classmethod
    def fra_graphql(cls, node: dict) -> "Navn":
        return cls(
            fornavne=node["fornavne"],
            efternavn=node["efternavn"],
            mellemnavn=node.get("mellemnavn") or None,
        )

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

    @classmethod
    def fra_graphql(cls, adresseoplysning: dict) -> "Adresse":
        """Byg en Adresse fra en CPRCustom_PublicSectorAdresseoplysninger-node."""
        a = adresseoplysning["cprAdresse"]
        return cls(
            vejadresseringsnavn=(a.get("vejadresseringsnavn") or "").strip(),
            husnummer=_uden_foranstillede_nuller(a.get("husnummer")),
            postnummer=(a.get("postnummer") or "").strip(),
            postdistrikt=(a.get("postdistrikt") or "").strip(),
            kommunekode=_uden_foranstillede_nuller(a.get("cprkommunekode")),
            vejkode=_uden_foranstillede_nuller(a.get("cprvejkode")),
            etage=_uden_foranstillede_nuller(a.get("etage")),
            sidedoer=(a.get("sidedoer") or "").strip() or None,
            gyldig_fra=_dato(adresseoplysning.get("virkningfra")),
        )

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

    @classmethod
    def fra_graphql(cls, node: dict) -> "Barn":
        """Byg et Barn fra en CPRCustom_PublicSectorSimpelPerson-node.

        Noden har ingen fødselsdato, så den udledes af CPR-nummeret.
        """
        adresse = node.get("adresseoplysninger")
        aktuel = adresse and (adresse.get("status") or "aktuel").lower() == "aktuel"
        return cls(
            cpr=node["personnummer"],
            foedselsdato=_fødselsdato_fra_cpr(node["personnummer"]),
            adresse=Adresse.fra_graphql(adresse) if aktuel else None,
        )

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
    foedselsdato: date | None = None
    navn: Navn | None = None
    adresse: Adresse | None = None
    aegtefaelle_cpr: str | None = None
    boern: tuple[Barn, ...] = field(default_factory=tuple)
    foraeldremyndighed: tuple[str, ...] = field(default_factory=tuple)
    beskyttelser: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def fra_graphql(cls, cpr: str, node: dict) -> "Person":
        """Byg en Person fra en CPRCustom_PublicSectorPerson-node.

        Forventer at navne, adresseoplysninger og civilstande allerede er
        filtreret til status "aktuel" i forespørgslen.
        """
        navne = node.get("navne") or []
        adresser = node.get("adresseoplysninger") or []
        aegtefaelle = next(
            (
                c["aegtefaelle"]["personnummer"]
                for c in node.get("civilstande") or []
                if c.get("civilstandstype", "").lower() == "gift"
                and c.get("aegtefaelle")
            ),
            None,
        )
        i_dag = date.today()
        return cls(
            cpr=cpr,
            status=node["status"],
            foedselsdato=_dato(node.get("foedselsdato")),
            navn=Navn.fra_graphql(navne[0]) if navne else None,
            adresse=Adresse.fra_graphql(adresser[0]) if adresser else None,
            aegtefaelle_cpr=aegtefaelle,
            boern=tuple(
                Barn.fra_graphql(b["barn"])
                for b in node.get("boern") or []
                if b.get("barn")
            ),
            foraeldremyndighed=tuple(
                f["foraeldremyndig"]["personnummer"]
                for f in node.get("foraeldremyndighedsoplysninger") or []
                if f.get("foraeldremyndig")
                and (_dato(f.get("virkningtil")) or date.max) > i_dag
            ),
            beskyttelser=_aktive_beskyttelser(node.get("beskyttelser") or []),
        )

    @property
    def har_navne_og_adressebeskyttelse(self) -> bool:
        """Aktiv navne- og adressebeskyttelse (ikke kun vejviser/markedsføring)."""
        return NAVNE_OG_ADRESSEBESKYTTELSE in self.beskyttelser

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
