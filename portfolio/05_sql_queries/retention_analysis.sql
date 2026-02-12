-- =====================================================
-- 코호트 기반 리텐션 분석 (Pivot 포함)
-- 난이도: ★★★★☆
--
-- 가장 난이도 높은 쿼리:
-- - CTE 4단계 체이닝
-- - Window Function + PIVOT
-- - 코호트 그룹 × Day N 매트릭스 생성
-- =====================================================

WITH
-- Step 1: 유저별 최초 활동일 (코호트 기준)
user_cohort AS (
    SELECT
        user_id,
        MIN(DATE(event_timestamp)) AS cohort_date
    FROM staging.events
    WHERE event_name = 'auth.complete.login'
      AND user_id NOT LIKE 'anonymous_%'
      AND DATE(event_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 60 DAY)
    GROUP BY user_id
),

-- Step 2: 유저별 일별 활동 기록
daily_activity AS (
    SELECT DISTINCT
        user_id,
        DATE(event_timestamp) AS active_date
    FROM staging.events
    WHERE event_name = 'auth.complete.login'
      AND user_id NOT LIKE 'anonymous_%'
),

-- Step 3: 코호트 × Day N 매트릭스
cohort_retention AS (
    SELECT
        uc.cohort_date,
        DATE_DIFF(da.active_date, uc.cohort_date, DAY) AS day_n,
        COUNT(DISTINCT uc.user_id) AS retained_users
    FROM user_cohort uc
    INNER JOIN daily_activity da
        ON uc.user_id = da.user_id
        AND da.active_date >= uc.cohort_date
        AND DATE_DIFF(da.active_date, uc.cohort_date, DAY) BETWEEN 0 AND 30
    GROUP BY 1, 2
),

-- Step 4: 코호트 사이즈
cohort_sizes AS (
    SELECT
        cohort_date,
        COUNT(DISTINCT user_id) AS cohort_size
    FROM user_cohort
    GROUP BY 1
)

-- ★ 최종 Pivot 테이블: 코호트별 D0~D30 리텐션율
SELECT
    cr.cohort_date,
    cs.cohort_size,

    -- D0 (= 100%)
    MAX(CASE WHEN day_n = 0 THEN
        ROUND(SAFE_DIVIDE(retained_users, cs.cohort_size) * 100, 1)
    END) AS d0,

    -- D1 리텐션
    MAX(CASE WHEN day_n = 1 THEN
        ROUND(SAFE_DIVIDE(retained_users, cs.cohort_size) * 100, 1)
    END) AS d1,

    -- D3 리텐션
    MAX(CASE WHEN day_n = 3 THEN
        ROUND(SAFE_DIVIDE(retained_users, cs.cohort_size) * 100, 1)
    END) AS d3,

    -- D7 리텐션 (핵심 지표)
    MAX(CASE WHEN day_n = 7 THEN
        ROUND(SAFE_DIVIDE(retained_users, cs.cohort_size) * 100, 1)
    END) AS d7,

    -- D14 리텐션
    MAX(CASE WHEN day_n = 14 THEN
        ROUND(SAFE_DIVIDE(retained_users, cs.cohort_size) * 100, 1)
    END) AS d14,

    -- D30 리텐션 (장기 지표)
    MAX(CASE WHEN day_n = 30 THEN
        ROUND(SAFE_DIVIDE(retained_users, cs.cohort_size) * 100, 1)
    END) AS d30

FROM cohort_retention cr
JOIN cohort_sizes cs ON cr.cohort_date = cs.cohort_date
GROUP BY cr.cohort_date, cs.cohort_size
HAVING cs.cohort_size >= 50   -- 통계적으로 유의미한 코호트만
ORDER BY cr.cohort_date DESC
