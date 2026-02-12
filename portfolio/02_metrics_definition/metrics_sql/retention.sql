-- =====================================================
-- Retention Analysis (Cohort-based)
-- Day 1, 3, 7, 14, 30 리텐션 산출
-- 코호트 기준: 유저의 최초 로그인 완료 일자
-- =====================================================

WITH user_first_login AS (
    -- 코호트 기준일: 유저별 최초 로그인 완료 시점
    SELECT
        user_id,
        MIN(DATE(event_timestamp)) AS cohort_date
    FROM {{ ref('stg_events') }}
    WHERE event_name = 'auth.complete.login'
      AND user_id NOT LIKE 'anonymous_%'
    GROUP BY user_id
),

user_activity AS (
    -- 유저별 활동 일자 (로그인 완료 기준)
    SELECT DISTINCT
        user_id,
        DATE(event_timestamp) AS activity_date
    FROM {{ ref('stg_events') }}
    WHERE event_name = 'auth.complete.login'
      AND user_id NOT LIKE 'anonymous_%'
),

cohort_size AS (
    -- 코호트별 유저 수
    SELECT
        cohort_date,
        COUNT(DISTINCT user_id) AS cohort_users
    FROM user_first_login
    GROUP BY cohort_date
),

retention_raw AS (
    -- 코호트 기준일 대비 N일 후 복귀 여부
    SELECT
        f.cohort_date,
        DATE_DIFF(a.activity_date, f.cohort_date, DAY) AS day_n,
        COUNT(DISTINCT a.user_id) AS returned_users
    FROM user_first_login f
    INNER JOIN user_activity a
        ON f.user_id = a.user_id
        AND a.activity_date >= f.cohort_date
    WHERE DATE_DIFF(a.activity_date, f.cohort_date, DAY) <= 30
    GROUP BY 1, 2
)

-- 최종 리텐션 테이블: 코호트별 × Day N별
SELECT
    r.cohort_date,
    c.cohort_users,
    r.day_n,
    r.returned_users,
    SAFE_DIVIDE(r.returned_users, c.cohort_users) * 100 AS retention_rate,

    -- 주요 포인트 리텐션 (피벗)
    MAX(CASE WHEN r.day_n = 1 THEN
        SAFE_DIVIDE(r.returned_users, c.cohort_users) * 100
    END) OVER (PARTITION BY r.cohort_date) AS d1_retention,

    MAX(CASE WHEN r.day_n = 3 THEN
        SAFE_DIVIDE(r.returned_users, c.cohort_users) * 100
    END) OVER (PARTITION BY r.cohort_date) AS d3_retention,

    MAX(CASE WHEN r.day_n = 7 THEN
        SAFE_DIVIDE(r.returned_users, c.cohort_users) * 100
    END) OVER (PARTITION BY r.cohort_date) AS d7_retention,

    MAX(CASE WHEN r.day_n = 14 THEN
        SAFE_DIVIDE(r.returned_users, c.cohort_users) * 100
    END) OVER (PARTITION BY r.cohort_date) AS d14_retention,

    MAX(CASE WHEN r.day_n = 30 THEN
        SAFE_DIVIDE(r.returned_users, c.cohort_users) * 100
    END) OVER (PARTITION BY r.cohort_date) AS d30_retention

FROM retention_raw r
JOIN cohort_size c ON r.cohort_date = c.cohort_date
WHERE r.cohort_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 60 DAY)
ORDER BY r.cohort_date DESC, r.day_n ASC
