from datetime import date

import pytest

from datafordeler import Adresse, Barn, Navn, Person, Produktionsenhed, Virksomhed


def lav_adresse(**ændringer) -> Adresse:
    felter = dict(
        vejadresseringsnavn="Flakhaven",
        husnummer="2",
        postnummer="5000",
        postdistrikt="Odense C",
        kommunekode="461",
        vejkode="1234",
    )
    felter.update(ændringer)
    return Adresse(**felter)


def lav_person(**ændringer) -> Person:
    felter = dict(
        cpr="0101901234",
        status="bopael_i_danmark",
        navn=Navn(fornavne="Anne", mellemnavn="Marie", efternavn="Hansen"),
        adresse=lav_adresse(),
    )
    felter.update(ændringer)
    return Person(**felter)


def test_fuldt_navn_uden_mellemnavn():
    assert Navn(fornavne="Anne", efternavn="Hansen").fuldt_navn == "Anne Hansen"


def test_formateret_adresse():
    adresse = lav_adresse(etage="2", sidedoer="tv")
    assert adresse.formateret() == "Flakhaven 2, 2 tv, 5000 Odense C"


def test_formateret_adresse_uden_etage():
    assert lav_adresse().formateret() == "Flakhaven 2, 5000 Odense C"


def test_sbsip_adresse():
    person = lav_person(adresse=lav_adresse(etage="2", sidedoer="tv"))
    linjer, postnr = person.sbsip_adresse()
    assert linjer == ["Anne Marie Hansen", "Flakhaven 2, 2. tv", "5000 Odense C"]
    assert postnr == "5000"


def test_sbsip_adresse_ukendt():
    adresse = lav_adresse(
        vejadresseringsnavn="Ukendt adresse", postnummer="9999", postdistrikt="Ukendt"
    )
    linjer, postnr = lav_person(adresse=adresse).sbsip_adresse()
    assert linjer == ["Anne Marie Hansen", "Ukendt adresse", "9999 Ukendt"]
    assert postnr == "9999"


def test_sbsip_adresse_uden_adresse_fejler():
    with pytest.raises(ValueError, match="Ingen aktuel adresse"):
        lav_person(adresse=None).sbsip_adresse()


def test_bor_i_kommune():
    assert lav_adresse().bor_i_kommune()
    assert lav_adresse().bor_i_kommune("0461")
    assert not lav_adresse(kommunekode="101").bor_i_kommune()


def test_har_fast_bopæl():
    assert lav_adresse().har_fast_bopæl
    assert not lav_adresse(vejkode="9910").har_fast_bopæl


def test_samme_adresse_skelner_mellem_lejligheder():
    assert lav_adresse(etage="1").samme_adresse(lav_adresse(etage="1"))
    assert not lav_adresse(etage="1").samme_adresse(lav_adresse(etage="2"))


def test_status():
    assert lav_person(status="doed").er_død
    assert lav_person().bor_i_danmark
    assert not lav_person(status="udrejst").bor_i_danmark


def test_barn_alder():
    barn = Barn(cpr="0106101234", foedselsdato=date(2010, 6, 1))
    assert barn.alder(date(2028, 5, 31)) == 17
    assert barn.alder(date(2028, 6, 1)) == 18


def test_hjemmeboende_børn_under_18():
    hjemme = Barn(cpr="1", foedselsdato=date(2015, 1, 1), adresse=lav_adresse())
    voksen = Barn(cpr="2", foedselsdato=date(2000, 1, 1), adresse=lav_adresse())
    flyttet = Barn(
        cpr="3", foedselsdato=date(2015, 1, 1), adresse=lav_adresse(husnummer="4")
    )
    uden_adresse = Barn(cpr="4", foedselsdato=date(2015, 1, 1))
    person = lav_person(boern=(hjemme, voksen, flyttet, uden_adresse))

    assert person.hjemmeboende_børn_under_18(date(2026, 10, 19)) == [hjemme]


def test_virksomhed():
    virksomhed = Virksomhed(
        cvr="35209115",
        navn="Odense Kommune",
        status="AKTIV",
        produktionsenheder=(Produktionsenhed(pnummer="1003388394", navn="Rådhuset"),),
    )
    assert virksomhed.er_aktiv
    assert virksomhed.find_produktionsenhed(1003388394).navn == "Rådhuset"
    assert virksomhed.find_produktionsenhed("1") is None


def graphql_adresse(**ændringer) -> dict:
    cpr_adresse = dict(
        cprkommunekode="0461",
        cprvejkode="0123",
        vejadresseringsnavn="Flakhaven",
        husnummer="002",
        etage=None,
        sidedoer=None,
        postnummer="5000",
        postdistrikt="Odense C",
    )
    cpr_adresse.update(ændringer)
    return {"status": "aktuel", "virkningfra": "2021-09-11", "cprAdresse": cpr_adresse}


def graphql_person(**ændringer) -> dict:
    node = {
        "status": "bopael_i_danmark",
        "foedselsdato": "1990-01-01",
        "beskyttelser": [
            {
                "beskyttelsestype": "markedsfoering",
                "status": "aktuel",
                "virkningfra": "2025-02-10T11:00:00.000000Z",
                "virkningtil": None,
            },
            {
                "beskyttelsestype": "navne_og_adresse",
                "status": "historisk",
                "virkningfra": "2025-02-10T11:00:00.000000Z",
                "virkningtil": "2026-02-10T11:00:00.000000Z",
            },
        ],
        "navne": [
            {
                "status": "aktuel",
                "fornavne": "Anne",
                "mellemnavn": None,
                "efternavn": "Hansen",
            }
        ],
        "adresseoplysninger": [graphql_adresse()],
        "civilstande": [
            {
                "status": "aktuel",
                "civilstandstype": "gift",
                "aegtefaelle": {"personnummer": "0202851234", "beskyttelser": []},
            }
        ],
        "boern": [
            {
                "barn": {
                    "personnummer": "0303154321",
                    "beskyttelser": [],
                    "adresseoplysninger": graphql_adresse(),
                }
            },
            {
                "barn": {
                    "personnummer": "0404005678",
                    "beskyttelser": [],
                    "adresseoplysninger": graphql_adresse(husnummer="10"),
                }
            },
        ],
        "foraeldremyndighedsoplysninger": [
            {"virkningtil": None, "foraeldremyndig": {"personnummer": "0505601111"}},
            {
                "virkningtil": "2010-01-01",
                "foraeldremyndig": {"personnummer": "0606602222"},
            },
            {"virkningtil": None, "foraeldremyndig": None},
        ],
    }
    node.update(ændringer)
    return node


def test_person_fra_graphql():
    person = Person.fra_graphql("0101901234", graphql_person())

    assert person.status == "bopael_i_danmark"
    assert person.foedselsdato == date(1990, 1, 1)
    assert person.navn == Navn(fornavne="Anne", efternavn="Hansen")
    assert person.adresse == lav_adresse(vejkode="123", gyldig_fra=date(2021, 9, 11))
    assert person.adresse.bor_i_kommune()
    assert person.aegtefaelle_cpr == "0202851234"
    assert person.foraeldremyndighed == ("0505601111",)
    assert person.beskyttelser == ("markedsfoering",)
    assert not person.har_navne_og_adressebeskyttelse


def test_person_fra_graphql_børn():
    person = Person.fra_graphql("0101901234", graphql_person())

    assert [b.foedselsdato for b in person.boern] == [
        date(2015, 3, 3),
        date(2000, 4, 4),
    ]
    assert [b.cpr for b in person.hjemmeboende_børn_under_18(date(2026, 10, 19))] == [
        "0303154321"
    ]


def test_person_fra_graphql_uden_adresse_og_navn():
    person = Person.fra_graphql(
        "0101901234",
        graphql_person(status="doed", navne=[], adresseoplysninger=[], civilstande=[]),
    )

    assert person.er_død
    assert person.navn is None
    assert person.adresse is None
    assert person.aegtefaelle_cpr is None
    assert person.hjemmeboende_børn_under_18() == []


def test_navne_og_adressebeskyttelse():
    beskyttelse = {
        "beskyttelsestype": "navne_og_adresse",
        "status": "aktuel",
        "virkningfra": "2025-02-10T11:00:00.000000Z",
        "virkningtil": None,
    }
    person = Person.fra_graphql(
        "0101901234", graphql_person(beskyttelser=[beskyttelse])
    )
    assert person.har_navne_og_adressebeskyttelse


def test_adresse_fra_graphql_etage_og_dør():
    adresse = Adresse.fra_graphql(graphql_adresse(etage="02", sidedoer="tv"))
    assert adresse.etage == "2"
    assert adresse.sbsip_linjer("X")[1] == "Flakhaven 2, 2. tv"
