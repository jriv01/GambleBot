"""Pokemon API Wrapper."""

from functools import lru_cache
import random

import requests

_NUM_POKEMON = 1025
_API_ROOT = "https://pokeapi.co/api/v2/"


class Pokemon:
    """A Pokémon."""

    def __init__(
        self,
        name: str,
        pokedex_number: int,
        artwork_url: str,
        language: str = "en",
    ):
        self.name = name
        self.pokedex_number = pokedex_number
        self.artwork_url = artwork_url
        self.language = language


class PokemonApiWrapper:
    """Wrapper for making requests to PokeApi V2."""

    @lru_cache(maxsize=32)
    def _get_request(self, request: str) -> dict:
        """Make request to PokeApi v2.

        The 32 most recent requests are cached.
        """
        response = requests.get(url=request, timeout=60)
        json = response.json()
        return json

    async def get_random_pokemon(self, language: str = "en") -> Pokemon:
        """Get a random Pokémon."""
        pokedex_id = str(random.randint(1, _NUM_POKEMON))
        return await self.get_pokemon(pokedex_id, language)

    async def get_pokemon(self, resource: str, language: str = "en") -> Pokemon:
        """Get a Pokémon by their resource name."""
        # Remove any leading zeros if resource is pokedex number
        resource = resource.lstrip("0")

        # Request pokemon & species information
        pokemon_info = self._get_request(_API_ROOT + f"pokemon/{resource}")
        species_info = self._get_request(
            _API_ROOT + f"pokemon-species/{resource}"
        )

        # Get the name for this resource in the specified language
        name = ""
        for resource_name in species_info["names"]:
            # Check if the name of the language matches
            if resource_name["language"]["name"] == language:
                name = resource_name["name"]
                break

        # Get pokemon attributes
        pokedex_number = pokemon_info["id"]
        artwork = pokemon_info["sprites"]["other"]["official-artwork"][
            "front_default"
        ]
        return Pokemon(
            name=name,
            pokedex_number=pokedex_number,
            artwork_url=artwork,
            language=language,
        )
