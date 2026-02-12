-- =====================================================
-- dbt Test: transaction_id 유니크 제약
-- 동일 transaction_id가 2건 이상이면 중복 결제 의심
-- =====================================================

SELECT
    transaction_id,
    COUNT(*) AS cnt
FROM {{ ref('stg_transactions') }}
WHERE transaction_status = 'COMPLETED'
GROUP BY transaction_id
HAVING COUNT(*) > 1
