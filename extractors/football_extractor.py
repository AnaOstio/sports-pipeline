import requests
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://api.football-data.org/v4"
CALLS_PER_MINUTE = 10
SLEEP_BETWEEN_CALLS = 60 / CALLS_PER_MINUTE  # 6 segundos


class FootballExtractor:
    def __init__(self):
        self.api_key = os.getenv("FOOTBALL_API_KEY")
        if not self.api_key:
            raise ValueError("FOOTBALL_API_KEY no encontrada en .env")
        self.headers = {"X-Auth-Token": self.api_key}
        self._last_call_time = 0

    def _wait_rate_limit(self):
        """Asegura al menos 6 segundos entre llamadas."""
        elapsed = time.time() - self._last_call_time
        if elapsed < SLEEP_BETWEEN_CALLS:
            wait = SLEEP_BETWEEN_CALLS - elapsed
            logger.info(f"Rate limit: esperando {wait:.1f}s")
            time.sleep(wait)

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Llamada GET con rate limiting y reintentos."""
        self._wait_rate_limit()
        url = f"{BASE_URL}/{endpoint}"

        for attempt in range(3):
            try:
                logger.info(f"GET {url} | params={params}")
                response = requests.get(url, headers=self.headers, params=params, timeout=15)
                self._last_call_time = time.time()

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"429 Too Many Requests — esperando {retry_after}s")
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout en intento {attempt + 1}/3")
                time.sleep(10)
            except requests.exceptions.RequestException as e:
                logger.error(f"Error en intento {attempt + 1}/3: {e}")
                if attempt == 2:
                    raise

    def get_matches(self, competition: str = "PD", season: int = 2023) -> dict:
        """
        Descarga todos los partidos de una competición y temporada.
        PD  = La Liga (Primera División)
        CL  = Champions League
        BL1 = Bundesliga
        """
        logger.info(f"Descargando partidos: {competition} temporada {season}")
        data = self._get(f"competitions/{competition}/matches", params={"season": season})
        logger.info(f"Partidos recibidos: {data['resultSet']['count']}")
        return data

    def get_standings(self, competition: str = "PD", season: int = 2023) -> dict:
        """Descarga la clasificación de una competición."""
        logger.info(f"Descargando clasificación: {competition} temporada {season}")
        return self._get(f"competitions/{competition}/standings", params={"season": season})

    def save_bronze(self, data: dict, filename: str, bronze_path: str = "data/bronze/football") -> str:
        """
        Guarda el JSON crudo en la capa bronze.
        Nombra el archivo con la fecha de descarga para trazabilidad.
        """
        Path(bronze_path).mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        filepath = f"{bronze_path}/{date_str}_{filename}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Bronze guardado: {filepath}")
        return filepath


if __name__ == "__main__":
    extractor = FootballExtractor()

    # Partidos
    matches = extractor.get_matches(competition="PD", season=2023)
    extractor.save_bronze(matches, "matches_PD_2023")

    # Clasificación
    standings = extractor.get_standings(competition="PD", season=2023)
    extractor.save_bronze(standings, "standings_PD_2023")

    print(f"\nTotal partidos descargados: {matches['resultSet']['count']}")
    print(f"Equipos en clasificación: {len(standings['standings'][0]['table'])}")