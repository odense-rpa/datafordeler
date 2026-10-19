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

## Nuværende funktionalitet

Biblioteket bruger Datafordelerens GraphQL-API med OAuth2 og returnerer typede dataclasses:

- **CPR** - personer via `CPR/custom/PublicSector/v2` (tjenesten til offentlige myndigheder):
  status, fødselsdato, aktuelt navn og adresse, ægtefælle, børn, forældremyndighed og beskyttelser
- **CVR** - virksomheder via `CVR/v2`: navn, status og produktionsenheder

Version 1.0.0 erstatter den gamle REST-klient (`Datafordeler`) med certifikat. Se [Migrering fra 0.1.x](#migrering-fra-01x).

## Installation

```bash
uv add git+https://github.com/odense-rpa/datafordeler.git
```

## Forudsætninger

1. **OAuth2-klient fra Datafordeleren** - Opret en IT-system-bruger med client credentials i [Datafordelerens administrationsportal](https://selfservice.datafordeler.dk/)
2. **Adgang til tjenesterne** - Myndigheder kan kun få adgang til én CPR GraphQL-tjeneste. Vælg kun `CustomPublicSectorPerson` i ansøgningen, ellers afvises den. Se [CPR-kontorets dokumentation](https://cprservicedesk.atlassian.net/wiki/spaces/CPR/pages/3623026695/GraphQL+til+offentlige+myndigheder)
3. **Python 3.13+**

Klienten læser følgende miljøvariabler, fx fra en `.env`-fil (som aldrig må committes):

```bash
DATAFORDELER_CLIENT_ID=...
DATAFORDELER_CLIENT_SECRET=...
# Valgfrie - standardværdierne peger på produktion
DATAFORDELER_TOKEN_URL=https://auth.datafordeler.dk/realms/distribution/protocol/openid-connect/token
DATAFORDELER_GRAPHQL_URL=https://graphql.datafordeler.dk
```

## Brug

```python
from datafordeler import DatafordelerGraphQL

klient = DatafordelerGraphQL.fra_miljøvariabler()
```

Klienten henter og fornyer selv OAuth2-tokenet. Ugyldige eller ukendte CPR- og CVR-numre giver `ValueError`, og fejl fra API'et giver `DatafordelerFejl`.

### Personer

```python
person = klient.hent_person("0101901234")

person.er_død                      # status == "doed"
person.bor_i_danmark               # status == "bopael_i_danmark"
person.har_navne_og_adressebeskyttelse
person.navn.fuldt_navn

if person.adresse:
    person.adresse.bor_i_kommune("461")
    person.adresse.har_fast_bopæl  # vejkode udenfor 9900-9999
    person.adresse.er_ukendt       # postdistrikt "Ukendt"
    person.adresse.gyldig_fra      # tilflytningsdato på adressen
    person.adresse.formateret()    # "Flakhaven 2, 2 tv, 5000 Odense C"

# Adresselinjer og postnummer til sbsip send_digital_post
adresse, post_nr = person.sbsip_adresse()

person.aegtefaelle_cpr                   # CPR på aktuel ægtefælle eller None
person.hjemmeboende_børn_under_18()      # børn på samme adresse
person.foraeldremyndighed                # CPR på aktuelle forældremyndighedsindehavere
```

`person.adresse` er `None`, hvis personen ikke har en aktuel adresse (fx udrejst eller død), så processen selv kan vælge, hvad der skal ske.

### Virksomheder

```python
virksomhed = klient.hent_virksomhed("35209115")

virksomhed.navn          # "Odense Kommune"
virksomhed.er_aktiv
enhed = virksomhed.find_produktionsenhed("1003388394")
enhed.navn, enhed.er_aktiv
```

Kun aktuelle produktionsenheder returneres, så en lukket P-enhed findes ikke.

### Egne forespørgsler

```python
data = klient.forespørg(
    "CVR/v2",
    "query($cvr: Long!) { CVR_Virksomhed(where: {CVRNummer: {eq: $cvr}}) { nodes { status } } }",
    {"cvr": 35209115},
)
```

Datafordelerens GraphQL har nogle regler, som ikke er tydelige i dokumentationen:

- Kun ét rodfelt pr. forespørgsel og ingen aliaser
- Introspection er slået fra. Skemaet hentes med `GET <endpoint>/schema` (se [Dokumentation og skemaer](#dokumentation-og-skemaer))
- `beskyttelser` skal altid vælges på personer, også på ægtefælle, børn og forældremyndige
- En liste filtreret med `where` (fx `navne(where: {status: {eq: "aktuel"}})`) skal også vælge `status`, ellers matcher filteret intet
- CPR returnerer også historiske oplysninger, så filtrér på `status: "aktuel"`

## Dokumentation og skemaer

Biblioteket bruger disse tjenester:

| Register | Endpoint | Skema |
|---|---|---|
| CPR | `https://graphql.datafordeler.dk/CPR/custom/PublicSector/v2` | `https://graphql.datafordeler.dk/CPR/custom/PublicSector/v2/schema` |
| CVR | `https://graphql.datafordeler.dk/CVR/v2` | `https://graphql.datafordeler.dk/CVR/v2/schema` |

Skemaerne kræver et token (uden får man `401`), så de hentes nemmest med scriptet:

```bash
uv run python scripts/hent_skema.py                     # CPR og CVR
uv run python scripts/hent_skema.py CPR/custom/PublicSector/v3
```

Dokumentation:

- [GraphQL til offentlige myndigheder](https://cprservicedesk.atlassian.net/wiki/spaces/CPR/pages/3623026695/GraphQL+til+offentlige+myndigheder) - CPR-kontorets vejledning, adgang og query params
- [Eksempler på queries - GraphQL v3](https://cprservicedesk.atlassian.net/wiki/spaces/CPR/pages/3935338522) - alle felter på `CPRCustom_PublicSectorPerson`
- [CPR_Events og eksempel på query](https://cprservicedesk.atlassian.net/wiki/spaces/CPR/pages/3679354900) - hændelser til ændringsdrevne processer
- [Hændelsesoversigt](https://cprservicedesk.atlassian.net/wiki/spaces/CPR/pages/3681648641) - CPR-hændelseskoder og forretningshændelser
- [Datafordelerens GraphQL-dokumentation](https://confluence.sdfi.dk/display/DML/GraphQL) - paginering og generelle regler

## Migrering fra 0.1.x

Processer, der bruger 0.1.x, fortsætter med at virke, da `uv.lock` låser dem til den commit, de blev bygget med. De rammes først, når datafordeler opgraderes med `uv lock --upgrade-package datafordeler`. Den sidste REST-version er tagget `v0.1.1`, hvis en proces skal låses eksplicit:

```toml
[tool.uv.sources]
datafordeler = { git = "https://github.com/odense-rpa/datafordeler.git", tag = "v0.1.1" }
```

| REST (`Datafordeler`) | GraphQL (`DatafordelerGraphQL`) |
|---|---|
| `hent_personoplysninger(cpr)["Person"]["status"]` | `hent_person(cpr).status` |
| `hent_aktiv_adresse(cpr)["borgernavn"]` | `hent_person(cpr).navn.fuldt_navn` |
| `hent_aktiv_adresse(cpr)["Adresseoplysninger"]["CprAdresse"]["cprKommunekode"]` | `hent_person(cpr).adresse.kommunekode` |
| `formater_adresse(adresse["Adresseoplysninger"])` | `hent_person(cpr).adresse.formateret()` |
| `hent_adresse_til_sbsip(cpr)` | `hent_person(cpr).sbsip_adresse()` |
| `Civilstande` / `Boern` / `Foraeldremyndighedsoplysninger` | `aegtefaelle_cpr` / `hjemmeboende_børn_under_18()` / `foraeldremyndighed` |
| `hent_CVR_oplysninger(cvr)` | `hent_virksomhed(cvr)` |

Bemærk forskellene:

- `hent_person` henter alt i ét kald. Hent personen én gang pr. sag i stedet for at kalde flere metoder.
- Husnummer, etage, kommunekode og vejkode er uden foranstillede nuller.
- `formateret()` og `sbsip_adresse()` giver samme tekst som `formater_adresse` og `hent_adresse_til_sbsip`.
- Børns alder beregnes ud fra fødselsdatoen efter CPR-kontorets århundrederegel.

## Udvikling

```bash
uv sync
uv run pytest
```

Integrationstestene i `tests/test_graphql.py` kalder det rigtige API og springes over uden `DATAFORDELER_CLIENT_ID`. `test_hent_person` og `test_foraeldremyndighed` kræver desuden `TEST_CPR` på en person, der har givet samtykke. Datafordeleren har intet testmiljø, så opslag foretages i produktion.

Kør alt, der rører persondata, gennem `scripts/sikker.py`, som maskerer CPR-numre og navne i outputtet:

```bash
uv run python scripts/sikker.py -- uv run pytest tests/test_graphql.py
```

Maskeringen er mønsterbaseret og fanger ikke navne uden nøgle, fx første linje i `sbsip_adresse()`. Udskriv derfor ikke rå værdier.

Andre scripts:

- `scripts/hent_skema.py` - henter de aktuelle GraphQL-skemaer til `skema/` (ignoreres af git)
- `scripts/tjek_token.py` - tjekker at OAuth2-klienten virker uden at vise tokenet

## Support

Der ydes ikke support på dette bibliotek, men ved datafordeler spørgsmål og problemer kan man henvende sig hos:

- **Datafordeleren Support**:
  - Telefon: 33 34 89 77 (dagligt 06:00 - 23:00)
  - Email: Via [support formular](https://datafordeler.dk/support/)
- **CPR-kontoret**: [CPR Servicedesk](https://cprservicedesk.atlassian.net/wiki/spaces/CPR/)
- **Bibliotek**: Opret et issue på GitHub

## Links

- [Datafordeleren hjemmeside](https://datafordeler.dk/)
- [Dokumentation](https://datafordeler.dk/dokumentation/)
- [Dataoversigt](https://datafordeler.dk/dataoversigt/)
- [Selvbetjening](https://selfservice.datafordeler.dk/)
- [GraphQL til offentlige myndigheder (CPR)](https://cprservicedesk.atlassian.net/wiki/spaces/CPR/pages/3623026695/GraphQL+til+offentlige+myndigheder)

## Licens

Dette bibliotek er udviklet af Michael Wulff Nielsen (miwn@odense.dk). Licenseret under MIT licens.
