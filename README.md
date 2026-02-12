# 🛒 E-commerce Real-time Data Platform

> BigQuery/GCP 기반 이커머스 실시간 데이터 파이프라인 플랫폼  
> Kubernetes 오케스트레이션 + GenAI 기반 데이터 품질 관리

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![GCP](https://img.shields.io/badge/cloud-GCP-4285F4.svg)](https://cloud.google.com)
[![Kubernetes](https://img.shields.io/badge/orchestration-Kubernetes-326CE5.svg)](https://kubernetes.io)
[![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC.svg)](https://terraform.io)

---

## 📋 프로젝트 개요

이커머스 환경에서 **사용자 행동 로그 수집 → 실시간 CDC 적재 → BigQuery 분석 → GenAI 품질 관리**를 수행하는 데이터 플랫폼입니다.

### 핵심 기술 스택

| 영역 | 기술 |
|------|------|
| **Data Warehouse** | Google BigQuery (raw/staging/mart 3-layer) |
| **Stream Processing** | Pub/Sub + Apache Beam (Dataflow) |
| **CDC Pipeline** | Debezium → Kafka → BigQuery |
| **Orchestration** | Apache Airflow (KubernetesExecutor) |
| **Infrastructure** | GKE (Kubernetes) + Terraform IaC |
| **GenAI** | Gemini + LangChain (품질 에이전트, SQL 최적화) |
| **Observability** | Prometheus + Grafana + OpenTelemetry |
| **Language** | Python 3.11+ |

---

## 🔑 주요 구현 내용

### 📊 BigQuery 3-Layer Architecture

#### 데이터 레이어 설계
- **Raw Layer**: CDC 이벤트와 사용자 행동 로그를 append-only로 적재. 일별 파티셔닝.
- **Staging Layer**: 중복 제거, 데이터 타입 정규화, 품질 검증 완료.
- **Mart Layer**: 비즈니스 분석용 사전 집계 테이블 (일별 매출, 전환 퍼널 등).

#### 실시간 CDC 파이프라인
```
PostgreSQL → Debezium → Kafka → Pub/Sub → BigQuery (Raw)
```
- Debezium `pgoutput` 플러그인으로 논리적 복제
- 버퍼링 + 배치 전략으로 BigQuery Streaming Insert 비용 최적화
- Dead Letter Queue로 실패 이벤트 격리

#### 기술 트레이드오프 분석
| 선택 | 대안 | 채택 이유 |
|------|------|-----------|
| BigQuery Streaming Insert | Storage Write API | 낮은 복잡도, 소규모에서 비용 효율적 |
| Pub/Sub | Kafka (직접 연동) | GCP 네이티브 통합, 운영 부담 최소화 |
| Beam/Dataflow | Spark Streaming | GCP 네이티브, 자동 스케일링 |
| Daily CTAS | Incremental MERGE | 구현 단순성, 데이터 정합성 보장 |

---

### ☸️ Kubernetes 클러스터 운영

#### GKE 클러스터 설계
- **Private Cluster**: 노드가 퍼블릭 IP 없이 동작 (보안)
- **Node Pool 분리**: General (항상 실행) + Pipeline (Spot Instance, 비용 절감)
- **Workload Identity**: SA 키 파일 대신 GKE ↔ GCP IAM 네이티브 연동

#### Kubernetes 리소스 설계
- **Event Collector**: Deployment + HPA (CPU/RPS 기반 오토스케일링, 2~10 replicas)
- **CDC Pipeline**: 단일 replica (중복 처리 방지) + PodDisruptionBudget
- **Airflow**: KubernetesExecutor (DAG 태스크별 Pod 생성/삭제)
- **Quality Agent**: CronJob (30분 주기)
- **Monitoring**: ServiceMonitor + PrometheusRule (알림 규칙)

#### 프로덕션 운영 고려사항
- `terminationGracePeriodSeconds: 60` → CDC 파이프라인 버퍼 flush 대기
- `podAntiAffinity` → Event Collector를 다른 노드에 분산 배치
- `PodDisruptionBudget` → 노드 유지보수 시 최소 가용성 보장
- Resource `requests/limits` 설정으로 QoS 보장

---

### 🤖 GenAI 기반 자동화

#### 개발 워크플로우에서의 GenAI 활용
| 도구 | 활용 영역 | 구체적 사례 |
|------|-----------|-------------|
| **GitHub Copilot** | 코드 생성/리팩토링 | Pydantic 모델, BigQuery 스키마, K8s 매니페스트 자동 생성 |
| **Claude** | 설계 리뷰/최적화 | 아키텍처 트레이드오프 분석, SQL 쿼리 최적화 |
| **Gemini** | 런타임 LLM | 데이터 품질 이상 분석, 파이프라인 문서 자동 생성 |

#### 프로덕션 GenAI 에이전트

**1. Data Quality Agent** (`src/genai/data_quality_agent.py`)
- 규칙 기반 품질 체크 (freshness, volume anomaly, null rate, duplicates)
- Gemini LLM으로 이상 징후 자연어 분석 + 조치 방안 제시
- BigQuery `monitoring.data_quality_checks` 테이블에 결과 저장
- Airflow DAG + K8s CronJob으로 30분 주기 자동 실행

**2. SQL Optimizer** (`src/genai/sql_optimizer.py`)
- BigQuery dry-run으로 비용 추정
- Gemini로 파티션 프루닝, 클러스터링 활용, 컬럼 프루닝 등 최적화 제안
- 최적화된 쿼리 + 비용 절감 추정치 자동 생성

**3. Pipeline Doc Generator** (`src/genai/pipeline_doc_generator.py`)
- AST 분석으로 파이프라인 코드 구조 파악
- Gemini로 데이터 리니지, 스키마 설명, SLA 정보, 트러블슈팅 가이드 자동 생성

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Google Cloud SDK (`gcloud`)
- Terraform >= 1.9
- kubectl

### 로컬 개발 환경

```bash
# 1. 프로젝트 클론
git clone https://github.com/jiminnote/ecommerce-data-platform.git
cd ecommerce-data-platform

# 2. Python 환경 설정
pip install -e ".[dev]"

# 3. 환경 변수 설정
cp .env.example .env

# 4. 로컬 인프라 실행
make dev

# 5. 테스트 이벤트 생성
make generate-events

# 6. 테스트 실행
make test
```

### GCP 배포

```bash
# 1. Terraform으로 GCP 인프라 프로비저닝
make tf-init
make tf-apply

# 2. GKE 클러스터 접속
gcloud container clusters get-credentials data-platform-dev \
  --zone asia-northeast3-a --project YOUR_PROJECT_ID

# 3. Kubernetes 리소스 배포
make k8s-deploy

# 4. 상태 확인
make k8s-status
```

---

## 📊 Monitoring & Observability

### 대시보드
- **Grafana**: `http://localhost:3000` (admin/admin)
- **Prometheus**: Event Collector `/metrics`
- **BigQuery**: `monitoring.pipeline_freshness` 뷰

### 알림 규칙
| 알림 | 조건 | 심각도 |
|------|------|--------|
| EventCollectorHighErrorRate | 에러율 > 5% (5분) | Critical |
| PipelineExecutionFailed | 파이프라인 실행 실패 | Warning |
| DataFreshnessSLABreach | 데이터 지연 > 30분 | Critical |
| DataPlatformPodRestarting | Pod 재시작 > 3회/시 | Warning |

---

## 🧪 Testing

```bash
# 전체 테스트
make test

# 특정 모듈
pytest tests/test_event_collector.py -v
pytest tests/test_pipelines.py -v
pytest tests/test_genai.py -v

# 커버리지
pytest --cov=src --cov-report=html
```

