-- =====================================================
-- Mart: mart_revenue
-- 매출 핵심 지표 테이블
--
-- 핀테크 금융 데이터의 특수성을 반영:
--   1. 중복 결제 제거 (stg_transactions에서 처리)
--   2. 취소/환불 건 Net Revenue 차감
--   3. Transaction Consistency 보장
--
-- Downstream: Tableau 대시보드, 경영진 리포트
-- =====================================================

{{
    config(
        materialized='table',
        partition_by={
            'field': 'dt',
            'data_type': 'date',
            'granularity': 'day'
        },
        cluster_by=['payment_method'],
        description='일별 매출 핵심 지표. ARPPU, Net Revenue, 결제수단별 분포 포함.'
    )
}}

WITH completed AS (
    SELECT
        DATE(event_timestamp) AS dt,
        user_id,
        transaction_id,
        amount AS gross_amount,
        payment_method,
        merchant_category,
        is_first_payment
    FROM {{ ref('stg_transactions') }}
    WHERE transaction_status = 'COMPLETED'
      AND payment_method != 'transfer'  -- 송금은 별도 집계
),

refunded AS (
    SELECT
        transaction_id,
        SUM(amount) AS refund_amount
    FROM {{ ref('stg_transactions') }}
    WHERE transaction_status = 'REFUNDED'
    GROUP BY transaction_id
),

net_transactions AS (
    SELECT
        c.dt,
        c.user_id,
        c.transaction_id,
        c.gross_amount,
        COALESCE(r.refund_amount, 0) AS refund_amount,
        c.gross_amount - COALESCE(r.refund_amount, 0) AS net_amount,
        c.payment_method,
        c.merchant_category,
        c.is_first_payment
    FROM completed c
    LEFT JOIN refunded r ON c.transaction_id = r.transaction_id
    WHERE c.gross_amount - COALESCE(r.refund_amount, 0) > 0
)

SELECT
    dt,

    -- 볼륨 지표
    COUNT(DISTINCT user_id) AS paying_users,
    COUNT(transaction_id) AS total_transactions,

    -- 매출 지표
    SUM(gross_amount) AS gross_revenue,
    SUM(refund_amount) AS total_refunds,
    SUM(net_amount) AS net_revenue,

    -- ★ ARPPU
    SAFE_DIVIDE(SUM(net_amount), COUNT(DISTINCT user_id)) AS arppu,

    -- 평균 거래 금액
    SAFE_DIVIDE(SUM(net_amount), COUNT(transaction_id)) AS avg_txn_amount,

    -- 첫 결제 유저
    COUNT(DISTINCT CASE WHEN is_first_payment THEN user_id END) AS new_paying_users,
    SAFE_DIVIDE(
        COUNT(DISTINCT CASE WHEN is_first_payment THEN user_id END),
        COUNT(DISTINCT user_id)
    ) * 100 AS new_paying_user_pct,

    -- 결제 수단 비중
    SAFE_DIVIDE(COUNTIF(payment_method = 'card'), COUNT(*)) * 100 AS card_pct,
    SAFE_DIVIDE(COUNTIF(payment_method = 'bank_transfer'), COUNT(*)) * 100 AS bank_transfer_pct,
    SAFE_DIVIDE(COUNTIF(payment_method = 'quickpay_balance'), COUNT(*)) * 100 AS quickpay_balance_pct,

    -- 가맹점 업종 Top (JSON)
    TO_JSON_STRING(
        ARRAY_AGG(STRUCT(merchant_category, net_amount) ORDER BY net_amount DESC LIMIT 5)
    ) AS top_merchant_categories

FROM net_transactions
GROUP BY dt
ORDER BY dt DESC
