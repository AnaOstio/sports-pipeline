import os
import pandas as pd
import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, accuracy_score, f1_score
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
DATA_PATH = "data/gold/ml_features.parquet"
MLFLOW_DIR = "sqlite:///mlflow.db"
EXPERIMENT = "sports_result_prediction"

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
TARGET_COL = "result"


# ---------------------------------------------------------------------------
# Carga y preparación de datos
# ---------------------------------------------------------------------------
def load_and_prepare(path: str):
    df = pd.read_parquet(path)
    print(f"Dataset cargado: {len(df)} filas")

    # Codificamos variables categóricas con LabelEncoder
    encoders = {}
    categorical_cols = ["home_team", "away_team", "rain_category", "temp_category"]

    for col in categorical_cols:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        encoders[col] = le

    X = df[FEATURE_COLS]
    y = df[TARGET_COL]

    return X, y, encoders


# ---------------------------------------------------------------------------
# Entrenamiento con MLflow
# ---------------------------------------------------------------------------
def train(n_estimators: int = 100, max_depth: int = None, min_samples_split: int = 2):
    mlflow.set_tracking_uri(MLFLOW_DIR)
    mlflow.set_experiment(EXPERIMENT)

    X, y, encoders = load_and_prepare(DATA_PATH)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"Train: {len(X_train)} | Test: {len(X_test)}")

    with mlflow.start_run():
        # Parámetros
        params = {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "min_samples_split": min_samples_split,
            "random_state": 42,
        }
        mlflow.log_params(params)

        # Entrenamiento
        model = RandomForestClassifier(**params)
        model.fit(X_train, y_train)

        # Evaluación en test
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        f1_macro = f1_score(y_test, y_pred, average="macro")
        f1_weighted = f1_score(y_test, y_pred, average="weighted")

        # Cross-validation para una métrica más robusta
        cv_scores = cross_val_score(model, X, y, cv=5, scoring="accuracy")

        # Métricas
        metrics = {
            "accuracy": round(accuracy, 4),
            "f1_macro": round(f1_macro, 4),
            "f1_weighted": round(f1_weighted, 4),
            "cv_mean": round(cv_scores.mean(), 4),
            "cv_std": round(cv_scores.std(), 4),
        }
        mlflow.log_metrics(metrics)

        # Importancia de features
        feature_importance = pd.Series(
            model.feature_importances_, index=FEATURE_COLS
        ).sort_values(ascending=False)

        print(f"\n{'=' * 50}")
        print(f"Parámetros: {params}")
        print(f"\nMétricas:")
        for k, v in metrics.items():
            print(f"  {k}: {v}")
        print(f"\nImportancia de features:")
        print(feature_importance.round(3).to_string())
        print(f"\nReporte completo:")
        print(classification_report(y_test, y_pred))

        # Guardamos el modelo en MLflow
        mlflow.sklearn.log_model(model, "random_forest_model")

        run_id = mlflow.active_run().info.run_id
        print(f"\nRun ID: {run_id}")
        print(f"Para ver en MLflow UI: mlflow ui --backend-store-uri {MLFLOW_DIR}")

        return model, metrics, run_id


# ---------------------------------------------------------------------------
# Comparamos 3 configuraciones distintas
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 50)
    print("Experimento 1: Random Forest base")
    print("=" * 50)
    train(n_estimators=100, max_depth=None, min_samples_split=2)

    print("\n" + "=" * 50)
    print("Experimento 2: Árbol más profundo")
    print("=" * 50)
    train(n_estimators=200, max_depth=10, min_samples_split=2)

    print("\n" + "=" * 50)
    print("Experimento 3: Árbol más conservador")
    print("=" * 50)
    train(n_estimators=100, max_depth=5, min_samples_split=5)

    print("\n✅ Los 3 experimentos completados.")
    print("Abre la UI de MLflow para comparar:")
    print("  mlflow ui --backend-store-uri mlruns")
