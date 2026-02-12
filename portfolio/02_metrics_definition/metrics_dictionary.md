# 📊 QuickPay Metrics Dictionary

> **"지표의 정의가 사람마다 다르면, 데이터는 있되 신뢰는 없다."**
> 모든 지표는 아래 정의를 Single Source of Truth로 사용합니다.

---

## 용어 정의 (Glossary)

| 용어 | 정의 | 비고 |
|:-----|:-----|:-----|
| **Active User** | 해당 기간 내 1회 이상 `auth.complete.login` 이벤트를 발생시킨 고유 유저 | 앱 실행만으로는 Active로 간주하지 않음 |
| **Transaction** | `payment.complete.payment_success` 또는 `transfer.complete.*` 이벤트가 발생한 건 | 취소/환불 건 제외 |
| **Paying User** | 해당 기간 내 1건 이상 결제를 완료한 고유 유저 | `payment.complete.payment_success` 기준 |
| **Revenue** | 결제 완료된 거래의 총 금액 합계 | 환불(`payment.complete.refund`) 금액 차감 |
| **First Day** | 유저가 최초로 `auth.complete.login`을 발생시킨 날짜 | 리텐션 코호트 기준일 |

---

## 핵심 지표 정의

### 1. DAU (Daily Active Users)

| 항목 | 정의 |
|:-----|:-----|
| **산출 공식** | `COUNT(DISTINCT user_id) WHERE event_name = 'auth.complete.login' AND DATE(event_timestamp) = target_date` |
| **분자** | 해당 일자에 로그인 완료한 고유 유저 수 |
| **분모** | N/A (절대값) |
| **집계 주기** | Daily |
| **데이터 소스** | `mart.daily_active_users` |
| **주의사항** | `anonymous_*` 유저는 제외. 동일 유저가 여러 디바이스에서 로그인해도 1명으로 카운트. |

### 2. WAU / MAU

| 항목 | WAU | MAU |
|:-----|:----|:----|
| **산출 공식** | `COUNT(DISTINCT user_id)` 최근 7일 | `COUNT(DISTINCT user_id)` 최근 30일 |
| **집계 주기** | Daily (Rolling 7d) | Daily (Rolling 30d) |
| **Stickiness** | DAU / MAU × 100 (목표: 40%+) | |

### 3. ARPPU (Average Revenue Per Paying User)

| 항목 | 정의 |
|:-----|:-----|
| **산출 공식** | `SUM(net_revenue) / COUNT(DISTINCT paying_user_id)` |
| **분자** | 결제 완료 금액 합계 − 환불 금액 합계 (= Net Revenue) |
| **분모** | 해당 기간 내 1건 이상 결제 완료한 고유 유저 수 |
| **집계 주기** | Daily / Monthly |
| **데이터 소스** | `mart.revenue_metrics` |
| **핀테크 주의사항** | 중복 결제(동일 `transaction_id`) 반드시 제거. 취소 상태(`CANCELLED`) 건 제외. |

### 4. Retention Rate (Day N)

| 항목 | 정의 |
|:-----|:-----|
| **산출 공식** | `COUNT(DISTINCT returned_users) / COUNT(DISTINCT cohort_users) × 100` |
| **분자** | 코호트 기준일 + N일 후에 다시 로그인한 유저 수 |
| **분모** | 코호트 기준일에 최초 로그인한 유저 수 |
| **표준 측정** | D1, D3, D7, D14, D30 |
| **데이터 소스** | `mart.user_retention_cohort` |

### 5. Payment Conversion Rate (결제 전환율)

| 항목 | 정의 |
|:-----|:-----|
| **산출 공식** | `COUNT(payment.complete) / COUNT(payment.view.checkout_screen) × 100` |
| **분자** | 결제 완료 이벤트 발생 세션 수 |
| **분모** | 결제 화면 진입 세션 수 |
| **집계 주기** | Daily |
| **데이터 소스** | `mart.payment_funnel` |

### 6. Transfer Success Rate (송금 성공률)

| 항목 | 정의 |
|:-----|:-----|
| **산출 공식** | `COUNT(transfer.complete) / (COUNT(transfer.complete) + COUNT(transfer.fail)) × 100` |
| **분자** | 송금 완료 건수 |
| **분모** | 송금 완료 + 송금 실패 건수 합계 |
| **SLA** | 99.5% 이상 유지 |

### 7. Error Rate (에러 발생률)

| 항목 | 정의 |
|:-----|:-----|
| **산출 공식** | `COUNT(error.occur.*) / COUNT(DISTINCT session_id) × 100` |
| **SLA** | 1% 미만 유지 |
| **알림 기준** | 5분간 에러율 > 3% → Critical Alert |

---

## 지표 간 관계도

```
                    ┌─────────┐
                    │   DAU   │
                    └────┬────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
         ┌────▼────┐ ┌───▼───┐ ┌───▼────┐
         │  WAU    │ │  MAU  │ │Stickiness│
         └─────────┘ └───────┘ └────────┘
              │
     ┌────────┼────────┐
     │        │        │
┌────▼───┐┌───▼───┐┌───▼────┐
│Paying  ││Funnel ││Retention│
│ Users  ││ CVR   ││  Rate  │
└────┬───┘└───────┘└────────┘
     │
┌────▼────┐
│ ARPPU   │
│ Revenue │
└─────────┘
```
