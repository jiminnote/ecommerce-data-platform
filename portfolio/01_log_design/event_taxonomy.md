# 📐 QuickPay Event Taxonomy

> **"개발자가 구현하기 쉽고, 분석가가 사용하기 편한 로그 구조를 고민했습니다."**

---

## 1. Taxonomy 설계 원칙

### 1.1 Naming Convention: `Category.Action.Label`

모든 이벤트는 3-depth 계층으로 명명합니다.

```
{category}.{action}.{label}

예시:
  payment.click.confirm_button
  transfer.complete.to_account
  auth.view.login_screen
  invest.scroll.fund_list
```

| Depth | 정의 | 규칙 | 예시 |
|:------|:-----|:-----|:-----|
| **Category** | 서비스 도메인 | snake_case, 명사 | `payment`, `transfer`, `auth`, `invest` |
| **Action** | 사용자 행위 | snake_case, 동사 | `view`, `click`, `submit`, `complete`, `scroll` |
| **Label** | 대상 요소 | snake_case, 구체적 | `confirm_button`, `amount_input`, `login_screen` |

### 1.2 왜 이 구조인가?

```
❌ 무체계 로그:  "btn_click", "page1_view", "결제완료"
   → 분석 시 LIKE '%click%' 남발, 지표 산출 불가능

✅ Taxonomy 로그: "payment.click.confirm_button"
   → WHERE category = 'payment' AND action = 'complete' 로 정확한 필터링
   → GROUP BY category 로 서비스 도메인별 집계 즉시 가능
```

---

## 2. 이벤트 카테고리 정의

### QuickPay 핵심 서비스 도메인

| Category | 설명 | 주요 이벤트 | 핵심 지표 연결 |
|:---------|:-----|:-----------|:-------------|
| `auth` | 인증/로그인 | view, submit, complete, fail | 로그인 성공률, 이탈률 |
| `payment` | 결제 | view, click, submit, complete, fail | 결제 전환율, ARPPU |
| `transfer` | 송금 | view, input, confirm, complete, fail | 송금 완료율, 평균 송금액 |
| `invest` | 투자 | view, scroll, click, subscribe, redeem | 투자 전환율 |
| `benefit` | 혜택/포인트 | view, click, use, earn | 포인트 사용률 |
| `notification` | 알림 | receive, view, click, dismiss | 알림 클릭률 (CTR) |
| `onboarding` | 온보딩 | view, skip, complete | 온보딩 완료율 |
| `error` | 에러/장애 | occur, retry, resolve | 에러 발생률 |

### 이벤트 흐름 예시: 결제 퍼널

```
auth.view.login_screen
  → auth.submit.login_form
  → auth.complete.login
  → payment.view.checkout_screen
  → payment.click.payment_method_select
  → payment.submit.payment_request
  → payment.complete.payment_success   ← 핵심 전환 이벤트
     OR
  → payment.fail.payment_error         ← 에러 추적 이벤트
```

---

## 3. 공통 속성 (Common Properties)

모든 이벤트에 반드시 포함되어야 하는 필드:

| 필드 | 타입 | 필수 | 설명 | Null 정책 |
|:-----|:-----|:-----|:-----|:---------|
| `event_id` | STRING | ✅ | UUID v4 | **절대 Null 불가** |
| `event_name` | STRING | ✅ | `category.action.label` | **절대 Null 불가** |
| `event_timestamp` | TIMESTAMP | ✅ | ISO 8601 (UTC) | **절대 Null 불가** |
| `user_id` | STRING | ✅ | 유저 고유 ID | 비로그인 시 `anonymous_{device_id}` |
| `session_id` | STRING | ✅ | 세션 ID | 앱 포그라운드 기준 갱신 |
| `device_id` | STRING | ✅ | 디바이스 고유 ID | **절대 Null 불가** |
| `device_type` | STRING | ✅ | `ios` / `android` / `web` | **절대 Null 불가** |
| `app_version` | STRING | ✅ | 시맨틱 버전 `3.2.1` | **절대 Null 불가** |
| `os_version` | STRING | ⬚ | `iOS 17.2`, `Android 14` | Null 허용 |
| `screen_name` | STRING | ⬚ | 현재 화면명 | Null 허용 |

---

## 4. 도메인별 확장 속성 (Domain-Specific Properties)

### Payment 이벤트 확장 필드

| 필드 | 타입 | 설명 |
|:-----|:-----|:-----|
| `transaction_id` | STRING | 결제 트랜잭션 ID |
| `amount` | INTEGER | 결제 금액 (원 단위) |
| `payment_method` | STRING | `card`, `bank_transfer`, `quickpay_balance` |
| `merchant_id` | STRING | 가맹점 ID |
| `merchant_category` | STRING | 가맹점 업종 코드 |
| `is_first_payment` | BOOLEAN | 첫 결제 여부 |

### Transfer 이벤트 확장 필드

| 필드 | 타입 | 설명 |
|:-----|:-----|:-----|
| `transfer_id` | STRING | 송금 트랜잭션 ID |
| `amount` | INTEGER | 송금 금액 |
| `from_account_type` | STRING | 출금 계좌 종류 |
| `to_account_type` | STRING | 입금 계좌 종류 |
| `is_scheduled` | BOOLEAN | 예약 송금 여부 |

---

## 5. 로그 버전 관리

```
v1.0.0 (2026-01-01) — 초기 Taxonomy 수립
v1.1.0 (2026-01-15) — invest 카테고리 추가
v1.2.0 (2026-02-01) — error 카테고리 추가, Null 정책 강화
```

> 스키마 변경 시 반드시 `event_schema.json`의 버전을 갱신하고,
> 하위 호환성(Backward Compatibility)을 유지합니다.
