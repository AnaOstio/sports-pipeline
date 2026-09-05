-- Calcula estadísticas agregadas por equipo y condición climática.
-- Este modelo alimenta el mart final y las features del modelo ML.

with matches as (
    select * from {{ ref('stg_matches') }}
),

-- Estadísticas como equipo LOCAL
home_stats as (
    select
        home_team                           as team,
        match_date_only,
        matchday,
        rain_category,
        temp_category,
        temp_avg,
        precipitation,
        wind_max,

        -- Resultado desde la perspectiva del equipo local
        case result
            when 'H' then 'W'
            when 'A' then 'L'
            when 'D' then 'D'
        end                                 as result,

        home_score                          as goals_scored,
        away_score                          as goals_conceded,
        total_goals,
        1                                   as is_home

    from matches
),

-- Estadísticas como equipo VISITANTE
away_stats as (
    select
        away_team                           as team,
        match_date_only,
        matchday,
        rain_category,
        temp_category,
        temp_avg,
        precipitation,
        wind_max,

        -- Resultado desde la perspectiva del equipo visitante
        case result
            when 'A' then 'W'
            when 'H' then 'L'
            when 'D' then 'D'
        end                                 as result,

        away_score                          as goals_scored,
        home_score                          as goals_conceded,
        total_goals,
        0                                   as is_home

    from matches
),

-- Unimos local y visitante
all_matches as (
    select * from home_stats
    union all
    select * from away_stats
),

-- Agregamos por equipo y condición climática
team_stats as (
    select
        team,
        rain_category,
        temp_category,

        -- Partidos
        count(*)                                                    as total_matches,
        countif(result = 'W')                                       as wins,
        countif(result = 'D')                                       as draws,
        countif(result = 'L')                                       as losses,
        countif(is_home = 1)                                        as home_matches,
        countif(is_home = 0)                                        as away_matches,

        -- Porcentajes
        round(countif(result = 'W') / count(*) * 100, 1)           as win_pct,
        round(countif(result = 'D') / count(*) * 100, 1)           as draw_pct,
        round(countif(result = 'L') / count(*) * 100, 1)           as loss_pct,

        -- Goles
        sum(goals_scored)                                           as total_goals_scored,
        sum(goals_conceded)                                         as total_goals_conceded,
        round(avg(goals_scored), 2)                                 as avg_goals_scored,
        round(avg(goals_conceded), 2)                               as avg_goals_conceded,

        -- Clima
        round(avg(temp_avg), 1)                                     as avg_temp,
        round(avg(precipitation), 1)                                as avg_precipitation,
        round(avg(wind_max), 1)                                     as avg_wind

    from all_matches
    group by team, rain_category, temp_category
)

select * from team_stats
order by team, rain_category, temp_category