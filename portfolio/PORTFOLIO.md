# 핀테크 DataOps: 신뢰할 수 있는 데이터 환경 구축

> **QuickPay** — 가상의 간편결제 서비스를 위한 데이터 운영 포트폴리오
>
> "데이터를 만드는 것이 아니라, **데이터를 신뢰할 수 있게 만드는 것**이 DataOps의 본질입니다."

---

## 📌 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **서비스** | QuickPay — 간편결제 / 송금 / 투자 핀테크 플랫폼 |
| **역할** | Data Engineer (1인) — 로그 설계 ~ 대시보드 운영까지 Full-Cycle |
| **기간** | 2024.06 ~ 현재 |
| **목표** | PM/마케팅/경영진이 "믿고 쓸 수 있는" 데이터 환경 구축 |

### 기술 스택

```
로그 설계     │ Event Taxonomy (Category.Action.Label) + JSON Schema
데이터 수집   │ Event Collector (FastAPI) → Pub/Sub → BigQuery
변환/모델링   │ dbt (staging → intermediate → mart)
품질 관리     │ Great Expectations + Slack Alert (P0/P1/P2)
오케스트레이션│ Apache Airflow (Daily Metrics DAG + Quality DAG)
시각화        │ Tableau / Dashboard (Revenue, Funnel, Retention)
인프라        │ GCP (BigQuery, Pub/Sub, GKE) + Terraform + Docker
```

### 토스 JD 매핑

| 토스 JD 요구사항 | 포트폴리오 대응 |
|-----------------|----------------|
| 로그 설계 및 데이터 거버넌스 | → PART 1: 이벤트 택소노미 & 스키마 설계 |
| 지표 정의 및 데이터 정합성 관리 | → PART 2: 메트릭 딕셔너리 & dbt 모델 |
| 데이터 QA 및 품질 관리 | → PART 3: Great Expectations & Slack 알림 |
| 시각화 및 의사결정 지원 | → PART 4: 대시보드 & 분석 쿼리 |
| 데이터 파이프라인 운영/자동화 | → PART 5: Airflow DAG & 운영 자동화 |

---

## PART 1: 로그 설계 & 데이터 거버넌스

> **"좋은 데이터 분석은 좋은 로그 설계에서 시작됩니다."**

### 1.1 이벤트 택소노미 (Event Taxonomy)

📄 [상세 문서](portfolio/01_log_design/event_taxonomy.md)

#### Why 택소노미가 필요한가?

핀테크 서비스에서 로그 데이터는 단순한 기록이 아니라 **비즈니스 의사결정의 원천**입니다.
택소노미 없이 개발자가 자유롭게 이벤트를 정의하면:

- `paymentComplete`, `payment_done`, `pay_success` — 같은 행동, 다른 이름 3개
- PM이 "결제 전환율" 하나 보려면 DE에게 매번 질의
- 분석 결과의 신뢰도 하락 → 데이터 팀에 대한 불신

#### Category.Action.Label 네이밍 규칙

```
{category}.{action}.{label}

예시:
  payment.view.payment_screen      → 결제 화면 진입
  payment.click.payment_method_select → 결제 수단 선택
  payment.submit.payment_request   → 결제 요청
  payment.complete.payment_success → 결제 완료
  payment.fail.payment_timeout     → 결제 실패 (타임아웃)
```

**8개 카테고리**: auth, payment, transfer, invest, benefit, notification, onboarding, error

#### 결제 퍼널 이벤트 흐름

```
[payment.view.*] → [payment.click.*] → [payment.submit.*] → [payment.complete.*]
     진입              수단 선택           결제 요청            결제 완료/실패
```

### 1.2 이벤트 스키마 (JSON Schema)

📄 [스키마 정의](portfolio/01_log_design/event_schema.json) · 📄 [개발자 가이드](portfolio/01_log_design/log_schema_guide.md)

```json
{
  "event_id": "evt_a1b2c3d4e5",
  "event_name": "payment.complete.payment_success",
  "event_timestamp": "2024-12-15T14:23:45.123Z",
  "user_id": "usr_12345",
  "session_id": "ses_abcde",
  "device_id": "dev_xyz",
  "device_type": "ios",
  "app_version": "3.2.1",
  "properties": {
    "amount": 50000,
    "payment_method": "quickpay_balance",
    "transaction_id": "TXN-A1B2C3D4",
    "merchant_category": "food_delivery"
  }
}
```

**핵심 설계 원칙:**
- `event_name` 정규식 검증: `^[a-z]+\.[a-z]+\.[a-z_]+$`
- 필수 8개 필드 (event_id, event_name, event_timestamp, user_id, session_id, device_id, device_type, app_version)
- `properties` 확장 가능: 결제/송금/에러 등 도메인별 속성 추가
- 버전 관리: Schema v1.2.0 (하위 호환성 유지)

### 1.3 개발자 가이드 & 거버넌스

| 항목 | 내용 |
|------|------|
| **새 이벤트 등록** | PR 리뷰 필수 → taxonomy.md 업데이트 → 스키마 검증 |
| **공통 실수 방지** | `camelCase ❌` → `snake_case ✅`, `timestamp: string ❌` → `ISO 8601 ✅` |
| **코드 예시** | iOS (Swift), Android (Kotlin), Backend (Python) SDK 제공 |

---

## PART 2: 지표 정의 & 데이터 정합성

> **"모두가 같은 숫자를 보고 있다고 확신할 수 있어야 합니다."**

### 2.1 메트릭 딕셔너리

📄 [상세 문서](portfolio/02_metrics_definition/metrics_dictionary.md)

#### Why 메트릭 딕셔너리?

PM이 "DAU가 몇이야?"라고 물었을 때, 사람마다 다른 숫자를 대답하면?

- 마케팅: "앱 설치 후 1회 이상 접속 = 120만"
- 프로덕트: "로그인한 유저 = 98만"
- 경영진: "결제한 유저 = 45만"

→ **하나의 지표 = 하나의 정의 = 하나의 SQL**

#### 핵심 지표 정의

| 지표 | 정의 | 산식 |
|------|------|------|
| **DAU** | 하루 중 로그인 이벤트가 1회 이상인 고유 유저 수 | `COUNT(DISTINCT user_id) WHERE event = 'auth.complete.login'` |
| **ARPPU** | 결제 유저 1인당 평균 순매출 | `SUM(net_revenue) / COUNT(DISTINCT paying_user_id)` |
| **D7 Retention** | 가입 후 7일째 재방문한 유저 비율 | `D7_active_users / cohort_size × 100` |
| **Payment CVR** | 결제 화면 진입 대비 결제 완료 비율 | `complete_sessions / view_sessions × 100` |
| **Error Rate** | 전체 결제 시도 중 실패 비율 | `failed_transactions / total_transactions × 100` |

### 2.2 메트릭 SQL

📄 [DAU/WAU/MAU](portfolio/02_metrics_definition/metrics_sql/dau.sql) · [ARPPU](portfolio/02_metrics_definition/metrics_sql/arppu.sql) · [Retention](portfolio/02_metrics_definition/metrics_sql/retention.sql)

```sql
-- ARPPU 산출: 중복 결제 제거 + 환불 차감
WITH valid_payments AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY transaction_id ORDER BY event_timestamp
    ) AS txn_rank
    FROM staging.events
    WHERE event_name = 'payment.complete.payment_success'
)
SELECT
    dt,
    SAFE_DIVIDE(SUM(net_revenue), COUNT(DISTINCT user_id)) AS arppu
FROM valid_payments
WHERE txn_rank = 1 AND net_revenue > 0  -- 중복 제거 & 환불 후 양수만
GROUP BY dt
```

**핀테크 데이터의 특수성:**
- 🔄 **중복 결제 제거**: `ROW_NUMBER()` by transaction_id
- 💰 **환불 처리**: Gross Revenue - Refund = Net Revenue
- 🚫 **취소 건 제외**: `amount > 0` 필터
- 📊 **SAFE_DIVIDE**: BigQuery에서 0으로 나누기 방지

### 2.3 dbt 모델 (데이터 리니지)

📄 [dbt 프로젝트](portfolio/04_dbt_mart/)

#### 3-Layer 아키텍처

```
Raw (BigQuery)
    │
    ▼
┌─────────────────────────────────────┐
│  Staging (VIEW)                      │
│  stg_events     — 이벤트 정규화      │
│  stg_transactions — 결제/송금 통합    │
└───────────────┬─────────────────────┘
                │
                ▼
┌─────────────────────────────────────┐
│  Intermediate (EPHEMERAL)            │
│  int_user_sessions — 세션 집계       │
└───────────────┬─────────────────────┘
                │
                ▼
┌─────────────────────────────────────┐
│  Mart (TABLE, partitioned)           │
│  mart_revenue        — 매출 분석     │
│  mart_payment_funnel — 퍼널 전환율   │
│  mart_user_retention — 코호트 리텐션  │
└─────────────────────────────────────┘
```

**Why 이 구조?**

| Layer | Materialization | Why |
|-------|----------------|-----|
| **Staging** | VIEW | 원본 데이터에 가까움. 매번 fresh한 데이터 보장. 스토리지 비용 ₩0 |
| **Intermediate** | EPHEMERAL | CTE로 인라인됨. 테이블 생성 불필요한 중간 로직 |
| **Mart** | TABLE | BI 도구에서 직접 조회. 파티셔닝으로 스캔 비용 최적화 |

**dbt 테스트 (3종):**
- `assert_revenue_not_negative` — 순매출 음수 감지
- `assert_arppu_reasonable` — Z-score > 3 이상치 감지
- `assert_unique_transaction_id` — 트랜잭션 중복 감지

---

## PART 3: 데이터 품질 & QA

> **"데이터 품질 문제를 발견하는 것은 사람이 아니라 시스템이어야 합니다."**

### 3.1 Great Expectations

📄 [GE 설정](portfolio/07_data_quality/great_expectations/) · [이벤트 Suite](portfolio/07_data_quality/great_expectations/expectations/quickpay_events_suite.json) · [트랜잭션 Suite](portfolio/07_data_quality/great_expectations/expectations/quickpay_transactions_suite.json)

#### Why Great Expectations?

| 대안 | 장점 | 단점 | 선택 이유 |
|------|------|------|----------|
| **dbt test만** | dbt 내장, 간편 | 복잡한 분포/통계 검증 불가 | - |
| **직접 SQL 검증** | 유연 | 규칙 관리/재사용 어려움 | - |
| **Great Expectations** | 선언적 규칙 + Data Docs + Checkpoint | 학습 곡선 | ✅ 규칙 재사용 + 자동 리포트 |

#### 품질 규칙 체계 (Priority)

| Priority | 기준 | 예시 | 조치 |
|----------|------|------|------|
| **P0** | 분석 불가 수준 | event_id NULL, amount 음수, 택소노미 규칙 위반 | 🚨 즉시 알림 + 파이프라인 중단 |
| **P1** | 분석 왜곡 가능 | device_type 이상값, 평균 금액 범위 이탈 | ⚠️ 알림 + 수동 확인 |
| **P2** | 경미한 이상 | 세션 카디널리티 변동, 볼륨 ±30% | ℹ️ Daily Summary 포함 |

#### 주요 품질 규칙

**이벤트 로그 (10개 규칙):**
```
✓ event_id NOT NULL & UNIQUE          (P0 · completeness/uniqueness)
✓ user_id NOT NULL                    (P0 · completeness)
✓ event_name regex: Category.Action.Label  (P0 · consistency)
✓ device_type IN ('ios','android','web')   (P1 · validity)
✓ amount BETWEEN 0 AND 100,000,000        (P0 · accuracy)
✓ row_count BETWEEN 10K AND 50M           (P1 · volume)
```

**트랜잭션 (8개 규칙):**
```
✓ transaction_id NOT NULL & UNIQUE    (P0 · 중복 결제 감지)
✓ amount > 0                          (P0 · 음수 결제 불가)
✓ status IN ('COMPLETED','REFUNDED','FAILED','PENDING','CANCELLED')  (P0)
✓ AVG(amount) BETWEEN 1,000 AND 500,000  (P1 · 이상치 감지)
```

### 3.2 Slack 알림 시스템

📄 [slack_alert.py](portfolio/07_data_quality/slack_alert.py)

```
┌──────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Great Expectations│────▶│ slack_alert.py│────▶│ Slack Channels   │
│ Checkpoint 실행   │     │ 결과 파싱     │     │ #critical / #warn│
└──────────────────┘     └──────────────┘     └─────────────────┘
                                │
                                ▼
                     P0 → 파이프라인 중단
                     P1 → 수동 확인 요청
                     P2 → Daily Summary
```

**Slack 알림 예시 (P0):**
```
🚨 [P0] 데이터 품질 검증 실패

Suite:        quickpay_events_suite
실행일:       2024-12-15 02:15:00
실패 건수:    2건
조치:         파이프라인 중단

실패 상세:
• user_id — 유저 ID 필수 (이상 비율: 2.0%)
• properties.amount — 결제 금액 음수 불가 (이상 비율: 0.1%)

🔗 Data Docs에서 전체 결과 확인  <!channel>
```

---

## PART 4: 시각화 & 의사결정 지원

> **"좋은 대시보드는 질문에 답하는 것이 아니라, 올바른 질문을 하게 만듭니다."**

### 4.1 QuickPay DataOps Dashboard

📄 [대시보드 HTML](portfolio/06_dashboard/quickpay-dashboard.html)

#### KPI 개요 + 결제 퍼널

![KPI & Funnel](portfolio/06_dashboard/screenshots/01_kpi_funnel.png)

- **5대 핵심 KPI**: DAU(1.24M), Net Revenue(₩4.8B), ARPPU(₩12,400), Payment CVR(68.4%), D7 Retention(42.3%)
- **실시간 결제 퍼널**: View(524K) → Select(418K) → Submit(388K) → Complete(359K)
- 가장 큰 이탈 구간: **결제 화면 → 수단 선택 (20.2% 이탈)** → UX 개선 인사이트

#### 매출 & 사용자 추이

![Revenue & DAU](portfolio/06_dashboard/screenshots/02_revenue_dau.png)

- 일별 Net Revenue + 7일 이동평균 (추세 파악)
- DAU/WAU/MAU 동시 표시 → **Stickiness**(DAU/MAU) 계산 가능
- 주말 DAU 급증 패턴 → 마케팅 타이밍 최적화

#### 리텐션 & 결제 수단

![Retention & Payment](portfolio/06_dashboard/screenshots/03_retention_payment.png)

- 코호트별 D0~D30 리텐션 커브 비교
- D7 42.3% → 전주 대비 +2.5%p 개선 확인
- 결제 수단 비중: QuickPay 잔액(42%) > 신용카드(28%) > 체크카드(15%)

#### 데이터 품질 모니터링

![Quality Monitoring](portfolio/06_dashboard/screenshots/04_quality_monitoring.png)

- 4대 품질 지표: Completeness(99.8%), Uniqueness(100%), Consistency(99.2%), Freshness(<5min)
- 24시간 이벤트 볼륨 + 정상 범위 밴드 → 이상 탐지 시각화

### 4.2 핵심 분석 쿼리

📄 [퍼널 분석](portfolio/05_sql_queries/funnel_analysis.sql) · [리텐션 분석](portfolio/05_sql_queries/retention_analysis.sql) · [매출 분석](portfolio/05_sql_queries/revenue_analysis.sql)

**난이도 최고 쿼리 — 코호트 리텐션 (CTE 4단계):**

```sql
-- CTE 체이닝: user_cohort → daily_activity → cohort_retention → cohort_sizes
WITH user_cohort AS (
    SELECT user_id, MIN(DATE(event_timestamp)) AS cohort_date
    FROM staging.events WHERE event_name = 'auth.complete.login'
    GROUP BY user_id
),
cohort_retention AS (
    SELECT cohort_date, DATE_DIFF(active_date, cohort_date, DAY) AS day_n,
           COUNT(DISTINCT user_id) AS retained_users
    FROM user_cohort JOIN daily_activity USING(user_id)
    GROUP BY 1, 2
)
-- → Pivot: 코호트 × D0~D30 매트릭스 생성
SELECT cohort_date, cohort_size,
    MAX(CASE WHEN day_n = 7 THEN ROUND(SAFE_DIVIDE(retained, size) * 100, 1) END) AS d7
...
```

---

## PART 5: 운영 자동화

> **"반복되는 작업은 자동화하고, 사람은 판단에 집중해야 합니다."**

### 5.1 Airflow DAG 설계

📄 [Daily Metrics DAG](portfolio/08_airflow_dags/daily_metrics_dag.py) · [Quality Check DAG](portfolio/08_airflow_dags/quality_check_dag.py)

#### Daily Metrics Pipeline

```
매일 새벽 02:00 KST
  │
  ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ dbt Staging   │───▶│ dbt Mart     │───▶│ dbt Test     │
│ (stg_*)       │    │ (mart_*)     │    │ (schema test)│
└──────────────┘    └──────────────┘    └──────┬───────┘
                                               │
                                               ▼
                                    ┌──────────────────┐
                                    │ Quality Check     │
                                    │ (Great Expectations)│
                                    └─────────┬────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │ Dashboard Refresh │
                                    │ (Tableau API)     │
                                    └─────────┬────────┘
                                              │
                                    ┌─────────┴────────┐
                                    ▼                  ▼
                              ✅ Success          🚨 Failure
                              (Summary)           (Critical Alert)
```

#### Quality Check Pipeline (6시간마다)

```
06:00, 12:00, 18:00, 00:00 KST
  │
  ├──▶ 이벤트 품질 검증 ──┐
  ├──▶ 트랜잭션 품질 검증 ─┼──▶ 분기 판단 ──▶ Critical / Summary
  └──▶ 볼륨 이상 감지 ────┘
```

**Why 2개 DAG 분리?**
- Daily DAG 실패 시에도 품질 모니터링은 독립 수행
- 품질 검증 주기(6h)와 메트릭 집계 주기(24h) 상이
- 장애 대응 시 영향 범위 격리

### 5.2 운영 패턴

| 패턴 | 구현 |
|------|------|
| **재시도** | `retries=2`, `retry_delay=5min` (Daily), `retries=1` (Quality) |
| **타임아웃** | `execution_timeout=1h` (Daily), `30min` (Quality) |
| **동시 실행 방지** | `max_active_runs=1` |
| **실패 알림** | `TriggerRule.ONE_FAILED` → Slack #data-alert-critical |
| **결과 전파** | XCom으로 품질 결과 → Summary 알림 메시지에 포함 |

---

## 🔧 트러블슈팅 & 실패 경험

> **"실패하지 않은 시스템은 없습니다. 중요한 것은 얼마나 빨리 감지하고 복구하느냐입니다."**

### Case 1: 중복 결제 이벤트로 매출 2배 집계

**상황:** 클라이언트 SDK 버그로 `payment.complete` 이벤트가 2회 발송되어
일 매출이 실제의 약 2배로 집계됨. PM이 보고서를 경영진에 전달한 뒤 발견.

**원인 분석:**
```sql
-- 중복 확인 쿼리
SELECT transaction_id, COUNT(*) AS cnt
FROM staging.events
WHERE event_name = 'payment.complete.payment_success'
GROUP BY 1
HAVING cnt > 1
-- → 약 30%의 결제가 2회 이상 기록
```

**해결:**
1. `stg_transactions.sql`에 `ROW_NUMBER() PARTITION BY transaction_id` 추가
2. Great Expectations에 `expect_column_values_to_be_unique(transaction_id)` 규칙 추가
3. 클라이언트 SDK에 idempotency key 도입 요청

**교훈:** 수집 단계의 중복은 변환 단계에서 반드시 제거해야 하며,
이를 자동 감지하는 품질 규칙이 사전에 존재해야 함.

### Case 2: 택소노미 미준수로 퍼널 분석 누락

**상황:** 신규 기능 배포 시 `paymentView` (camelCase)로 이벤트를 보내,
결제 퍼널의 Step 1이 30% 급감한 것처럼 보임.

**해결:**
1. `event_name` regex 검증을 P0 규칙으로 승격
2. 개발자 가이드에 "공통 실수 목록" 추가
3. CI/CD 파이프라인에 스키마 검증 단계 추가

### Case 3: 환불 미반영으로 ARPPU 과대 산출

**상황:** ARPPU 산출 시 환불 건을 차감하지 않아 실제보다 15% 높게 산출.

**해결:**
1. `mart_revenue.sql`에 refund LEFT JOIN 추가
2. `assert_arppu_reasonable` dbt 테스트로 Z-score 이상치 자동 감지

---

## 🏗️ 로컬 개발 환경

📄 [docker-compose.yml](portfolio/docker-compose.yml)

```bash
# 전체 환경 실행
docker-compose -f portfolio/docker-compose.yml up -d

# 서비스 확인
# Airflow UI:          http://localhost:8080 (admin/admin)
# BigQuery Emulator:   localhost:9050
# PostgreSQL:          localhost:5432
```

```
┌─────────────────────────────────────────────────┐
│                Docker Compose                    │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐ │
│  │PostgreSQL │  │BigQuery  │  │ Airflow       │ │
│  │ (Meta DB) │  │Emulator  │  │ Webserver     │ │
│  └──────────┘  └──────────┘  └───────────────┘ │
│                                                  │
│  ┌──────────┐  ┌──────────────────────────────┐ │
│  │  dbt     │  │ Great Expectations            │ │
│  │ (변환)   │  │ (품질 검증)                    │ │
│  └──────────┘  └──────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## 📁 프로젝트 구조

```
portfolio/
├── PORTFOLIO.md                          ← 이 문서
├── docker-compose.yml                    ← 로컬 개발 환경
│
├── 01_log_design/                        ── PART 1
│   ├── event_taxonomy.md                 · 이벤트 택소노미 설계
│   ├── event_schema.json                 · JSON Schema v1.2.0
│   └── log_schema_guide.md               · 개발자 가이드
│
├── 02_metrics_definition/                ── PART 2
│   ├── metrics_dictionary.md             · 메트릭 딕셔너리
│   └── metrics_sql/
│       ├── dau.sql                       · DAU/WAU/MAU + Stickiness
│       ├── arppu.sql                     · ARPPU (중복제거 + 환불)
│       └── retention.sql                 · 코호트 리텐션 D1~D30
│
├── 04_dbt_mart/                          ── PART 2 (데이터 모델)
│   ├── dbt_project.yml
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_events.sql
│   │   │   └── stg_transactions.sql
│   │   ├── intermediate/
│   │   │   └── int_user_sessions.sql
│   │   └── mart/
│   │       ├── mart_revenue.sql
│   │       ├── mart_payment_funnel.sql
│   │       └── mart_user_retention.sql
│   └── tests/
│       ├── assert_revenue_not_negative.sql
│       ├── assert_arppu_reasonable.sql
│       └── assert_unique_transaction_id.sql
│
├── 05_sql_queries/                       ── PART 4 (분석 쿼리)
│   ├── funnel_analysis.sql               · 결제 퍼널 전환율
│   ├── retention_analysis.sql            · 코호트 리텐션 (CTE 4단계)
│   └── revenue_analysis.sql              · 매출 분석 (Net Revenue)
│
├── 06_dashboard/                         ── PART 4 (시각화)
│   ├── quickpay-dashboard.html           · 인터랙티브 대시보드
│   ├── generate_screenshots.py
│   └── screenshots/
│       ├── 01_kpi_funnel.png
│       ├── 02_revenue_dau.png
│       ├── 03_retention_payment.png
│       └── 04_quality_monitoring.png
│
├── 07_data_quality/                      ── PART 3
│   ├── slack_alert.py                    · Slack 알림 (P0/P1/P2)
│   ├── quality_runner.py                 · GE 실행 러너
│   └── great_expectations/
│       ├── great_expectations.yml
│       └── expectations/
│           ├── quickpay_events_suite.json
│           └── quickpay_transactions_suite.json
│
└── 08_airflow_dags/                      ── PART 5
    ├── daily_metrics_dag.py              · 일별 지표 파이프라인
    └── quality_check_dag.py              · 품질 검증 DAG (6h)
```

---

## 💡 기술 선택의 "Why"

| 기술 | Why 이 기술? | 대안 대비 장점 |
|------|-------------|---------------|
| **dbt** | SQL 기반 변환 → DE 아닌 분석가도 이해 가능 | Spark: 오버엔지니어링 / Stored Proc: 버전관리 불가 |
| **Great Expectations** | 선언적 품질 규칙 + Data Docs 자동 생성 | SQL 검증: 재사용 불가 / dbt test: 통계 검증 한계 |
| **Airflow** | DAG 의존성 관리 + 재시도 + 모니터링 통합 | Cron: 의존성 없음 / Prefect: 생태계 미성숙 |
| **BigQuery** | 서버리스 + 파티셔닝으로 페타바이트 스캔 비용 최적화 | Redshift: 클러스터 관리 필요 / Snowflake: 비용 높음 |
| **JSON Schema** | 클라이언트 SDK에서 사전 검증 가능 | Proto: 모바일 복잡 / Avro: 클라이언트 지원 약함 |
| **Slack Alert** | 평균 확인 시간 5분 (이메일 2시간) | PagerDuty: 소규모 팀에 과한 비용 |

---

## 🎯 이 포트폴리오가 보여주는 것

1. **"데이터를 잘 만드는"** 능력 — 택소노미, 스키마, dbt 모델링
2. **"데이터를 신뢰할 수 있게 만드는"** 능력 — Great Expectations, 품질 규칙, 알림
3. **"데이터로 의사결정을 돕는"** 능력 — 대시보드, 메트릭 딕셔너리, 분석 쿼리
4. **"시스템으로 운영하는"** 능력 — Airflow, 자동화, 장애 대응
5. **"왜(Why)를 설명하는"** 능력 — 모든 기술 선택에 근거 제시

> 📬 궁금한 점이 있으시면 편하게 연락 주세요.
