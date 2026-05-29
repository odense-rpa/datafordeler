from src.datafordeler.datafordeler import Datafordeler

def test_hent_personoplysninger(datafordeler_client: Datafordeler, test_cpr: str):
    cpr = test_cpr
    person_oplysninger = datafordeler_client.hent_personoplysninger(cpr)

    assert isinstance(person_oplysninger, dict)
    assert "Person" in person_oplysninger