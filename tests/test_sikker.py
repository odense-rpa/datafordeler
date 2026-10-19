import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from sikker import masker


def test_cpr_maskeres():
    assert masker("cpr 0101901234 og 010190-1234") == "cpr <CPR> og <CPR>"
    assert masker('{"personnummer": "0101901234"}') == '{"personnummer": "<CPR>"}'
    assert masker("id=x0101901234y") == "id=x<CPR>y"


def test_andre_tal_maskeres_ikke():
    assert masker("postnummer 5000, cvr 35209115") == "postnummer 5000, cvr 35209115"


def test_navne_i_json_maskeres():
    tekst = '{"fornavne": "Anne", "efternavn": "Hansen", "Navn": "A \\"B\\" C"}'
    assert masker(tekst) == (
        '{"fornavne": "<NAVN>", "efternavn": "<NAVN>", "Navn": "<NAVN>"}'
    )


def test_navne_i_repr_maskeres():
    tekst = "Navn(fornavne='Anne', efternavn='Hansen', mellemnavn=None)"
    assert masker(tekst) == (
        "Navn(fornavne='<NAVN>', efternavn='<NAVN>', mellemnavn=None)"
    )
    assert masker("borgernavn: 'Anne Hansen'") == "borgernavn: '<NAVN>'"


def test_adresse_og_virksomhed_vises():
    tekst = (
        '{"vejadresseringsnavn": "Flakhaven", "virksomhedsnavn": "Odense Kommune",'
        ' "produktionsenhedsnavn": "Rådhuset"}'
    )
    assert masker(tekst) == tekst
