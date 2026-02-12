-- =====================================================
-- Intermediate: int_user_sessions
-- 유저 세션 단위 집계 (Ephemeral)
--
-- 퍼널 분석, 세션 지표의 기반 데이터
-- materialized: ephemeral → 다른 모델에서 참조 시 인라인 실행
-- =====================================================

{{
    config(
        materialized='ephemeral',
        description='유저 세션 단위 집계. 퍼널 분석의 기반 데이터.'
    )
}}

SELECT
    session_id,
    user_id,
    device_type,
    MIN(event_timestamp) AS session_start,
    MAX(event_timestamp) AS session_end,
    TIMESTAMP_DIFF(MAX(event_timestamp), MIN(event_timestamp), SECOND) AS session_duration_sec,
    COUNT(*) AS total_events,

    -- 퍼널 스텝 통과 여부
    MAX(CASE WHEN event_name = 'auth.complete.login' THEN 1 ELSE 0 END) AS has_login,
    MAX(CASE WHEN event_category = 'payment' AND event_action = 'view' THEN 1 ELSE 0 END) AS has_payment_view,
    MAX(CASE WHEN event_name = 'payment.click.payment_method_select' THEN 1 ELSE 0 END) AS has_method_select,
    MAX(CASE WHEN event_name = 'payment.submit.payment_request' THEN 1 ELSE 0 END) AS has_payment_submit,
    MAX(CASE WHEN event_name = 'payment.complete.payment_success' THEN 1 ELSE 0 END) AS has_payment_complete,
    MAX(CASE WHEN event_name LIKE 'payment.fail.%' THEN 1 ELSE 0 END) AS has_payment_fail,

    -- 송금 퍼널
    MAX(CASE WHEN event_category = 'transfer' AND event_action = 'view' THEN 1 ELSE 0 END) AS has_transfer_view,
    MAX(CASE WHEN event_name = 'transfer.complete.to_account' THEN 1 ELSE 0 END) AS has_transfer_complete,

    -- 에러 발생 여부
    MAX(CASE WHEN event_category = 'error' THEN 1 ELSE 0 END) AS has_error

FROM {{ ref('stg_events') }}
GROUP BY session_id, user_id, device_type
