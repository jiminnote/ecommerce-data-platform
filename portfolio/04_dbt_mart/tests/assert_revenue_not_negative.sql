-- =====================================================
-- dbt Test: 매출 금액은 음수일 수 없다
-- 핀테크 데이터 무결성의 핵심 규칙
--
-- 환불 처리 후에도 net_revenue가 음수가 되면
-- 비즈니스 로직에 버그가 있다는 의미
-- =====================================================

-- 이 쿼리가 1행이라도 반환되면 테스트 FAIL
SELECT
    dt,
    net_revenue,
    gross_revenue,
    total_refunds
FROM {{ ref('mart_revenue') }}
WHERE net_revenue < 0
   OR gross_revenue < 0
