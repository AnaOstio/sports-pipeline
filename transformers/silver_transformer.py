import glob
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from utils.constants import WINNER_MAP, WMO_CODES

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class SilverTransformer:
    """
    Transforma los JSONs de la capa bronze a un Parquet limpio en silver.

    Responsabilidades:
      1. Leer y limpiar partidos (football-data.org)
      2. Leer y limpiar clima (Open-Meteo) de todos los equipos
      3. Join partidos + clima por equipo local y fecha
      4. Guardar como Parquet en data/silver/
    """

    def transform_matches(self, bronze_path: str) -> pd.DataFrame:
        """
        Lee el JSON crudo de partidos y devuelve un DataFrame limpio.
        Solo incluye partidos con status FINISHED.
        """
        logger.info(f"Leyendo partidos: {bronze_path}")
        with open(bronze_path, encoding="utf-8") as f:
            raw = json.load(f)

        rows = []
        for m in raw["matches"]:
            # Saltamos partidos no terminados — no tienen score ni winner fiable
            if m["status"] != "FINISHED":
                continue

            rows.append(
                {
                    "match_id": m["id"],
                    "matchday": m.get("matchday"),
                    "match_date": m["utcDate"],
                    "home_team": m["homeTeam"]["name"],
                    "away_team": m["awayTeam"]["name"],
                    "home_score": m["score"]["fullTime"].get("home"),
                    "away_score": m["score"]["fullTime"].get("away"),
                    "winner_raw": m["score"].get(
                        "winner"
                    ),  # HOME_TEAM / AWAY_TEAM / DRAW
                }
            )

        df = pd.DataFrame(rows)

        # Tipos
        df["match_date"] = pd.to_datetime(df["match_date"], utc=True).dt.tz_localize(
            None
        )
        df["match_date_only"] = df["match_date"].dt.date
        df["home_score"] = df["home_score"].astype("Int64")  # Int64 soporta NaN
        df["away_score"] = df["away_score"].astype("Int64")

        # Resultado en etiqueta corta: H / A / D
        df["result"] = df["winner_raw"].map(WINNER_MAP)

        # Total de goles — útil para el modelo ML
        df["total_goals"] = df["home_score"] + df["away_score"]

        # Deduplicación por si hubiera partidos duplicados en la respuesta
        before = len(df)
        df = df.drop_duplicates(subset="match_id").reset_index(drop=True)
        if len(df) < before:
            logger.warning(f"Eliminados {before - len(df)} duplicados en partidos")

        logger.info(f"Partidos FINISHED: {len(df)}")
        return df

    def transform_weather(self, bronze_weather_dir: str) -> pd.DataFrame:
        """
        Lee todos los JSONs de clima de un directorio y los concatena
        en un único DataFrame limpio.
        """
        files = glob.glob(f"{bronze_weather_dir}/*.json")
        if not files:
            raise FileNotFoundError(f"No se encontraron JSONs en {bronze_weather_dir}")

        logger.info(f"Leyendo clima de {len(files)} equipos")
        dfs = []

        for filepath in files:
            with open(filepath, encoding="utf-8") as f:
                raw = json.load(f)

            daily = raw["daily"]
            meta = raw.get("_meta", {})

            df = pd.DataFrame(
                {
                    "match_date_only": pd.to_datetime(daily["time"]).date,
                    "home_team": meta.get("team", ""),
                    "city": meta.get("city", ""),
                    "stadium": meta.get("stadium", ""),
                    "temp_max": daily["temperature_2m_max"],
                    "temp_min": daily["temperature_2m_min"],
                    "temp_avg": [
                        round((mx + mn) / 2, 1)
                        for mx, mn in zip(
                            daily["temperature_2m_max"], daily["temperature_2m_min"]
                        )
                    ],
                    "precipitation": daily["precipitation_sum"],
                    "wind_max": daily["windspeed_10m_max"],
                    "weather_code": daily["weathercode"],
                }
            )

            dfs.append(df)

        df_all = pd.concat(dfs, ignore_index=True)

        # Añadimos descripción legible del weather code (WMO estándar)
        df_all["weather_desc"] = df_all["weather_code"].map(WMO_CODES).fillna("Unknown")

        logger.info(
            f"Filas de clima: {len(df_all)} | Equipos: {df_all['home_team'].nunique()}"
        )
        return df_all

    def join_and_save(
        self,
        df_matches: pd.DataFrame,
        df_weather: pd.DataFrame,
        silver_path: str = "data/silver",
    ) -> str:
        """
        Hace el join partidos + clima por equipo local y fecha.
        Guarda el resultado como Parquet en silver_path.
        Devuelve la ruta del archivo generado.
        """
        logger.info("Haciendo join partidos + clima")

        # El clima está indexado por equipo LOCAL (home_team) y fecha
        df_merged = df_matches.merge(
            df_weather,
            on=["home_team", "match_date_only"],
            how="left",
        )

        # Verificación de calidad
        nulos_clima = df_merged["temp_avg"].isna().sum()
        if nulos_clima > 0:
            logger.warning(
                f"{nulos_clima} partidos sin datos de clima — "
                "revisar nombres de equipo o rango de fechas"
            )
        else:
            logger.info("✅ Todos los partidos tienen datos de clima")

        # Columnas finales ordenadas — lo que irá a BigQuery
        cols = [
            "match_id",
            "matchday",
            "match_date",
            "match_date_only",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "total_goals",
            "result",  # H / A / D
            "city",
            "stadium",
            "temp_avg",
            "temp_max",
            "temp_min",
            "precipitation",
            "wind_max",
            "weather_code",
            "weather_desc",
        ]
        df_final = df_merged[cols]

        # Guardar como Parquet
        Path(silver_path).mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        output_path = f"{silver_path}/{date_str}_matches_weather.parquet"
        df_final.to_parquet(output_path, index=False)

        logger.info(
            f"Silver guardado: {output_path} | {len(df_final)} filas | {len(df_final.columns)} columnas"
        )
        return output_path

    def run(
        self,
        football_bronze_dir: str = "data/bronze/football",
        weather_bronze_dir: str = "data/bronze/weather",
        silver_path: str = "data/silver",
    ) -> str:
        """
        Ejecuta el pipeline completo de transformación:
        bronze football + bronze weather → silver Parquet.
        """
        # Cogemos el archivo de partidos más reciente
        football_files = sorted(glob.glob(f"{football_bronze_dir}/*matches*.json"))
        if not football_files:
            raise FileNotFoundError(
                f"No se encontró JSON de partidos en {football_bronze_dir}"
            )
        matches_file = football_files[-1]
        logger.info(f"Usando archivo de partidos: {matches_file}")

        df_matches = self.transform_matches(matches_file)
        df_weather = self.transform_weather(weather_bronze_dir)
        output_path = self.join_and_save(df_matches, df_weather, silver_path)

        return output_path


if __name__ == "__main__":
    transformer = SilverTransformer()
    output = transformer.run()

    # Verificación rápida del resultado
    df = pd.read_parquet(output)
    print(f"\n{'=' * 50}")
    print(f"Silver generado: {output}")
    print(f"Filas:    {len(df)}")
    print(f"Columnas: {list(df.columns)}")
    print(f"\nPrimeras filas:")
    print(
        df[
            [
                "match_date_only",
                "home_team",
                "away_team",
                "result",
                "temp_avg",
                "precipitation",
            ]
        ]
        .head(10)
        .to_string()
    )
    print(f"\nEstadísticas de clima:")
    print(df[["temp_avg", "precipitation", "wind_max"]].describe().round(2))
