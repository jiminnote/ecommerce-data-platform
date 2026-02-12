-- =====================================================
-- dbt Test: ARPPU는 합리적 범위 내여야 한다
-- 이상치 탐지 (평균 ± 3σ 범위 이탈)
-- =====================================================

WITH stats AS (
    SELECT
        AVG(arppu) AS avg_arppu,
        STDDEV(arppu) AS std_arppu
    FROM {{ ref('mart_revenue') }}
    WHERE dt >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
      AND arppu IS NOT NULL
)

SELECT
    r.dt,
    r.arppu,
    s.avg_arppu,
    s.std_arppu,
    ABS(r.arppu - s.avg_arppu) / NULLIF(s.std_arppu, 0) AS z_score
FROM {{ ref('mart_revenue') }} r
CROSS JOIN stats s
WHERE r.dt = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
  AND ABS(r.arppu - s.avg_arppu) / NULLIF(s.std_arppu, 0) > 3
