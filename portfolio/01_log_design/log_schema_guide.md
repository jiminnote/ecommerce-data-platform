# 📖 QuickPay 로그 스키마 가이드 (개발자용)

> **이 문서는 Frontend/Backend 개발자가 이벤트 로그를 올바르게 구현하기 위한 가이드입니다.**

---

## 🚨 반드시 읽어주세요

1. **모든 이벤트는 `event_schema.json`을 준수해야 합니다.**
2. **필수 필드 누락 시 데이터 파이프라인에서 자동 reject됩니다.**
3. **새로운 이벤트 추가 시 반드시 DataOps 팀에 리뷰를 요청하세요.**

---

## ✅ 올바른 구현 예시

### iOS (Swift)

```swift
// ✅ 올바른 결제 완료 이벤트
QuickPayAnalytics.track(
    event: "payment.complete.payment_success",
    properties: [
        "transaction_id": "txn_abc123",
        "amount": 15000,
        "payment_method": "card",
        "merchant_id": "merchant_456",
        "is_first_payment": false
    ]
)

// ❌ 잘못된 예시 — 이벤트명 규칙 위반
QuickPayAnalytics.track(event: "결제완료")           // 한글 불가
QuickPayAnalytics.track(event: "paymentComplete")     // camelCase 불가
QuickPayAnalytics.track(event: "payment_complete")    // 3-depth 아님
```

### Android (Kotlin)

```kotlin
// ✅ 올바른 송금 완료 이벤트
QuickPayAnalytics.track(
    event = "transfer.complete.to_account",
    properties = mapOf(
        "transfer_id" to "tfr_xyz789",
        "amount" to 50000,
        "from_account_type" to "quickpay_balance",
        "to_account_type" to "bank_account"
    )
)
```

### Backend (Python)

```python
# ✅ 서버사이드 이벤트 (결제 실패 — 클라이언트에서 감지 불가한 경우)
from quickpay.analytics import track_event

track_event(
    event_name="payment.fail.server_error",
    user_id=user.id,
    properties={
        "transaction_id": txn.id,
        "amount": txn.amount,
        "error_code": "PG_TIMEOUT",
        "error_message": "PG사 응답 타임아웃 (30s)",
    }
)
```

---

## ⚠️ 흔한 실수 & 해결법

| 실수 | 문제 | 해결 |
|:-----|:-----|:-----|
| `event_timestamp` 누락 | 시간 기반 분석 불가 | SDK가 자동 주입하도록 설정 |
| `user_id = null` | 유저별 지표 산출 불가 | 비로그인 시 `anonymous_{device_id}` 사용 |
| `amount = -5000` | 금액 유효성 위반 | 환불은 별도 이벤트(`payment.complete.refund`)로 분리 |
| 같은 이벤트를 2번 전송 | 중복 집계 | `event_id` (UUID)로 dedup 처리 |
| `event_name = "PaymentSuccess"` | Taxonomy 규칙 위반 | `payment.complete.payment_success` 형식 준수 |

---

## 🔍 이벤트 검증 체크리스트

```
□ event_name이 category.action.label 형식인가?
□ 필수 필드(event_id, event_timestamp, user_id 등) 8개가 모두 포함되었는가?
□ event_id가 UUID v4 형식인가?
□ event_timestamp가 UTC ISO 8601 형식인가?
□ amount 필드가 음수가 아닌가?
□ device_type이 ios/android/web 중 하나인가?
□ 기존 Taxonomy에 없는 새 이벤트라면 DataOps 리뷰를 받았는가?
```

---

## 📬 새 이벤트 추가 요청 프로세스

```
1. Slack #data-log-request 채널에 요청
   → 이벤트명, 속성 목록, 비즈니스 목적 기재

2. DataOps 리뷰 (1 영업일 내)
   → Taxonomy 적합성, 기존 이벤트 중복 여부 확인

3. event_schema.json 업데이트 & PR 머지

4. 클라이언트 구현 & QA

5. 데이터 수신 확인 (파이프라인 모니터링)
```
