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
