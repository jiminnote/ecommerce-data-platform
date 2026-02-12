-- =====================================================
-- Conversion Funnel Analysis
-- BigQuery SQL for e-commerce funnel analysis
-- =====================================================

-- Full Purchase Funnel by Device Type (Daily)
WITH funnel_steps AS (
    SELECT
        DATE(event_timestamp) AS event_date,
        device_type,
        session_id,
        user_id,
        -- Track each funnel step
        MAX(CASE WHEN event_type = 'page_view' THEN 1 ELSE 0 END) AS has_page_view,
        MAX(CASE WHEN event_type = 'product_view' THEN 1 ELSE 0 END) AS has_product_view,
        MAX(CASE WHEN event_type = 'add_to_cart' THEN 1 ELSE 0 END) AS has_add_to_cart,
        MAX(CASE WHEN event_type = 'begin_checkout' THEN 1 ELSE 0 END) AS has_checkout,
        MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS has_purchase,
        -- First and last event for session timing
        MIN(event_timestamp) AS session_start,
        MAX(event_timestamp) AS session_end,
        COUNT(*) AS total_events
    FROM `${PROJECT_ID}.staging.user_events`
    WHERE DATE(event_timestamp) BETWEEN
        DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
        AND CURRENT_DATE() - 1
    GROUP BY 1, 2, 3, 4
)
SELECT
    event_date,
    device_type,
    -- Absolute numbers
    COUNT(DISTINCT session_id) AS total_sessions,
    COUNTIF(has_page_view = 1) AS step_1_page_view,
    COUNTIF(has_product_view = 1) AS step_2_product_view,
    COUNTIF(has_add_to_cart = 1) AS step_3_add_to_cart,
    COUNTIF(has_checkout = 1) AS step_4_checkout,
    COUNTIF(has_purchase = 1) AS step_5_purchase,
    -- Step-by-step conversion rates
    SAFE_DIVIDE(
        COUNTIF(has_product_view = 1),
        COUNTIF(has_page_view = 1)
    ) AS rate_view_to_product,
    SAFE_DIVIDE(
        COUNTIF(has_add_to_cart = 1),
        COUNTIF(has_product_view = 1)
    ) AS rate_product_to_cart,
    SAFE_DIVIDE(
        COUNTIF(has_checkout = 1),
        COUNTIF(has_add_to_cart = 1)
    ) AS rate_cart_to_checkout,
    SAFE_DIVIDE(
        COUNTIF(has_purchase = 1),
        COUNTIF(has_checkout = 1)
    ) AS rate_checkout_to_purchase,
    -- Overall conversion
    SAFE_DIVIDE(
        COUNTIF(has_purchase = 1),
        COUNT(DISTINCT session_id)
    ) AS overall_conversion_rate,
    -- Session quality metrics
    AVG(total_events) AS avg_events_per_session,
    AVG(
        TIMESTAMP_DIFF(session_end, session_start, SECOND)
    ) AS avg_session_duration_sec
FROM funnel_steps
GROUP BY 1, 2
ORDER BY 1 DESC, 2;


-- Funnel Drop-off Analysis
WITH sequential_events AS (
    SELECT
        session_id,
        user_id,
        event_type,
        event_timestamp,
        LEAD(event_type) OVER (
            PARTITION BY session_id
            ORDER BY event_timestamp
        ) AS next_event_type,
        LEAD(event_timestamp) OVER (
            PARTITION BY session_id
            ORDER BY event_timestamp
        ) AS next_event_timestamp
    FROM `${PROJECT_ID}.staging.user_events`
    WHERE DATE(event_timestamp) = CURRENT_DATE() - 1
        AND event_type IN (
            'page_view', 'product_view', 'add_to_cart',
            'begin_checkout', 'purchase'
        )
)
SELECT
    event_type AS current_step,
    next_event_type AS next_step,
    COUNT(*) AS transition_count,
    AVG(
        TIMESTAMP_DIFF(next_event_timestamp, event_timestamp, SECOND)
    ) AS avg_time_between_steps_sec,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY event_type) AS pct_of_current_step
FROM sequential_events
WHERE next_event_type IS NOT NULL
GROUP BY 1, 2
ORDER BY event_type, transition_count DESC;
