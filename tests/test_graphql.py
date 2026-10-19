import os

import pytest

from datafordeler import DatafordelerGraphQL

ODENSE_KOMMUNE_CVR = "35209115"

pytestmark = pytest.mark.skipif(
    "DATAFORDELER_CLIENT_ID" not in os.environ,
    reason="Kræver DATAFORDELER_CLIENT_ID og DATAFORDELER_CLIENT_SECRET",
)


@pytest.fixture(scope="module")
def klient() -> DatafordelerGraphQL:
    return DatafordelerGraphQL.fra_miljøvariabler()


def test_hent_virksomhed(klient: DatafordelerGraphQL):
    virksomhed = klient.hent_virksomhed(ODENSE_KOMMUNE_CVR)

    assert virksomhed.cvr == ODENSE_KOMMUNE_CVR
    assert virksomhed.navn == "Odense Kommune"
    assert virksomhed.er_aktiv
    assert len(virksomhed.produktionsenheder) > 100
    assert all(p.navn for p in virksomhed.produktionsenheder)

    enhed = virksomhed.produktionsenheder[0]
    assert virksomhed.find_produktionsenhed(enhed.pnummer) == enhed


def test_hent_virksomhed_findes_ikke(klient: DatafordelerGraphQL):
    with pytest.raises(ValueError, match="Ingen virksomhed fundet"):
        klient.hent_virksomhed("00000001")


def test_hent_virksomhed_ugyldigt_cvr(klient: DatafordelerGraphQL):
    with pytest.raises(ValueError, match="Ugyldigt CVR-nummer format"):
        klient.hent_virksomhed("123")


@pytest.mark.skipif("TEST_CPR" not in os.environ, reason="Kræver TEST_CPR")
def test_hent_person(klient: DatafordelerGraphQL):
    person = klient.hent_person(os.environ["TEST_CPR"])

    assert person.cpr == os.environ["TEST_CPR"]
    assert person.status
    assert person.foedselsdato is not None
    assert person.navn is not None and person.navn.fornavne and person.navn.efternavn
    if person.adresse is not None:
        linjer, postnr = person.sbsip_adresse()
        assert len(linjer) == 3
        assert len(postnr) == 4


def test_hent_person_ugyldigt_cpr(klient: DatafordelerGraphQL):
    with pytest.raises(ValueError, match="Ugyldigt CPR-nummer format"):
        klient.hent_person("123")


def test_hent_person_findes_ikke(klient: DatafordelerGraphQL):
    with pytest.raises(ValueError, match="Ingen person fundet"):
        klient.hent_person("0000000000")


@pytest.mark.skipif("TEST_CPR" not in os.environ, reason="Kræver TEST_CPR")
def test_foraeldremyndighed(klient: DatafordelerGraphQL):
    """TEST_CPR skal have et hjemmeboende barn under 18 (samtykke fra forælderen)."""
    forælder = klient.hent_person(os.environ["TEST_CPR"])
    børn = forælder.hjemmeboende_børn_under_18()
    if not børn:
        pytest.skip("TEST_CPR har ingen hjemmeboende børn under 18")

    barn = klient.hent_person(børn[0].cpr)

    assert forælder.cpr in barn.foraeldremyndighed
    assert barn.foedselsdato == børn[0].foedselsdato
    assert barn.adresse is not None and barn.adresse.samme_adresse(forælder.adresse)
