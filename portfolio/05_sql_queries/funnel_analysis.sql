-- =====================================================
-- 결제 퍼널 전환율 분석 (세션 기반)
-- 난이도: ★★★☆☆
--
-- 결제 프로세스의 각 단계별 이탈 지점을 파악하여
-- UX 개선 및 매출 증대 인사이트 도출
-- =====================================================

WITH session_funnel AS (
    SELECT
        DATE(MIN(e.event_timestamp)) AS dt,
        e.session_id,
        e.user_id,
        e.device_type,

        -- 퍼널 스텝 통과 여부
        MAX(CASE WHEN e.event_name LIKE 'payment.view.%' THEN 1 ELSE 0 END) AS step1_view,
        MAX(CASE WHEN e.event_name = 'payment.click.payment_method_select' THEN 1 ELSE 0 END) AS step2_select,
        MAX(CASE WHEN e.event_name = 'payment.submit.payment_request' THEN 1 ELSE 0 END) AS step3_submit,
        MAX(CASE WHEN e.event_name = 'payment.complete.payment_success' THEN 1 ELSE 0 END) AS step4_complete,
        MAX(CASE WHEN e.event_name LIKE 'payment.fail.%' THEN 1 ELSE 0 END) AS has_error,

        -- 세션 내 체류 시간
        TIMESTAMP_DIFF(MAX(e.event_timestamp), MIN(e.event_timestamp), SECOND) AS session_duration_sec,

        -- 결제 금액 (완료 시)
        MAX(e.properties.amount) AS payment_amount

    FROM staging.events e
    WHERE e.event_category = 'payment'
      AND DATE(e.event_timestamp) BETWEEN
          DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY) AND CURRENT_DATE() - 1
    GROUP BY e.session_id, e.user_id, e.device_type
)

SELECT
    dt,
    device_type,

    -- 퍼널 절대 수치
    COUNTIF(step1_view = 1) AS funnel_view,
    COUNTIF(step2_select = 1) AS funnel_select,
    COUNTIF(step3_submit = 1) AS funnel_submit,
    COUNTIF(step4_complete = 1) AS funnel_complete,

    -- 단계별 전환율
    SAFE_DIVIDE(COUNTIF(step2_select = 1), COUNTIF(step1_view = 1)) * 100
        AS cvr_1to2_pct,
    SAFE_DIVIDE(COUNTIF(step3_submit = 1), COUNTIF(step2_select = 1)) * 100
        AS cvr_2to3_pct,
    SAFE_DIVIDE(COUNTIF(step4_complete = 1), COUNTIF(step3_submit = 1)) * 100
        AS cvr_3to4_pct,

    -- ★ 전체 전환율
    SAFE_DIVIDE(COUNTIF(step4_complete = 1), COUNTIF(step1_view = 1)) * 100
        AS overall_cvr_pct,

    -- 이탈 구간 파악: 가장 큰 이탈이 발생하는 단계
    GREATEST(
        COUNTIF(step1_view = 1) - COUNTIF(step2_select = 1),
        COUNTIF(step2_select = 1) - COUNTIF(step3_submit = 1),
        COUNTIF(step3_submit = 1) - COUNTIF(step4_complete = 1)
    ) AS max_dropoff_count,

    -- 평균 결제 완료 시간
    AVG(CASE WHEN step4_complete = 1 THEN session_duration_sec END) AS avg_completion_time_sec,

    -- 에러 발생 세션 비율
    SAFE_DIVIDE(COUNTIF(has_error = 1), COUNT(*)) * 100 AS error_session_pct

FROM session_funnel
GROUP BY dt, device_type
ORDER BY dt DESC, device_type
