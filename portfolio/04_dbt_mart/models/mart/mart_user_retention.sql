-- =====================================================
-- Mart: mart_user_retention
-- 코호트 기반 리텐션 분석 테이블
-- =====================================================

{{
    config(
        materialized='table',
        partition_by={'field': 'cohort_date', 'data_type': 'date'},
        description='코호트 기반 유저 리텐션 (D1~D30). Tableau 리텐션 히트맵 소스.'
    )
}}

WITH first_login AS (
    SELECT
        user_id,
        MIN(DATE(event_timestamp)) AS cohort_date
    FROM {{ ref('stg_events') }}
    WHERE event_name = 'auth.complete.login'
      AND user_id NOT LIKE 'anonymous_%'
    GROUP BY user_id
),

daily_activity AS (
    SELECT DISTINCT
        user_id,
        DATE(event_timestamp) AS activity_date
    FROM {{ ref('stg_events') }}
    WHERE event_name = 'auth.complete.login'
      AND user_id NOT LIKE 'anonymous_%'
),

retention AS (
    SELECT
        f.cohort_date,
        DATE_DIFF(a.activity_date, f.cohort_date, DAY) AS day_n,
        COUNT(DISTINCT f.user_id) AS returned_users
    FROM first_login f
    INNER JOIN daily_activity a
        ON f.user_id = a.user_id
        AND a.activity_date >= f.cohort_date
        AND DATE_DIFF(a.activity_date, f.cohort_date, DAY) <= 30
    GROUP BY 1, 2
),

cohort_size AS (
    SELECT
        cohort_date,
        COUNT(DISTINCT user_id) AS cohort_users
    FROM first_login
    GROUP BY 1
)

SELECT
    r.cohort_date,
    c.cohort_users,
    r.day_n,
    r.returned_users,
    SAFE_DIVIDE(r.returned_users, c.cohort_users) * 100 AS retention_rate
FROM retention r
JOIN cohort_size c ON r.cohort_date = c.cohort_date
WHERE r.cohort_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 60 DAY)
ORDER BY r.cohort_date DESC, r.day_n ASC
