-- =====================================================
-- Staging: stg_events
-- Raw 이벤트 로그를 정제하는 첫 번째 레이어
--
-- 역할:
--   1. 컬럼명 표준화 (snake_case)
--   2. 타입 캐스팅 (STRING → TIMESTAMP 등)
--   3. 기본 필터링 (테스트 유저 제외)
--   4. 중복 제거 (event_id 기준)
-- =====================================================

{{
    config(
        materialized='view',
        description='QuickPay 이벤트 로그 Staging 뷰. Raw 데이터에서 중복 제거 및 타입 정규화.'
    )
}}

WITH raw_events AS (
    SELECT
        event_id,
        event_name,
        TIMESTAMP(event_timestamp) AS event_timestamp,
        user_id,
        session_id,
        device_id,
        device_type,
        app_version,
        os_version,
        screen_name,

        -- Taxonomy 파싱: category.action.label
        SPLIT(event_name, '.')[SAFE_OFFSET(0)] AS event_category,
        SPLIT(event_name, '.')[SAFE_OFFSET(1)] AS event_action,
        SPLIT(event_name, '.')[SAFE_OFFSET(2)] AS event_label,

        -- 확장 속성
        properties,

        -- 메타데이터
        _ingested_at,

        -- 중복 제거용
        ROW_NUMBER() OVER (
            PARTITION BY event_id
            ORDER BY _ingested_at ASC
        ) AS _row_num

    FROM {{ source('raw', 'events') }}
    WHERE
        -- 테스트/내부 유저 제외
        user_id NOT LIKE 'test_%'
        AND user_id NOT LIKE 'internal_%'
        -- event_name 형식 검증 (3-depth Taxonomy)
        AND REGEXP_CONTAINS(event_name, r'^[a-z_]+\.[a-z_]+\.[a-z_]+$')
        -- 파티션 프루닝
        AND DATE(event_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL {{ var('lookback_days') }} DAY)
)

SELECT
    * EXCEPT(_row_num)
FROM raw_events
WHERE _row_num = 1   -- event_id 기준 중복 제거
