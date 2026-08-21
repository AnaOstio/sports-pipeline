import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import storage

load_dotenv()
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class GCSClient:
    """
    Cliente para interactuar con Google Cloud Storage.

    Responsabilidades:
      - Subir archivos locales al bucket (bronze, silver, gold)
      - Descargar archivos del bucket a local
      - Listar archivos de un prefijo (carpeta)
    """

    def __init__(self):
        self.bucket_name = os.getenv("GCS_BUCKET")
        if not self.bucket_name:
            raise ValueError("GCS_BUCKET no encontrada en .env")

        # Las credenciales las coge automáticamente de GOOGLE_APPLICATION_CREDENTIALS
        self.client = storage.Client()
        self.bucket = self.client.bucket(self.bucket_name)
        logger.info(f"GCS conectado al bucket: {self.bucket_name}")

    def upload(self, local_path: str, gcs_path: str) -> str:
        """
        Sube un archivo local a GCS.

        Args:
            local_path: ruta local del archivo, ej. 'data/bronze/football/20240821_matches.json'
            gcs_path:   ruta destino en GCS,   ej. 'bronze/football/20240821_matches.json'

        Returns:
            URI completa gs://bucket/gcs_path
        """
        if not Path(local_path).exists():
            raise FileNotFoundError(f"Archivo local no encontrado: {local_path}")

        blob = self.bucket.blob(gcs_path)
        blob.upload_from_filename(local_path)
        uri = f"gs://{self.bucket_name}/{gcs_path}"
        logger.info(f"Subido: {local_path} → {uri}")
        return uri

    def download(self, gcs_path: str, local_path: str) -> str:
        """
        Descarga un archivo de GCS a local.

        Args:
            gcs_path:   ruta en GCS,   ej. 'silver/20240821_matches_weather.parquet'
            local_path: ruta local destino

        Returns:
            Ruta local del archivo descargado
        """
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        blob = self.bucket.blob(gcs_path)

        if not blob.exists():
            raise FileNotFoundError(
                f"Archivo no encontrado en GCS: gs://{self.bucket_name}/{gcs_path}"
            )

        blob.download_to_filename(local_path)
        logger.info(f"Descargado: gs://{self.bucket_name}/{gcs_path} → {local_path}")
        return local_path

    def upload_folder(self, local_dir: str, gcs_prefix: str) -> list[str]:
        """
        Sube todos los archivos de una carpeta local a GCS bajo un prefijo.

        Args:
            local_dir:  carpeta local, ej. 'data/bronze/weather'
            gcs_prefix: prefijo GCS,   ej. 'bronze/weather'

        Returns:
            Lista de URIs subidas
        """
        files = list(Path(local_dir).glob("*"))
        if not files:
            logger.warning(f"No se encontraron archivos en {local_dir}")
            return []

        uris = []
        for file in files:
            if file.is_file():
                gcs_path = f"{gcs_prefix}/{file.name}"
                uri = self.upload(str(file), gcs_path)
                uris.append(uri)

        logger.info(
            f"Subidos {len(uris)} archivos a gs://{self.bucket_name}/{gcs_prefix}/"
        )
        return uris

    def list_files(self, prefix: str) -> list[str]:
        """
        Lista los archivos de un prefijo (carpeta) en GCS.

        Args:
            prefix: ej. 'bronze/football/'

        Returns:
            Lista de rutas GCS
        """
        blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
        paths = [blob.name for blob in blobs]
        logger.info(f"Archivos en gs://{self.bucket_name}/{prefix}: {len(paths)}")
        return paths

    def exists(self, gcs_path: str) -> bool:
        """Comprueba si un archivo existe en GCS."""
        return self.bucket.blob(gcs_path).exists()


if __name__ == "__main__":
    gcs = GCSClient()

    # 1. Subir bronze football
    uris_football = gcs.upload_folder(
        local_dir="data/bronze/football",
        gcs_prefix="bronze/football",
    )

    # 2. Subir bronze weather
    uris_weather = gcs.upload_folder(
        local_dir="data/bronze/weather",
        gcs_prefix="bronze/weather",
    )

    # 3. Subir silver
    uris_silver = gcs.upload_folder(
        local_dir="data/silver",
        gcs_prefix="silver",
    )

    # 4. Verificar que están en GCS
    print("\nArchivos en bronze/football:")
    for f in gcs.list_files("bronze/football/"):
        print(" ", f)

    print("\nArchivos en bronze/weather:")
    for f in gcs.list_files("bronze/weather/"):
        print(" ", f)

    print("\nArchivos en silver:")
    for f in gcs.list_files("silver/"):
        print(" ", f)
