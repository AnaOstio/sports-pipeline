"""
DAG: sports_ingestion
Orquesta el pipeline completo de ingesta y transformación:

  extract_football ──┐
                     ├──► transform_silver ──► upload_to_gcs
  extract_weather  ──┘

Schedule: diario a las 6:00 AM (hora España)
"""

import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración del DAG
# ---------------------------------------------------------------------------
default_args = {
    "owner": "sports-pipeline",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

dag = DAG(
    dag_id="sports_ingestion",
    description="Extrae partidos y clima, transforma a silver y sube a GCS",
    default_args=default_args,
    start_date=datetime(2024, 8, 1),
    schedule_interval="0 6 * * *",  # Cada día a las 6:00 AM
    catchup=False,  # No ejecuta días pasados al activar el DAG
    tags=["sports", "ingestion", "bronze", "silver"],
)

# ---------------------------------------------------------------------------
# Tareas
# ---------------------------------------------------------------------------


def task_extract_football(**context):
    """
    Descarga partidos y clasificación de La Liga desde football-data.org
    y los guarda en data/bronze/football/.
    Pushea las rutas a XCom para la tarea siguiente.
    """
    from extractors.football_extractor import FootballExtractor

    extractor = FootballExtractor()

    matches = extractor.get_matches(competition="PD", season=2023)
    standings = extractor.get_standings(competition="PD", season=2023)

    path_matches = extractor.save_bronze(matches, "matches_PD_2023")
    path_standings = extractor.save_bronze(standings, "standings_PD_2023")

    # Compartimos las rutas con la tarea de transformación via XCom
    context["ti"].xcom_push(key="matches_path", value=path_matches)
    context["ti"].xcom_push(key="standings_path", value=path_standings)

    logger.info(f"Football extraído → {path_matches}, {path_standings}")


def task_extract_weather(**context):
    """
    Descarga el clima histórico de toda la temporada para los 20 estadios
    y los guarda en data/bronze/weather/.
    """
    from extractors.weather_extractor import WeatherExtractor

    extractor = WeatherExtractor(stadiums_path="data/stadiums.json")

    all_weather = extractor.get_all_teams_weather(
        date_from="2023-08-01",
        date_to="2024-06-30",
    )
    paths = extractor.save_all_bronze(all_weather)

    context["ti"].xcom_push(key="weather_paths", value=paths)
    logger.info(f"Weather extraído → {len(paths)} archivos")


def task_transform_silver(**context):
    """
    Lee los JSONs de bronze, hace el join partidos + clima
    y guarda el resultado como Parquet en data/silver/.
    """
    from transformers.silver_transformer import SilverTransformer

    transformer = SilverTransformer()
    output_path = transformer.run(
        football_bronze_dir="data/bronze/football",
        weather_bronze_dir="data/bronze/weather",
        silver_path="data/silver",
    )

    context["ti"].xcom_push(key="silver_path", value=output_path)
    logger.info(f"Silver generado → {output_path}")


def task_upload_to_gcs(**context):
    """
    Sube los archivos bronze y silver al bucket de GCS.
    """
    from utils.gcs_client import GCSClient

    gcs = GCSClient()

    # Bronze football
    uris_football = gcs.upload_folder("data/bronze/football", "bronze/football")

    # Bronze weather
    uris_weather = gcs.upload_folder("data/bronze/weather", "bronze/weather")

    # Silver
    uris_silver = gcs.upload_folder("data/silver", "silver")

    total = len(uris_football) + len(uris_weather) + len(uris_silver)
    logger.info(f"GCS: {total} archivos subidos")


# ---------------------------------------------------------------------------
# Definición del grafo de tareas
# ---------------------------------------------------------------------------
with dag:
    extract_football = PythonOperator(
        task_id="extract_football",
        python_callable=task_extract_football,
    )

    extract_weather = PythonOperator(
        task_id="extract_weather",
        python_callable=task_extract_weather,
    )

    transform_silver = PythonOperator(
        task_id="transform_silver",
        python_callable=task_transform_silver,
    )

    upload_gcs = PythonOperator(
        task_id="upload_to_gcs",
        python_callable=task_upload_to_gcs,
    )

    # extract_football y extract_weather corren en paralelo
    # transform_silver espera a que ambas terminen
    # upload_gcs es lo último
    [extract_football, extract_weather] >> transform_silver >> upload_gcs
