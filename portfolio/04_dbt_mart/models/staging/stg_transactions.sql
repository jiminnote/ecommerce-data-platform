-- =====================================================
-- Staging: stg_transactions
-- 결제/송금 트랜잭션 정제 레이어
--
-- 핀테크 데이터 특수성:
--   - 중복 결제 제거 (동일 transaction_id)
--   - 취소/환불 상태 매핑
--   - 금액 유효성 검증 (amount > 0)
-- =====================================================

{{
    config(
        materialized='view',
        description='QuickPay 트랜잭션 Staging. 중복 결제 제거 및 환불 매핑 포함.'
    )
}}

WITH payment_events AS (
    SELECT
        event_timestamp,
        user_id,
        session_id,
        properties.transaction_id,
        properties.amount,
        properties.payment_method,
        properties.merchant_id,
        properties.merchant_category,
        properties.is_first_payment,
        event_name,
        CASE
            WHEN event_name = 'payment.complete.payment_success' THEN 'COMPLETED'
            WHEN event_name = 'payment.complete.refund' THEN 'REFUNDED'
            WHEN event_name = 'payment.fail.payment_error' THEN 'FAILED'
            ELSE 'UNKNOWN'
        END AS transaction_status,
        ROW_NUMBER() OVER (
            PARTITION BY properties.transaction_id, event_name
            ORDER BY event_timestamp ASC
        ) AS _dedup_rank
    FROM {{ ref('stg_events') }}
    WHERE event_category = 'payment'
      AND properties.transaction_id IS NOT NULL
),

transfer_events AS (
    SELECT
        event_timestamp,
        user_id,
        session_id,
        properties.transfer_id AS transaction_id,
        properties.amount,
        'transfer' AS payment_method,
        NULL AS merchant_id,
        NULL AS merchant_category,
        FALSE AS is_first_payment,
        event_name,
        CASE
            WHEN event_name LIKE '%complete%' THEN 'COMPLETED'
            WHEN event_name LIKE '%fail%' THEN 'FAILED'
            ELSE 'UNKNOWN'
        END AS transaction_status,
        ROW_NUMBER() OVER (
            PARTITION BY properties.transfer_id, event_name
            ORDER BY event_timestamp ASC
        ) AS _dedup_rank
    FROM {{ ref('stg_events') }}
    WHERE event_category = 'transfer'
      AND properties.transfer_id IS NOT NULL
)

SELECT * FROM payment_events  WHERE _dedup_rank = 1 AND amount > 0
UNION ALL
SELECT * FROM transfer_events WHERE _dedup_rank = 1 AND amount > 0
