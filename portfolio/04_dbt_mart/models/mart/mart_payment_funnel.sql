-- =====================================================
-- Mart: mart_payment_funnel
-- 결제 전환 퍼널 분석 테이블
--
-- 퍼널 스텝:
--   1. 결제 화면 진입 (payment.view)
--   2. 결제 수단 선택 (payment.click.payment_method_select)
--   3. 결제 요청 (payment.submit.payment_request)
--   4. 결제 완료 (payment.complete.payment_success)
--      OR 결제 실패 (payment.fail.*)
--
-- Downstream: Tableau 퍼널 차트
-- =====================================================

{{
    config(
        materialized='table',
        partition_by={'field': 'dt', 'data_type': 'date'},
        description='일별 결제 전환 퍼널. 디바이스별 전환율 포함.'
    )
}}

WITH sessions AS (
    SELECT * FROM {{ ref('int_user_sessions') }}
)

SELECT
    DATE(session_start) AS dt,
    device_type,

    -- 절대 수치
    COUNT(DISTINCT session_id) AS total_sessions,
    COUNTIF(has_payment_view = 1) AS step1_payment_view,
    COUNTIF(has_method_select = 1) AS step2_method_select,
    COUNTIF(has_payment_submit = 1) AS step3_payment_submit,
    COUNTIF(has_payment_complete = 1) AS step4_payment_complete,
    COUNTIF(has_payment_fail = 1) AS payment_fail_sessions,

    -- 단계별 전환율
    SAFE_DIVIDE(COUNTIF(has_method_select = 1), COUNTIF(has_payment_view = 1)) * 100
        AS cvr_view_to_select,
    SAFE_DIVIDE(COUNTIF(has_payment_submit = 1), COUNTIF(has_method_select = 1)) * 100
        AS cvr_select_to_submit,
    SAFE_DIVIDE(COUNTIF(has_payment_complete = 1), COUNTIF(has_payment_submit = 1)) * 100
        AS cvr_submit_to_complete,

    -- ★ 전체 전환율 (결제 화면 → 결제 완료)
    SAFE_DIVIDE(COUNTIF(has_payment_complete = 1), COUNTIF(has_payment_view = 1)) * 100
        AS overall_payment_cvr,

    -- 결제 실패율
    SAFE_DIVIDE(
        COUNTIF(has_payment_fail = 1),
        COUNTIF(has_payment_submit = 1)
    ) * 100 AS payment_failure_rate

FROM sessions
WHERE has_payment_view = 1   -- 결제 화면 진입 세션만
GROUP BY dt, device_type
ORDER BY dt DESC, device_type
