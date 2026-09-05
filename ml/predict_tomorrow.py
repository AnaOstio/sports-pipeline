import requests
import pandas as pd
from datetime import datetime, timedelta
import mlflow
import mlflow.sklearn
from sklearn.preprocessing import LabelEncoder
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
MLFLOW_DIR = "sqlite:///mlflow.db"
BEST_RUN_ID = "dcbb04ba644448c092f61b2e4bc8397e"
TOMORROW = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

FEATURE_COLS = [
    "matchday",
    "home_team",
    "away_team",
    "temp_avg",
    "precipitation",
    "wind_max",
    "rain_category",
    "temp_category",
]

RESULT_LABELS = {"H": "Victoria local", "A": "Victoria visitante", "D": "Empate"}

# Partidos de mañana
MATCHES = [
    {
        "home_team": "Valencia CF",
        "away_team": "FC Barcelona",
        "matchday": 3,
        "lat": 39.4750,
        "lon": -0.3582,
    },
    {
        "home_team": "Deportivo Alavés",
        "away_team": "CA Osasuna",
        "matchday": 3,
        "lat": 42.8459,
        "lon": -2.6862,
    },
]


# ---------------------------------------------------------------------------
# Clima real de mañana desde Open-Meteo
# ---------------------------------------------------------------------------
def get_tomorrow_weather(lat: float, lon: float, date: str) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date,
        "end_date": date,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "windspeed_10m_max",
        ],
        "timezone": "Europe/Madrid",
    }
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast", params=params, timeout=10
    )
    r.raise_for_status()
    data = r.json()["daily"]
    temp_max = data["temperature_2m_max"][0]
    temp_min = data["temperature_2m_min"][0]
    return {
        "temp_avg": round((temp_max + temp_min) / 2, 1),
        "temp_max": temp_max,
        "temp_min": temp_min,
        "precipitation": data["precipitation_sum"][0],
        "wind_max": data["windspeed_10m_max"][0],
    }


# ---------------------------------------------------------------------------
# Preparación de features
# ---------------------------------------------------------------------------
def get_rain_category(p):
    if p == 0:
        return "Seco"
    elif p < 5:
        return "Lluvia ligera"
    elif p < 20:
        return "Lluvia moderada"
    else:
        return "Lluvia fuerte"


def get_temp_category(t):
    if t < 5:
        return "Frío"
    elif t < 15:
        return "Fresco"
    elif t < 25:
        return "Templado"
    else:
        return "Caluroso"


def prepare_features(df, training_data_path="data/gold/ml_features.parquet"):
    train_df = pd.read_parquet(training_data_path)
    categorical_cols = ["home_team", "away_team", "rain_category", "temp_category"]
    for col in categorical_cols:
        le = LabelEncoder()
        le.fit(train_df[col].astype(str))
        df[col] = (
            df[col]
            .astype(str)
            .map(lambda x, le=le: x if x in le.classes_ else le.classes_[0])
        )
        df[col] = le.transform(df[col])
    return df[FEATURE_COLS]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mlflow.set_tracking_uri(MLFLOW_DIR)
    model = mlflow.sklearn.load_model(f"runs:/{BEST_RUN_ID}/random_forest_model")

    print(f"\n📅 Predicciones para mañana {TOMORROW}")
    print("=" * 60)

    for match in MATCHES:
        # Clima real de mañana
        weather = get_tomorrow_weather(match["lat"], match["lon"], TOMORROW)

        row = {
            "home_team": match["home_team"],
            "away_team": match["away_team"],
            "matchday": match["matchday"],
            "temp_avg": weather["temp_avg"],
            "precipitation": weather["precipitation"],
            "wind_max": weather["wind_max"],
            "rain_category": get_rain_category(weather["precipitation"]),
            "temp_category": get_temp_category(weather["temp_avg"]),
        }

        df = pd.DataFrame([row])
        X = prepare_features(df.copy())

        pred = model.predict(X)[0]
        probs = model.predict_proba(X)[0]
        classes = model.classes_

        prob_dict = {cls: round(p * 100, 1) for cls, p in zip(classes, probs)}

        print(f"\n⚽ {match['home_team']} vs {match['away_team']}")
        print(
            f"   🌡  Temp: {weather['temp_avg']}°C (max {weather['temp_max']}° / min {weather['temp_min']}°)"
        )
        print(
            f"   🌧  Lluvia: {weather['precipitation']}mm | Viento: {weather['wind_max']} km/h"
        )
        print(f"   📊 Categorías: {row['temp_category']} / {row['rain_category']}")
        print(f"   🔮 Predicción: {RESULT_LABELS[pred]}")
        print(
            f"   📈 Prob → Local: {prob_dict.get('H', 0)}% | Empate: {prob_dict.get('D', 0)}% | Visitante: {prob_dict.get('A', 0)}%"
        )

    print("\n" + "=" * 60)
    print("Modelo: Random Forest | Experimento 3 | Accuracy: 43%")
