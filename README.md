# sports-pipeline 🏟️

End-to-end Data Engineering project that predicts La Liga match results using historical match data and real weather conditions at each stadium.

---

## Architecture

```
football-data.org ──┐
                    ├──► Python Extractors ──► GCS Bronze ──► GCS Silver
open-meteo.com ─────┘         │                                    │
                          (Airflow DAG)                           dbt
                                                                   │
                                                              BigQuery
                                                             /         \
                                                         MLflow     Predictions
                                                       (sklearn)
```

**Medallion pattern:**
- **Bronze** — raw JSON from APIs, untouched
- **Silver** — cleaned Parquet with matches + weather joined by home team and date
- **Gold** — ML-ready feature set

---

## Stack

| Layer | Tool | Why |
|---|---|---|
| Orchestration | Apache Airflow | Industry standard for pipeline scheduling |
| Ingestion | Python + requests | Football data + weather APIs |
| Data Lake | Google Cloud Storage | Medallion architecture (bronze/silver/gold) |
| Transformation | dbt Core | Staging → intermediate → mart layers |
| Data Warehouse | BigQuery | Free tier, column-oriented, SQL at scale |
| ML | scikit-learn + MLflow | Model training, experiment tracking |
| Cloud | GCP (free tier) | GCS + BigQuery — no cost for this project |

---

## Data Sources

- **[football-data.org](https://www.football-data.org/)** — La Liga 2023/24 fixtures, results, standings. Free tier: 10 calls/min.
- **[Open-Meteo](https://open-meteo.com/)** — Historical daily weather per stadium coordinates. No rate limit.

**Key finding:** home team win rate is significantly higher in cold and rainy conditions:
- 🌧️ Moderate rain → **61% home win rate** vs 36% in dry conditions
- 🥶 Cold weather → **60% home win rate** vs 27% in hot conditions

---

## Project Structure

```
sports-pipeline/
├── dags/
│   └── sports_ingestion_dag.py    # Airflow DAG — daily pipeline
├── extractors/
│   ├── football_extractor.py      # football-data.org client
│   └── weather_extractor.py       # Open-Meteo client
├── transformers/
│   └── silver_transformer.py      # Bronze JSON → Silver Parquet
├── utils/
│   ├── constants.py               # WMO codes, paths, mappings
│   └── gcs_client.py              # GCS upload/download
├── ml/
│   ├── train.py                   # RandomForest training + MLflow tracking
│   └── predict.py                 # Load best model and predict
├── sports_dbt/
│   └── models/
│       ├── staging/               # stg_matches — typing and cleaning
│       ├── intermediate/          # int_team_stats — aggregations by team + weather
│       └── marts/                 # mart_team_performance — final table
├── data/
│   ├── stadiums.json              # Coordinates for all 20 La Liga stadiums
│   ├── bronze/                    # Raw API responses (JSON)
│   ├── silver/                    # Cleaned data (Parquet)
│   └── gold/                      # ML features (Parquet)
├── scripts/
│   └── load_to_bigquery.py        # Load Silver Parquet → BigQuery
├── docker-compose.yml             # Airflow + Postgres
└── requirements.txt
```

---

## dbt Models

```
stg_matches          ← cleans raw_matches: types, deduplication, weather categories
      ↓
int_team_stats       ← aggregates wins/draws/losses by team and weather condition
      ↓
mart_team_performance ← final table: performance vs average per weather condition
```

**20 data tests** running on every dbt execution:
- `unique` and `not_null` on match IDs
- `accepted_values` on result (H/A/D), rain and temperature categories

---

## ML Model

**Target:** match result — Home win (H), Away win (A), Draw (D)

**Features:**
- Matchday, home team, away team
- Temperature (avg/max/min), precipitation, wind
- Rain category, temperature category

**Results across 3 experiments tracked in MLflow:**

| Experiment | n_estimators | max_depth | Accuracy | F1 macro |
|---|---|---|---|---|
| Base RF | 100 | None | 0.41 | 0.40 |
| Deep RF | 200 | 10 | 0.38 | 0.36 |
| **Conservative RF** | **100** | **5** | **0.43** | **0.42** |

Best model: **Conservative Random Forest** (accuracy 0.43 vs 0.33 random baseline)

---

## Airflow Pipeline

Daily DAG with 4 tasks:

```
extract_football ──┐
                   ├──► transform_silver ──► upload_to_gcs
extract_weather  ──┘
```

- `extract_football` and `extract_weather` run in parallel
- `transform_silver` waits for both, joins matches + weather, saves Parquet
- `upload_to_gcs` pushes bronze and silver to GCS bucket

---

## Setup

### Prerequisites
- Python 3.11+
- Docker Desktop
- GCP account (free tier)

### 1. Clone and install

```bash
git clone https://github.com/AnaOstio/sports-pipeline
cd sports-pipeline
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Configure credentials

Create a `.env` file:

```
FOOTBALL_API_KEY=your_key_here
GCS_BUCKET=your-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\credentials.json
```

Get your football API key at [football-data.org](https://www.football-data.org/client/register).  
Create a GCP Service Account with BigQuery Admin + Storage Admin roles and download the JSON key.

### 3. Run the pipeline manually

```bash
# Extract
python extractors/football_extractor.py
python extractors/weather_extractor.py

# Transform
python transformers/silver_transformer.py

# Load to BigQuery
python scripts/load_to_bigquery.py

# dbt transformations
cd sports_dbt
dbt run
dbt test
cd ..

# Train ML model
python ml/train.py

# Predict
python ml/predict.py
```

### 4. Start Airflow

```bash
docker compose up airflow-init
docker compose up -d
```

Open `http://localhost:8080` — user: `admin` / password: `admin`  
Activate and trigger the `sports_ingestion` DAG.

### 5. MLflow UI

```bash
mlflow ui --backend-store-uri sqlite:///mlflow.db
```

Open `http://localhost:5000` to compare experiments.

---

## Key Design Decisions

**Why dbt over plain SQL scripts?**  
dbt enforces a transformation layer structure (staging → intermediate → marts), generates automatic data lineage, and runs data quality tests on every execution. Plain SQL scripts don't scale.

**Why medallion architecture in GCS?**  
Separating raw (bronze), cleaned (silver), and aggregated (gold) data allows full reprocessing from source without re-calling the APIs. If the transformer has a bug, bronze data is always safe.

**Why MLflow?**  
Experiment tracking is what separates a notebook from a production ML workflow. MLflow logs parameters, metrics, and the serialized model for every run — enabling reproducibility and comparison across experiments.

---

## Author

Built as a portfolio project to demonstrate end-to-end Data Engineering skills.  
Stack: Python · Airflow · GCS · dbt · BigQuery · scikit-learn · MLflow · GCP