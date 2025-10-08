import httpx


class Datafordeleren:
    def __init__(self, certifikat_sti: str, certifikat_nøglefil: str):
        self.certifikat_sti = certifikat_sti
        self.certifikat_adgangskode = certifikat_nøglefil

        self._client = httpx.Client(cert=(self.certifikat_sti, self.certifikat_adgangskode))

        
    
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
        response = self._client.get(f"https://s5-certservices.datafordeler.dk/CPR/CprPersonFullSimple/1/REST/PersonFullListSimple?pnr.personnummer.wi={cpr}")

        response.raise_for_status()

        data = response.json()

        if len(data.get("Personer", [])) == 0:
            raise ValueError(f"Ingen person fundet med CPR-nummer {cpr}")

        return data["Personer"][0]
