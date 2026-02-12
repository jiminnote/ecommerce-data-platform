-- =====================================================
-- User Behavior Analysis Queries
-- BigQuery SQL for analyzing user behavior patterns
-- =====================================================

-- 1. Daily Active Users (DAU) with retention cohort
WITH daily_users AS (
    SELECT
        DATE(event_timestamp) AS event_date,
        user_id,
        device_type,
        COUNT(*) AS event_count,
        COUNT(DISTINCT event_type) AS unique_event_types,
        MIN(event_timestamp) AS first_event_at,
        MAX(event_timestamp) AS last_event_at
    FROM `${PROJECT_ID}.staging.user_events`
    WHERE user_id IS NOT NULL
        AND DATE(event_timestamp) BETWEEN
            DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
            AND CURRENT_DATE()
    GROUP BY 1, 2, 3
),
user_first_seen AS (
    SELECT
        user_id,
        MIN(event_date) AS cohort_date
    FROM daily_users
    GROUP BY 1
)
SELECT
    du.event_date,
    ufs.cohort_date,
    DATE_DIFF(du.event_date, ufs.cohort_date, DAY) AS days_since_first_visit,
    du.device_type,
    COUNT(DISTINCT du.user_id) AS active_users,
    AVG(du.event_count) AS avg_events_per_user,
    AVG(du.unique_event_types) AS avg_event_types
FROM daily_users du
JOIN user_first_seen ufs ON du.user_id = ufs.user_id
GROUP BY 1, 2, 3, 4
ORDER BY 1 DESC, 3;


-- 2. Session Analysis (avg duration, pages per session, bounce rate)
WITH session_events AS (
    SELECT
        session_id,
        user_id,
        device_type,
        event_type,
        event_timestamp,
        page_url,
        ROW_NUMBER() OVER (
            PARTITION BY session_id
            ORDER BY event_timestamp
        ) AS event_order
    FROM `${PROJECT_ID}.staging.user_events`
    WHERE DATE(event_timestamp) = CURRENT_DATE() - 1
),
session_summary AS (
    SELECT
        session_id,
        user_id,
        device_type,
        COUNT(*) AS total_events,
        COUNT(DISTINCT page_url) AS unique_pages,
        COUNT(DISTINCT event_type) AS unique_event_types,
        MIN(event_timestamp) AS session_start,
        MAX(event_timestamp) AS session_end,
        TIMESTAMP_DIFF(
            MAX(event_timestamp),
            MIN(event_timestamp),
            SECOND
        ) AS session_duration_sec,
        COUNTIF(event_type = 'purchase') > 0 AS has_purchase
    FROM session_events
    GROUP BY 1, 2, 3
)
SELECT
    device_type,
    COUNT(*) AS total_sessions,
    AVG(session_duration_sec) AS avg_session_duration_sec,
    AVG(unique_pages) AS avg_pages_per_session,
    AVG(total_events) AS avg_events_per_session,
    COUNTIF(total_events = 1) / COUNT(*) AS bounce_rate,
    COUNTIF(has_purchase) / COUNT(*) AS conversion_rate
FROM session_summary
GROUP BY 1
ORDER BY total_sessions DESC;


-- 3. Real-time trending search queries (last 1 hour)
SELECT
    JSON_VALUE(properties, '$.search_query') AS search_query,
    COUNT(*) AS search_count,
    COUNT(DISTINCT user_id) AS unique_searchers,
    COUNT(DISTINCT session_id) AS unique_sessions,
    AVG(CAST(JSON_VALUE(properties, '$.result_count') AS INT64)) AS avg_result_count,
    COUNTIF(
        JSON_VALUE(properties, '$.result_count') = '0'
    ) AS zero_result_count
FROM `${PROJECT_ID}.staging.user_events`
WHERE event_type = 'search'
    AND event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
GROUP BY 1
HAVING search_count >= 3
ORDER BY search_count DESC
LIMIT 50;
