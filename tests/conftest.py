import pytest
import os

from datafordeler.datafordeler import Datafordeler


@pytest.fixture(scope="session")
def datafordeler_client() -> Datafordeler:
    certifikat_sti = os.getenv("CERTIFIKATER", "./certifikater")
    datafordeler = Datafordeler(
        certifikat_sti=os.path.join(certifikat_sti, "datafordeler.crt"),
        certifikat_nøglefil=os.path.join(certifikat_sti, "datafordeler.key"),
    )
    
    return datafordeler

@pytest.fixture(scope="session")
def test_cpr() -> str:
    cpr = os.getenv("TEST_CPR") or ""
    assert cpr, "TEST_CPR environment variable not set"
    return cpr