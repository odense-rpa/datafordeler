import httpx
import pytest

from datafordeler import DatafordelerGraphQL
from datafordeler.graphql import TOKEN_URL


def lav_klient(graphql_svar: list[int]) -> tuple[DatafordelerGraphQL, list[str]]:
    """Klient med falsk transport. graphql_svar er statuskoder i rækkefølge."""
    tokens_udstedt = 0
    brugte_tokens: list[str] = []
    svar = iter(graphql_svar)

    def håndter(request: httpx.Request) -> httpx.Response:
        nonlocal tokens_udstedt
        if str(request.url) == TOKEN_URL:
            tokens_udstedt += 1
            return httpx.Response(
                200,
                json={"access_token": f"token-{tokens_udstedt}", "expires_in": 3600},
            )
        brugte_tokens.append(request.headers["Authorization"])
        status = next(svar)
        if status == 401:
            return httpx.Response(401)
        return httpx.Response(
            200,
            json={"data": {"ok": True}},
            headers={"content-type": "application/graphql-response+json"},
        )

    klient = DatafordelerGraphQL("id", "secret")
    klient._client = httpx.Client(transport=httpx.MockTransport(håndter))
    return klient, brugte_tokens


def test_token_genbruges():
    klient, brugte_tokens = lav_klient([200, 200])

    klient.forespørg("CVR/v2", "{ ok }")
    klient.forespørg("CVR/v2", "{ ok }")

    assert brugte_tokens == ["Bearer token-1", "Bearer token-1"]


def test_nyt_token_ved_401():
    klient, brugte_tokens = lav_klient([401, 200])

    assert klient.forespørg("CVR/v2", "{ ok }") == {"ok": True}
    assert brugte_tokens == ["Bearer token-1", "Bearer token-2"]


def test_401_to_gange_fejler():
    klient, brugte_tokens = lav_klient([401, 401])

    with pytest.raises(httpx.HTTPStatusError):
        klient.forespørg("CVR/v2", "{ ok }")
    assert len(brugte_tokens) == 2


def test_nyt_token_når_det_er_ved_at_udløbe():
    klient, brugte_tokens = lav_klient([200, 200])

    klient.forespørg("CVR/v2", "{ ok }")
    klient._token_udløber = 0
    klient.forespørg("CVR/v2", "{ ok }")

    assert brugte_tokens == ["Bearer token-1", "Bearer token-2"]
