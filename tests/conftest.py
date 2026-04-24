import os
import pytest
from dotenv import load_dotenv
from pathlib import Path

import datafordeler

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture
def datafordeler_client() -> datafordeler.Datafordeler:
    certifikat_sti = str(PROJECT_ROOT / "datafordeler.crt")
    certifikat_nøglefil = str(PROJECT_ROOT / "datafordeler.key")
    return datafordeler.Datafordeler(certifikat_sti, certifikat_nøglefil)

