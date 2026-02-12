-- =====================================================
-- Product Analytics Queries
-- BigQuery SQL for product performance analysis
-- =====================================================

-- 1. Product Performance Dashboard
WITH product_views AS (
    SELECT
        CAST(JSON_VALUE(properties, '$.product_id') AS INT64) AS product_id,
        COUNT(*) AS view_count,
        COUNT(DISTINCT user_id) AS unique_viewers,
        COUNT(DISTINCT session_id) AS unique_sessions
    FROM `${PROJECT_ID}.staging.user_events`
    WHERE event_type = 'product_view'
        AND DATE(event_timestamp) = CURRENT_DATE() - 1
    GROUP BY 1
),
product_carts AS (
    SELECT
        CAST(JSON_VALUE(properties, '$.product_id') AS INT64) AS product_id,
        COUNT(*) AS cart_count,
        COUNT(DISTINCT user_id) AS unique_cart_users
    FROM `${PROJECT_ID}.staging.user_events`
    WHERE event_type = 'add_to_cart'
        AND DATE(event_timestamp) = CURRENT_DATE() - 1
    GROUP BY 1
),
product_purchases AS (
    SELECT
        oi.product_id,
        COUNT(DISTINCT o.order_id) AS order_count,
        SUM(oi.quantity) AS total_quantity,
        SUM(oi.subtotal) AS total_revenue
    FROM `${PROJECT_ID}.staging.orders` o
    JOIN `${PROJECT_ID}.staging.order_items` oi ON o.order_id = oi.order_id
    WHERE DATE(o.ordered_at) = CURRENT_DATE() - 1
        AND o.order_status NOT IN ('CANCELLED', 'REFUNDED')
    GROUP BY 1
)
SELECT
    p.product_id,
    p.product_name,
    p.category_l1,
    p.category_l2,
    p.price,
    p.storage_type,
    COALESCE(pv.view_count, 0) AS view_count,
    COALESCE(pv.unique_viewers, 0) AS unique_viewers,
    COALESCE(pc.cart_count, 0) AS cart_count,
    COALESCE(pp.order_count, 0) AS order_count,
    COALESCE(pp.total_revenue, 0) AS total_revenue,
    -- Conversion funnel
    SAFE_DIVIDE(pc.cart_count, pv.view_count) AS view_to_cart_rate,
    SAFE_DIVIDE(pp.order_count, pc.cart_count) AS cart_to_purchase_rate,
    SAFE_DIVIDE(pp.order_count, pv.view_count) AS overall_conversion_rate
FROM `${PROJECT_ID}.staging.products` p
LEFT JOIN product_views pv ON p.product_id = pv.product_id
LEFT JOIN product_carts pc ON p.product_id = pc.product_id
LEFT JOIN product_purchases pp ON p.product_id = pp.product_id
ORDER BY COALESCE(pp.total_revenue, 0) DESC;


-- 2. Category-level Sales Trend (Weekly)
SELECT
    DATE_TRUNC(DATE(ordered_at), WEEK) AS week_start,
    p.category_l1,
    p.storage_type,
    COUNT(DISTINCT o.order_id) AS order_count,
    COUNT(DISTINCT o.user_id) AS unique_customers,
    SUM(oi.subtotal) AS total_revenue,
    AVG(oi.subtotal) AS avg_item_revenue,
    SUM(oi.quantity) AS total_quantity
FROM `${PROJECT_ID}.staging.orders` o
JOIN `${PROJECT_ID}.staging.order_items` oi ON o.order_id = oi.order_id
JOIN `${PROJECT_ID}.staging.products` p ON oi.product_id = p.product_id
WHERE o.order_status NOT IN ('CANCELLED', 'REFUNDED')
    AND DATE(o.ordered_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 WEEK)
GROUP BY 1, 2, 3
ORDER BY 1 DESC, total_revenue DESC;


-- 3. Stock Depletion Alert (products running low)
SELECT
    product_id,
    product_name,
    category_l1,
    stock_quantity,
    price,
    storage_type,
    CASE
        WHEN stock_quantity = 0 THEN '🔴 OUT_OF_STOCK'
        WHEN stock_quantity < 10 THEN '🟡 CRITICAL'
        WHEN stock_quantity < 50 THEN '🟠 LOW'
        ELSE '🟢 NORMAL'
    END AS stock_status
FROM `${PROJECT_ID}.staging.products`
WHERE stock_quantity < 50
ORDER BY stock_quantity ASC;
