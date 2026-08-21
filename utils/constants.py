# ---------------------------------------------------------------------------
# Códigos WMO (World Meteorological Organization)
# Estándar usado por Open-Meteo para describir condiciones meteorológicas
# Ref: https://open-meteo.com/en/docs#weathervariables
# ---------------------------------------------------------------------------
WMO_CODES = {
    0: "Despejado",
    1: "Principalmente despejado",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Niebla",
    48: "Niebla con escarcha",
    51: "Llovizna ligera",
    53: "Llovizna moderada",
    55: "Llovizna densa",
    61: "Lluvia ligera",
    63: "Lluvia moderada",
    65: "Lluvia fuerte",
    71: "Nevada ligera",
    73: "Nevada moderada",
    75: "Nevada fuerte",
    80: "Chubascos ligeros",
    81: "Chubascos moderados",
    82: "Chubascos violentos",
    95: "Tormenta",
    96: "Tormenta con granizo",
    99: "Tormenta con granizo fuerte",
}

# ---------------------------------------------------------------------------
# Competiciones disponibles en el plan gratuito de football-data.org
# ---------------------------------------------------------------------------
COMPETITIONS = {
    "PD": "La Liga (Primera División)",
    "CL": "Champions League",
    "PL": "Premier League",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
}

# ---------------------------------------------------------------------------
# Resultado de partido — mapeo desde la API a etiqueta corta
# ---------------------------------------------------------------------------
WINNER_MAP = {
    "HOME_TEAM": "H",
    "AWAY_TEAM": "A",
    "DRAW": "D",
}

# ---------------------------------------------------------------------------
# Rutas por defecto del proyecto (relativas a la raíz)
# ---------------------------------------------------------------------------
BRONZE_FOOTBALL = "data/bronze/football"
BRONZE_WEATHER = "data/bronze/weather"
SILVER_PATH = "data/silver"
GOLD_PATH = "data/gold"
STADIUMS_PATH = "data/stadiums.json"
