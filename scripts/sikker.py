"""Kør en kommando og masker CPR-numre og personnavne i outputtet.

Brug:
    uv run python scripts/sikker.py -- uv run pytest tests/
    some_command | uv run python scripts/sikker.py

Maskeringen er mønsterbaseret:
- CPR: 10 cifre i træk eller ddmmyy-xxxx, også inde i længere tekst.
- Navne: værdien af enhver nøgle/attribut hvis navn indeholder "navn"
  (JSON "fornavne": "...", Python repr fornavne='...'), undtagen vej-,
  virksomheds- og produktionsenhedsnavne.

Navne uden nøgle (fx første linje i sbsip_linjer) fanges ikke. Udskriv derfor
struktur og antal frem for rå værdier.
"""

import re
import subprocess
import sys

CPR_MØNSTER = re.compile(r"(?<!\d)\d{6}-?\d{4}(?!\d)")

_STRENG = r"(?:\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')"
NAVN_MØNSTER = re.compile(
    rf"""(?P<nøgle>["']?(?<!\w)(?!vej|virksomhed|produktionsenhed)\w*navn\w*["']?)"""
    rf"""(?P<sep>\s*[:=]\s*)(?P<værdi>{_STRENG})""",
    re.IGNORECASE,
)


def masker(tekst: str) -> str:
    tekst = NAVN_MØNSTER.sub(
        lambda m: f"{m['nøgle']}{m['sep']}{m['værdi'][0]}<NAVN>{m['værdi'][0]}",
        tekst,
    )
    return CPR_MØNSTER.sub("<CPR>", tekst)


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--"]:
        args = args[1:]

    if not args:
        for linje in sys.stdin:
            sys.stdout.write(masker(linje))
        return 0

    resultat = subprocess.run(
        args, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    sys.stdout.write(masker(resultat.stdout))
    return resultat.returncode


if __name__ == "__main__":
    sys.exit(main())
