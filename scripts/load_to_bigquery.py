import glob
import pandas as pd
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()

# Cargamos el parquet silver más reciente
files = sorted(glob.glob("data/silver/*.parquet"))
if not files:
    raise FileNotFoundError("No se encontró ningún Parquet en data/silver/")

df = pd.read_parquet(files[-1])
print(f"Parquet cargado: {files[-1]} | {len(df)} filas | {len(df.columns)} columnas")

# Subimos a BigQuery
client = bigquery.Client()

# Crear el dataset si no existe
dataset_id = "sports-pipeline-506109.sports_dbt"
try:
    client.get_dataset(dataset_id)
    print("Dataset ya existe")
except Exception:
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "EU"
    client.create_dataset(dataset)
    print("Dataset creado")

table_id = "sports-pipeline-506109.sports_dbt.raw_matches"

job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
job.result()

print(f"✅ Cargadas {len(df)} filas en {table_id}")
