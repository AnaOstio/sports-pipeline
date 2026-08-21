import requests
import json
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
STADIUMS_PATH = "data/stadiums.json"


class WeatherExtractor:
    def __init__(self, stadiums_path: str = STADIUMS_PATH):
        with open(stadiums_path, "r", encoding="utf-8") as f:
            self.stadiums = json.load(f)
        logger.info(f"Estadios cargados: {len(self.stadiums)}")

    def get_team_coords(self, team_name: str) -> dict:
        """
        Devuelve lat/lon del estadio de un equipo.
        Lanza KeyError si el equipo no está en stadiums.json.
        """
        if team_name not in self.stadiums:
            raise KeyError(f"Equipo no encontrado en stadiums.json: '{team_name}'")
        return self.stadiums[team_name]

    def get_historical_weather(
        self,
        team_name: str,
        date_from: str,
        date_to: str,
    ) -> dict:
        """
        Descarga el clima histórico diario para el estadio de un equipo.

        Args:
            team_name:  Nombre exacto del equipo (igual que en stadiums.json)
            date_from:  Fecha inicio en formato 'YYYY-MM-DD'
            date_to:    Fecha fin en formato 'YYYY-MM-DD'

        Returns:
            dict con la respuesta cruda de Open-Meteo
        """
        stadium = self.get_team_coords(team_name)

        params = {
            "latitude":   stadium["lat"],
            "longitude":  stadium["lon"],
            "start_date": date_from,
            "end_date":   date_to,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "windspeed_10m_max",
                "weathercode",
            ],
            "timezone": "Europe/Madrid",
        }

        logger.info(
            f"Descargando clima: {team_name} ({stadium['city']}) | "
            f"{date_from} → {date_to}"
        )

        response = requests.get(BASE_URL, params=params, timeout=20)

        if response.status_code != 200:
            logger.error(f"Error {response.status_code}: {response.text}")
            response.raise_for_status()

        data = response.json()
        # Añadimos metadatos para trazabilidad
        data["_meta"] = {
            "team":    team_name,
            "stadium": stadium["stadium"],
            "city":    stadium["city"],
        }
        return data

    def get_all_teams_weather(
        self,
        date_from: str = "2023-08-01",
        date_to: str = "2024-06-30",
    ) -> dict[str, dict]:
        """
        Descarga el clima para todos los equipos en stadiums.json.
        Open-Meteo no tiene rate limit estricto, pero añadimos pequeña pausa
        para no saturar el servicio.

        Returns:
            dict { team_name: weather_data }
        """
        import time
        results = {}
        teams = list(self.stadiums.keys())

        for i, team in enumerate(teams, 1):
            logger.info(f"[{i}/{len(teams)}] {team}")
            try:
                results[team] = self.get_historical_weather(team, date_from, date_to)
                time.sleep(0.5)  # Pausa mínima por cortesía con el servicio
            except Exception as e:
                logger.error(f"Error descargando clima de {team}: {e}")
                results[team] = None  # No paramos el proceso por un equipo

        ok = sum(1 for v in results.values() if v is not None)
        logger.info(f"Clima descargado: {ok}/{len(teams)} equipos")
        return results

    def save_bronze(
        self,
        data: dict,
        team_name: str,
        bronze_path: str = "data/bronze/weather",
    ) -> str:
        """Guarda el JSON crudo de clima en la capa bronze."""
        Path(bronze_path).mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        # Slug del nombre del equipo para el nombre de archivo
        team_slug = team_name.lower().replace(" ", "_").replace(".", "")
        filepath = f"{bronze_path}/{date_str}_{team_slug}_weather.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Bronze guardado: {filepath}")
        return filepath

    def save_all_bronze(
        self,
        all_weather: dict[str, dict],
        bronze_path: str = "data/bronze/weather",
    ) -> list[str]:
        """Guarda el clima de todos los equipos en bronze."""
        paths = []
        for team, data in all_weather.items():
            if data is not None:
                path = self.save_bronze(data, team, bronze_path)
                paths.append(path)
        return paths


if __name__ == "__main__":
    extractor = WeatherExtractor(stadiums_path="data/stadiums.json")

    # Descarga clima de toda la temporada para todos los equipos
    all_weather = extractor.get_all_teams_weather(
        date_from="2023-08-01",
        date_to="2024-06-30",
    )

    # Guarda en bronze
    paths = extractor.save_all_bronze(all_weather)
    print(f"\nArchivos guardados en bronze: {len(paths)}")

    # Verificación rápida con un equipo
    sample = all_weather.get("Athletic Club")
    if sample:
        daily = sample["daily"]
        print(f"\nEjemplo Athletic Club — primeros 3 días:")
        for i in range(3):
            print(
                f"  {daily['time'][i]} | "
                f"max: {daily['temperature_2m_max'][i]}°C | "
                f"lluvia: {daily['precipitation_sum'][i]}mm"
            )