-- =====================================================
-- 매출 분석 (Transaction Consistency 반영)
-- 난이도: ★★★★☆
--
-- 핀테크 금융 데이터의 특수성:
-- - 중복 결제 제거
-- - 부분 환불 처리
-- - 취소 건 완전 제외
-- - 결제 수단별/가맹점별 크로스 분석
-- =====================================================

WITH
-- 유효 결제 (중복 제거 + 취소 제외)
valid_payments AS (
    SELECT
        DATE(event_timestamp) AS dt,
        user_id,
        properties.transaction_id,
        properties.amount,
        properties.payment_method,
        properties.merchant_category,
        properties.is_first_payment,
        ROW_NUMBER() OVER (
            PARTITION BY properties.transaction_id
            ORDER BY event_timestamp ASC
        ) AS txn_rank
    FROM staging.events
    WHERE event_name = 'payment.complete.payment_success'
      AND properties.amount > 0
      AND properties.transaction_id IS NOT NULL
),

-- 환불 건 (부분 환불 포함)
refunds AS (
    SELECT
        properties.transaction_id,
        SUM(properties.amount) AS refund_total
    FROM staging.events
    WHERE event_name = 'payment.complete.refund'
    GROUP BY 1
),

-- Net Revenue 산출
net_payments AS (
    SELECT
        p.dt,
        p.user_id,
        p.transaction_id,
        p.amount AS gross,
        COALESCE(r.refund_total, 0) AS refund,
        p.amount - COALESCE(r.refund_total, 0) AS net,
        p.payment_method,
        p.merchant_category,
        p.is_first_payment
    FROM valid_payments p
    LEFT JOIN refunds r ON p.transaction_id = r.transaction_id
    WHERE p.txn_rank = 1  -- 중복 제거
),

-- 일별 집계
daily_metrics AS (
    SELECT
        dt,
        COUNT(DISTINCT user_id) AS paying_users,
        COUNT(transaction_id) AS txn_count,
        SUM(gross) AS gross_revenue,
        SUM(refund) AS total_refund,
        SUM(net) AS net_revenue,
        SAFE_DIVIDE(SUM(net), COUNT(DISTINCT user_id)) AS arppu,
        SAFE_DIVIDE(SUM(net), COUNT(transaction_id)) AS avg_txn_amount,
        COUNT(DISTINCT CASE WHEN is_first_payment THEN user_id END) AS new_payers
    FROM net_payments
    WHERE net > 0
    GROUP BY dt
)

SELECT
    dm.*,

    -- 전일 대비 변화율
    SAFE_DIVIDE(
        dm.net_revenue - LAG(dm.net_revenue) OVER (ORDER BY dm.dt),
        LAG(dm.net_revenue) OVER (ORDER BY dm.dt)
    ) * 100 AS revenue_change_pct,

    -- 7일 이동평균
    AVG(dm.net_revenue) OVER (
        ORDER BY dm.dt
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS revenue_7d_ma,

    -- 결제 수단별 매출 비중 (서브쿼리)
    (SELECT SAFE_DIVIDE(SUM(CASE WHEN payment_method = 'card' THEN net ELSE 0 END), SUM(net)) * 100
     FROM net_payments np WHERE np.dt = dm.dt) AS card_revenue_pct,

    (SELECT SAFE_DIVIDE(SUM(CASE WHEN payment_method = 'quickpay_balance' THEN net ELSE 0 END), SUM(net)) * 100
     FROM net_payments np WHERE np.dt = dm.dt) AS quickpay_revenue_pct

FROM daily_metrics dm
ORDER BY dm.dt DESC
