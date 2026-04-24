import os
import pytest
import datafordeler


def test_hent_personoplysninger(datafordeler_client: datafordeler.Datafordeler):
    cpr = os.environ["TEST_CPR"]
    result = datafordeler_client.hent_personoplysninger(cpr)
    assert isinstance(result, dict)


def test_hent_personoplysninger_ugyldigt_cpr(datafordeler_client: datafordeler.Datafordeler):
    with pytest.raises(ValueError, match="Ugyldigt CPR-nummer format"):
        datafordeler_client.hent_personoplysninger("ikke-et-cpr")


def test_hent_aktiv_adresse(datafordeler_client: datafordeler.Datafordeler):
    cpr = os.environ["TEST_CPR"]
    result = datafordeler_client.hent_aktiv_adresse(cpr)
    assert isinstance(result, dict)

def test_hent_sbsip_adresse(datafordeler_client: datafordeler.Datafordeler):
    cpr = os.environ["TEST_CPR"]
    result, postnr = datafordeler_client.hent_adresse_til_sbsip(cpr)
    
    assert result is not None
    assert len(result) == 3
    assert len(postnr) == 4