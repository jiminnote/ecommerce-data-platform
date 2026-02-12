-- =====================================================
-- ARPPU (Average Revenue Per Paying User)
-- 핀테크 특수성: 중복 결제 제거, 취소/환불 차감
-- Source: mart.revenue_metrics
-- =====================================================

WITH payments AS (
    -- 결제 완료 이벤트만 추출
    SELECT
        DATE(e.event_timestamp) AS dt,
        e.user_id,
        e.properties.transaction_id,
        e.properties.amount AS gross_amount,
        e.properties.payment_method,
        e.properties.merchant_category,
        e.properties.is_first_payment,
        -- 중복 결제 방지: 동일 transaction_id 중 최초 건만 유효
        ROW_NUMBER() OVER (
            PARTITION BY e.properties.transaction_id
            ORDER BY e.event_timestamp ASC
        ) AS txn_rank
    FROM {{ ref('stg_events') }} e
    WHERE e.event_name = 'payment.complete.payment_success'
      AND e.properties.transaction_id IS NOT NULL
      AND e.properties.amount > 0
),

valid_payments AS (
    SELECT * FROM payments WHERE txn_rank = 1   -- 중복 제거
),

refunds AS (
    -- 환불 건: revenue에서 차감
    SELECT
        DATE(e.event_timestamp) AS dt,
        e.user_id,
        e.properties.transaction_id,
        e.properties.amount AS refund_amount
    FROM {{ ref('stg_events') }} e
    WHERE e.event_name = 'payment.complete.refund'
      AND e.properties.transaction_id IS NOT NULL
),

daily_revenue AS (
    SELECT
        p.dt,
        p.user_id,
        p.transaction_id,
        p.gross_amount,
        COALESCE(r.refund_amount, 0) AS refund_amount,
        p.gross_amount - COALESCE(r.refund_amount, 0) AS net_amount,
        p.payment_method,
        p.merchant_category,
        p.is_first_payment
    FROM valid_payments p
    LEFT JOIN refunds r
        ON p.transaction_id = r.transaction_id
)

SELECT
    dt,

    -- 결제 유저 수
    COUNT(DISTINCT user_id) AS paying_users,

    -- 총 거래 건수
    COUNT(transaction_id) AS total_transactions,

    -- 매출 지표
    SUM(gross_amount) AS gross_revenue,
    SUM(refund_amount) AS total_refunds,
    SUM(net_amount) AS net_revenue,

    -- ★ ARPPU = Net Revenue / Paying Users
    SAFE_DIVIDE(
        SUM(net_amount),
        COUNT(DISTINCT user_id)
    ) AS arppu,

    -- 평균 결제 금액
    SAFE_DIVIDE(
        SUM(net_amount),
        COUNT(transaction_id)
    ) AS avg_transaction_amount,

    -- 첫 결제 유저 비율
    SAFE_DIVIDE(
        COUNT(DISTINCT CASE WHEN is_first_payment = TRUE THEN user_id END),
        COUNT(DISTINCT user_id)
    ) * 100 AS first_payment_user_pct,

    -- 결제 수단별 비중
    SAFE_DIVIDE(
        COUNTIF(payment_method = 'card'),
        COUNT(*)
    ) * 100 AS card_pct,
    SAFE_DIVIDE(
        COUNTIF(payment_method = 'quickpay_balance'),
        COUNT(*)
    ) * 100 AS quickpay_balance_pct

FROM daily_revenue
WHERE net_amount > 0   -- 전액 환불 건 제외
GROUP BY dt
ORDER BY dt DESC
