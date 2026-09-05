-- Tabla final lista para el dashboard de Looker Studio y el modelo ML.
-- Combina estadísticas de rendimiento por equipo con contexto climático.

with team_stats as (
    select * from {{ ref('int_team_stats') }}
),

-- Ranking general por equipo (sumando todos los partidos independiente del clima)
overall as (
    select
        team,
        sum(total_matches)          as total_matches,
        sum(wins)                   as total_wins,
        sum(draws)                  as total_draws,
        sum(losses)                 as total_losses,
        sum(total_goals_scored)     as total_goals_scored,
        sum(total_goals_conceded)   as total_goals_conceded,
        round(
            sum(wins) / sum(total_matches) * 100, 1
        )                           as overall_win_pct
    from team_stats
    group by team
),

final as (
    select
        -- Equipo
        ts.team,

        -- Contexto climático
        ts.rain_category,
        ts.temp_category,

        -- Rendimiento en esta condición climática
        ts.total_matches,
        ts.wins,
        ts.draws,
        ts.losses,
        ts.win_pct,
        ts.draw_pct,
        ts.loss_pct,

        -- Goles en esta condición climática
        ts.total_goals_scored,
        ts.total_goals_conceded,
        ts.avg_goals_scored,
        ts.avg_goals_conceded,

        -- Clima
        ts.avg_temp,
        ts.avg_precipitation,
        ts.avg_wind,

        -- Rendimiento global del equipo (para comparar)
        ov.overall_win_pct,
        ov.total_wins                   as season_wins,
        ov.total_matches                as season_matches,

        -- Diferencia: ¿rinde mejor o peor en esta condición climática?
        round(ts.win_pct - ov.overall_win_pct, 1) as win_pct_vs_average

    from team_stats ts
    left join overall ov on ts.team = ov.team
)

select * from final
order by team, win_pct_vs_average desc