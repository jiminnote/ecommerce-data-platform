# 📸 Dashboard Screenshots Guide

이 디렉토리에는 포트폴리오에 사용되는 Grafana 스타일 대시보드 스크린샷이 포함됩니다.

## 스크린샷 생성 방법

### 방법 1: HTML 대시보드에서 직접 캡처

```bash
# 브라우저에서 대시보드 HTML 열기
open docs/dashboards/data-platform-dashboard.html
```

1. 브라우저에서 열린 대시보드 전체 페이지를 캡처
2. 아래 4개 영역을 각각 캡처하여 저장:

| 파일명 | 캡처 영역 |
|--------|-----------|
| `dashboard-overview.png` | 전체 대시보드 (Key Metrics ~ Data Quality & Funnel) |
| `dashboard-ai-cost.png` | AI Quality Agent & Pipeline Status ~ Cost Optimization |
| `dashboard-hpa-scaling.png` | HPA Pod Auto-Scaling 패널 |
| `dashboard-cost-optimization.png` | BigQuery Daily Cost Trend 패널 |

### 방법 2: Puppeteer로 자동 캡처 (Node.js 필요)

```bash
npm install puppeteer
node docs/dashboards/capture-screenshots.js
```

### 방법 3: macOS 기본 도구

```bash
# 전체 대시보드 HTML을 Safari에서 열고 캡처
open -a Safari docs/dashboards/data-platform-dashboard.html
# Cmd + Shift + 4로 영역 선택 캡처
```

## 스크린샷 파일 목록

- `dashboard-overview.png` — 전체 대시보드 오버뷰 (Key Metrics + Pipeline Performance + Data Quality)
- `dashboard-ai-cost.png` — AI Quality Agent + Cost Optimization + HPA Scaling
- `dashboard-hpa-scaling.png` — HPA Pod Auto-Scaling 패널 단독
- `dashboard-cost-optimization.png` — BigQuery 비용 최적화 전/후 비교 패널
