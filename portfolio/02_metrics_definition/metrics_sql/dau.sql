-- =====================================================
-- DAU / WAU / MAU 산출 쿼리
-- Source: mart.daily_active_users
-- Metric Dictionary 정의를 정확히 반영
-- =====================================================

-- DAU: 해당 일자에 로그인 완료한 고유 유저 수
-- 정의: auth.complete.login 이벤트 기준 (앱 실행만으로는 Active 아님)
WITH daily_logins AS (
    SELECT
        DATE(event_timestamp) AS dt,
        user_id,
        device_type,
        MIN(event_timestamp) AS first_login_at,
        COUNT(*) AS login_count
    FROM {{ ref('stg_events') }}
    WHERE event_name = 'auth.complete.login'
      AND user_id NOT LIKE 'anonymous_%'   -- 비로그인 유저 제외
      AND DATE(event_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
    GROUP BY 1, 2, 3
)

SELECT
    dt,
    COUNT(DISTINCT user_id) AS dau,

    -- Rolling WAU (최근 7일)
    COUNT(DISTINCT user_id) OVER (
        ORDER BY dt
        RANGE BETWEEN INTERVAL 6 DAY PRECEDING AND CURRENT ROW
    ) AS wau,

    -- Rolling MAU (최근 30일)
    COUNT(DISTINCT user_id) OVER (
        ORDER BY dt
        RANGE BETWEEN INTERVAL 29 DAY PRECEDING AND CURRENT ROW
    ) AS mau,

    -- Stickiness (DAU / MAU)
    SAFE_DIVIDE(
        COUNT(DISTINCT user_id),
        COUNT(DISTINCT user_id) OVER (
            ORDER BY dt
            RANGE BETWEEN INTERVAL 29 DAY PRECEDING AND CURRENT ROW
        )
    ) * 100 AS stickiness_pct,

    -- 디바이스별 분포
    COUNTIF(device_type = 'ios') AS dau_ios,
    COUNTIF(device_type = 'android') AS dau_android,
    COUNTIF(device_type = 'web') AS dau_web

FROM daily_logins
GROUP BY dt
ORDER BY dt DESC
