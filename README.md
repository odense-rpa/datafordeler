# Datafordeleren Python Bibliotek

Et Python bibliotek til at tilgå [Datafordeleren](https://datafordeler.dk/) - Danmarks officielle platform for offentlige grunddata fra landets myndigheder.

## Om Datafordeleren

Datafordeleren er din indgang til offentlige grunddata fra Danmarks myndigheder. Platformen drives af Klimadatastyrelsen og giver adgang til en bred vifte af offentlige datasæt, herunder:

- **Personer** - Personoplysninger fra CPR
- **Fast ejendom** - Ejendomsdata og grundoplysninger
- **Virksomheder** - Virksomhedsregistre og CVR-data  
- **Adresser, veje og områder** - Geografiske og administrative data
- **Landkort og geografi** - Geodata og kortmateriale
- **Vand og klima** - Miljø- og klimadata

## Installation

```bash
pip install datafordeleren
```

## Forudsætninger

For at bruge Datafordeleren skal du have:

1. **Certifikat fra Datafordeleren** - Opret en konto på [datafordeler.dk](https://datafordeler.dk/konto/login-oversigt/) og download dit certifikat
2. **Python 3.13+** - Biblioteket kræver Python 3.13 eller nyere

## Brug

```python
from datafordeleren import Datafordeleren

# Initialiser med dit certifikat
client = Datafordeleren(
    certifikat_sti="datafordeler.crt",
    certifikat_nøglefil="datafordeler.key"
)

# Hent personoplysninger baseret på CPR-nummer
try:
    person = client.hent_personoplysninger("1234567890")
    print(f"Navn: {person['navn']}")
except ValueError as e:
    print(f"Fejl: {e}")
```

## Funktioner

### `hent_personoplysninger(cpr: str) -> dict`

Henter personoplysninger fra CPR-registret baseret på CPR-nummer.

**Parametre:**
- `cpr` (str): 10-cifret CPR-nummer

**Returnerer:**
- `dict`: Ordbog med personoplysninger

**Exceptions:**
- `ValueError`: Hvis ingen person findes med det angivne CPR-nummer

## Support

Ved spørgsmål eller problemer:

- **Datafordeleren Support**: 
  - Telefon: 33 34 89 77 (dagligt 06:00 - 23:00)
  - Email: Via [support formular](https://datafordeler.dk/support/)
- **Bibliotek**: Opret et issue på GitHub

## Links

- [Datafordeleren hjemmeside](https://datafordeler.dk/)
- [Dokumentation](https://datafordeler.dk/dokumentation/)
- [Dataoversigt](https://datafordeler.dk/dataoversigt/)
- [Selvbetjening](https://selfservice.datafordeler.dk/)

## Licens

Dette bibliotek er udviklet af Michael Wulff Nielsen (miwn@odense.dk). Licenseret under MIT licens.