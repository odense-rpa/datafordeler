import httpx
import re

from typing import Any


class Datafordeler:
    def __init__(self, certifikat_sti: str, certifikat_nøglefil: str):
        self.certifikat_sti = certifikat_sti
        self.certifikat_adgangskode = certifikat_nøglefil

        self._client = httpx.Client(
            cert=(self.certifikat_sti, self.certifikat_adgangskode)
        )

    def _clean(self, value: Any) -> str:
        """Normalize any value into a safe string."""
        if value is None:
            return ""
        return str(value).strip()

    def _clean_leading_zeros(self, value: Any) -> str:
        """Strip leading zeros from house number."""
        return re.sub(r"^0+", "", self._clean(value))

    def hent_personoplysninger(self, cpr: str) -> dict:
        """
        Hent personoplysninger fra Datafordeleren baseret på CPR-nummer.p

        Args:
            cpr (str): CPR-nummeret for den person, hvis oplysninger skal hentes.
        Returns:
            dict: En ordbog med personoplysninger.
        Raises:
            ValueError: Hvis ingen person findes med det angivne CPR-nummer.
        """
        if not re.match(r"^\d{10}$", cpr):
            raise ValueError(
                f"Ugyldigt CPR-nummer format: {cpr}. CPR skal være 10 numeriske cifre."
            )

        response = self._client.get(
            f"https://s5-certservices.datafordeler.dk/CPR/CprPersonFullSimple/1/REST/PersonFullListSimple?pnr.personnummer.wi={cpr}"
        )

        response.raise_for_status()

        data = response.json()

        if len(data.get("Personer", [])) == 0:
            raise ValueError(f"Ingen person fundet med CPR-nummer {cpr}")

        return data["Personer"][0]

    def hent_aktiv_adresse(self, cpr: str) -> dict:
        """
        Hent adresseoplysninger fra Datafordeleren baseret på CPR-nummer.

        Args:
            cpr (str): CPR-nummeret for den person, hvis adresseoplysninger skal hentes.
        Returns:
            dict: En ordbog med adresseoplysninger.
        Raises:
            ValueError: Hvis ingen adresse findes for det angivne CPR-nummer.
        """
        person_oplysninger = self.hent_personoplysninger(cpr)

        person = person_oplysninger.get("Person")
        if not person:
            raise ValueError(f"Ingen person data fundet for CPR-nummer {cpr}")

        adresse_oplysninger = person.get("Adresseoplysninger")
        if not adresse_oplysninger:
            raise ValueError(f"Ingen adresseoplysninger fundet for CPR-nummer {cpr}")

        aktive_adresser = [
            adresse
            for adresse in adresse_oplysninger
            if adresse.get("Adresseoplysninger", {}).get("status") == "aktuel"
        ]
        
        

        if not aktive_adresser:
            raise ValueError(f"Ingen aktiv adresse fundet for CPR-nummer {cpr}")

        adresse = aktive_adresser[0]

        navne = person.get("Navne", [])
        aktiv_navn = next(
            (n["Navn"] for n in navne if n.get("Navn", {}).get("status") == "aktuel"), None
        )
        if aktiv_navn:
            navn_dele = [
                aktiv_navn.get("fornavne", ""),
                aktiv_navn.get("mellemnavn", ""),
                aktiv_navn.get("efternavn", ""),
            ]
            adresse["borgernavn"] = " ".join(d for d in navn_dele if d)
        else:
            adresse["borgernavn"] = ""

        return adresse

    def formater_adresse(self, address: dict) -> str:
        """
        Formater en adresse ordbog til en læsbar adresse streng.
        Args:
            address (dict): En ordbog med adresseoplysninger.
        Returns:
            str: En formateret adresse streng.
        """

        cpr = (address or {}).get("CprAdresse") or {}

        vej = self._clean(cpr.get("vejadresseringsnavn"))
        husnr = self._clean_leading_zeros(cpr.get("husnummer"))
        etage = self._clean_leading_zeros(cpr.get("etage"))
        sidedoer = self._clean_leading_zeros(cpr.get("sidedoer"))
        postnr = self._clean(cpr.get("postnummer"))
        by = self._clean(cpr.get("postdistrikt"))

        # ---------- Street line ----------
        street_parts = [p for p in (vej, husnr) if p]
        street = " ".join(street_parts)

        # ---------- Floor / door ----------
        detail_parts = [p for p in (etage, sidedoer) if p]
        detail = " ".join(detail_parts)

        # ---------- City line ----------
        city_parts = [p for p in (postnr, by) if p]
        city = " ".join(city_parts)

        # ---------- Assemble ----------
        parts = [p for p in (street, detail, city) if p]

        return ", ".join(parts)
    
    def hent_adresse_til_sbsip(self, cpr:str) -> tuple[list[str], str]:
        """
        Hent adresseoplysninger formateret til brug med sbsip funktionen send_digital_post på CPR-nummer.

        Args:
            cpr (str): CPR-nummeret for den person, hvis adresseoplysninger skal hentes.
        Returns:
            tuple[list[str], str]: En tuple bestående af en liste med adressen som kan anvendes til adresse input i sbsip funktionen
                (borgernavn, vejnavn + nummer(inkl. etage og dør) og postnummer + by) samt postnummeret som separat streng der også skal bruges som input.
        Raises:
            ValueError: Hvis ingen aktiv adresse findes for det angivne CPR-nummer.
        """
        
        aktiv_adresse= self.hent_aktiv_adresse(cpr)
        
        adresse_liste: list[str] = []
        
        adresse_liste.append(aktiv_adresse["borgernavn"])
        adresse = aktiv_adresse["Adresseoplysninger"]["CprAdresse"]
        if adresse["postdistrikt"].lower() == "ukendt":
            adresse_liste.append(adresse["vejadresseringsnavn"])
            adresse_liste.append(f"{adresse["postnummer"]} {adresse["postdistrikt"]}")
            
            return adresse_liste, adresse["postnummer"]
        
        gade = f"{adresse["vejadresseringsnavn"]} {self._clean_leading_zeros(adresse["husnummer"])}"
        postnr = f"{adresse["postnummer"]} {adresse["postdistrikt"]}"
        
        if "etage" in adresse:
            gade = f"{gade}, {self._clean_leading_zeros(adresse["etage"])}."
        
        if "sidedoer" in adresse:
            gade = f"{gade} {adresse["sidedoer"]}"
        
        adresse_liste.append(gade)
        adresse_liste.append(postnr)
        
        return adresse_liste, adresse["postnummer"]
