-- Limpieza y tipado básico de la tabla raw.
-- Este modelo es la única referencia a raw_matches en todo el proyecto.

with source as (
    select * from {{ source('sports_dbt', 'raw_matches') }}
),

renamed as (
    select
        -- IDs
        cast(match_id      as INT64)      as match_id,
        cast(matchday      as INT64)      as matchday,

        -- Fechas
        cast(match_date    as TIMESTAMP)  as match_date,
        cast(match_date_only as DATE)     as match_date_only,

        -- Equipos
        home_team,
        away_team,

        -- Marcador
        cast(home_score    as INT64)      as home_score,
        cast(away_score    as INT64)      as away_score,
        cast(total_goals   as INT64)      as total_goals,

        -- Resultado: H / A / D
        result,

        -- Estadio y ciudad
        city,
        stadium,

        -- Clima
        cast(temp_avg      as FLOAT64)    as temp_avg,
        cast(temp_max      as FLOAT64)    as temp_max,
        cast(temp_min      as FLOAT64)    as temp_min,
        cast(precipitation as FLOAT64)    as precipitation,
        cast(wind_max      as FLOAT64)    as wind_max,
        cast(weather_code  as INT64)      as weather_code,
        weather_desc,

        -- Categorías de clima útiles para el ML
        case
            when precipitation = 0              then 'Seco'
            when precipitation < 5              then 'Lluvia ligera'
            when precipitation < 20             then 'Lluvia moderada'
            else                                     'Lluvia fuerte'
        end as rain_category,

        case
            when temp_avg < 5                   then 'Frío'
            when temp_avg between 5 and 15      then 'Fresco'
            when temp_avg between 15 and 25     then 'Templado'
            else                                     'Caluroso'
        end as temp_category

    from source
)

select * from renamed