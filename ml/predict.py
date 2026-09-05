import os
import pandas as pd
import mlflow
import mlflow.sklearn
from sklearn.preprocessing import LabelEncoder
from dotenv import load_dotenv

load_dotenv()

MLFLOW_DIR = "sqlite:///mlflow.db"
BEST_RUN_ID = "dcbb04ba644448c092f61b2e4bc8397e"

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

RESULT_LABELS = {
    "H": "Victoria local",
    "A": "Victoria visitante",
    "D": "Empate",
}


# ---------------------------------------------------------------------------
# Carga del modelo desde MLflow
# ---------------------------------------------------------------------------
def load_model():
    mlflow.set_tracking_uri(MLFLOW_DIR)
    model_uri = f"runs:/{BEST_RUN_ID}/random_forest_model"
    model = mlflow.sklearn.load_model(model_uri)
    print(f"Modelo cargado desde run: {BEST_RUN_ID}")
    return model


# ---------------------------------------------------------------------------
# Preparación de features
# ---------------------------------------------------------------------------
def prepare_features(df: pd.DataFrame, training_data_path: str) -> pd.DataFrame:
    """
    Codifica las variables categóricas usando los mismos valores
    que había en el dataset de entrenamiento.
    """
    train_df = pd.read_parquet(training_data_path)
    categorical_cols = ["home_team", "away_team", "rain_category", "temp_category"]

    for col in categorical_cols:
        le = LabelEncoder()
        le.fit(train_df[col].astype(str))

        # Valores desconocidos los mapeamos al más frecuente del training
        df[col] = (
            df[col].astype(str).map(lambda x: x if x in le.classes_ else le.classes_[0])
        )
        df[col] = le.transform(df[col])

    return df[FEATURE_COLS]


# ---------------------------------------------------------------------------
# Predicción
# ---------------------------------------------------------------------------
def predict(
    matches: list[dict], training_data_path: str = "data/gold/ml_features.parquet"
):
    """
    Predice el resultado de una lista de partidos.

    Args:
        matches: lista de dicts con los campos de FEATURE_COLS
        training_data_path: path al Parquet de entrenamiento (para el encoder)

    Returns:
        DataFrame con predicciones y probabilidades
    """
    model = load_model()
    df = pd.DataFrame(matches)

    # Categorías de clima
    df["rain_category"] = df["precipitation"].apply(
        lambda p: (
            "Seco"
            if p == 0
            else "Lluvia ligera"
            if p < 5
            else "Lluvia moderada"
            if p < 20
            else "Lluvia fuerte"
        )
    )
    df["temp_category"] = df["temp_avg"].apply(
        lambda t: (
            "Frío"
            if t < 5
            else "Fresco"
            if t < 15
            else "Templado"
            if t < 25
            else "Caluroso"
        )
    )

    X = prepare_features(df.copy(), training_data_path)

    # Predicción y probabilidades
    predictions = model.predict(X)
    probabilities = model.predict_proba(X)
    classes = model.classes_

    results = []
    for i, (match, pred) in enumerate(zip(matches, predictions)):
        probs = {
            cls: round(probabilities[i][j] * 100, 1) for j, cls in enumerate(classes)
        }
        results.append(
            {
                "home_team": match["home_team"],
                "away_team": match["away_team"],
                "matchday": match["matchday"],
                "temp_avg": match["temp_avg"],
                "precipitation": match["precipitation"],
                "prediction": pred,
                "prediction_label": RESULT_LABELS[pred],
                "prob_H": probs.get("H", 0),
                "prob_D": probs.get("D", 0),
                "prob_A": probs.get("A", 0),
            }
        )

    return pd.DataFrame(results)


if __name__ == "__main__":
    # Partidos de ejemplo para predecir
    upcoming_matches = [
        {
            "home_team": "Athletic Club",
            "away_team": "FC Barcelona",
            "matchday": 20,
            "temp_avg": 8.0,  # Frío en Bilbao en enero
            "precipitation": 12.0,  # Lluvia moderada
            "wind_max": 25.0,
        },
        {
            "home_team": "Real Madrid CF",
            "away_team": "Club Atlético de Madrid",
            "matchday": 20,
            "temp_avg": 6.0,
            "precipitation": 0.0,  # Seco
            "wind_max": 15.0,
        },
        {
            "home_team": "FC Barcelona",
            "away_team": "Real Madrid CF",
            "matchday": 28,
            "temp_avg": 18.0,  # Templado en Barcelona en abril
            "precipitation": 2.0,  # Lluvia ligera
            "wind_max": 10.0,
        },
    ]

    df_predictions = predict(upcoming_matches)

    print("\n" + "=" * 60)
    print("PREDICCIONES")
    print("=" * 60)
    for _, row in df_predictions.iterrows():
        print(f"\n{row['home_team']} vs {row['away_team']}")
        print(
            f"  Jornada: {row['matchday']} | Temp: {row['temp_avg']}°C | Lluvia: {row['precipitation']}mm"
        )
        print(f"  Predicción: {row['prediction_label']}")
        print(
            f"  Probabilidades → Local: {row['prob_H']}% | Empate: {row['prob_D']}% | Visitante: {row['prob_A']}%"
        )
