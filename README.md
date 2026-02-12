# 🛒 E-commerce Real-time Data Platform

> BigQuery/GCP 기반 이커머스 실시간 데이터 파이프라인 플랫폼
> Kubernetes 오케스트레이션 + GenAI 기반 데이터 품질 관리

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![GCP](https://img.shields.io/badge/cloud-GCP-4285F4.svg)](https://cloud.google.com)
[![Kubernetes](https://img.shields.io/badge/orchestration-Kubernetes-326CE5.svg)](https://kubernetes.io)
[![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC.svg)](https://terraform.io)

---

## 📋 프로젝트 개요

컬리와 유사한 이커머스 환경에서 **사용자 행동 로그 수집 → 실시간 CDC 적재 → BigQuery 분석 → GenAI 품질 관리**를 수행하는 풀스택 데이터 플랫폼입니다.

### 핵심 기술 스택

| 영역 | 기술 |
|------|------|
| **Data Warehouse** | Google BigQuery (raw/staging/mart 3-layer) |
| **Stream Processing** | Pub/Sub + Apache Beam (Dataflow) |
| **CDC Pipeline** | Debezium → Kafka → BigQuery |
| **Orchestration** | Apache Airflow (KubernetesExecutor) |
| **Infrastructure** | GKE (Kubernetes) + Terraform IaC |
| **GenAI/AX** | Gemini + LangChain (품질 에이전트, SQL 최적화) |
| **Observability** | Prometheus + Grafana + OpenTelemetry |
| **Language** | Python 3.11+ |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Data Sources                                  │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │
│  │PostgreSQL │  │ Mobile/Web   │  │  External APIs               │   │
│  │(Source DB)│  │ Clients      │  │  (Analytics Solutions)       │   │
│  └────┬─────┘  └──────┬───────┘  └──────────────────────────────┘   │
│       │               │                                              │
│  ┌────▼─────┐  ┌──────▼───────┐                                     │
│  │ Debezium │  │Event Collector│  ◄── FastAPI + Kubernetes HPA      │
│  │   CDC    │  │  (FastAPI)   │                                     │
│  └────┬─────┘  └──────┬───────┘                                     │
│       │               │                                              │
│  ┌────▼───────────────▼────┐                                        │
│  │    Google Cloud Pub/Sub  │  ◄── Message Queue                    │
│  └────┬───────────────┬────┘                                        │
│       │               │                                              │
│  ┌────▼─────┐  ┌──────▼───────┐                                     │
│  │CDC Pipeline│ │ Beam/Dataflow│  ◄── Stream Processing             │
│  └────┬─────┘  └──────┬───────┘                                     │
│       │               │                                              │
│  ┌────▼───────────────▼────┐                                        │
│  │      BigQuery (Raw)      │  ◄── Append-only, Partitioned        │
│  └────────────┬────────────┘                                        │
│               │                                                      │
│  ┌────────────▼────────────┐                                        │
│  │    BigQuery (Staging)    │  ◄── Deduplicated, Validated          │
│  └────────────┬────────────┘      (Airflow Daily Batch)             │
│               │                                                      │
│  ┌────────────▼────────────┐                                        │
│  │     BigQuery (Mart)      │  ◄── Business-ready Aggregations     │
│  └─────────────────────────┘                                        │
│                                                                      │
│  ┌─────────────────────────┐  ┌────────────────────────────┐        │
│  │   GenAI Quality Agent   │  │  Prometheus + Grafana      │        │
│  │  (Gemini + LangChain)   │  │  (Observability)           │        │
│  └─────────────────────────┘  └────────────────────────────┘        │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │              GKE (Kubernetes Cluster)                     │       │
│  │  Managed by Terraform IaC                                 │       │
│  └──────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 📁 프로젝트 구조

```
ecommerce-data-platform/
├── src/
│   ├── event_collector/          # 사용자 행동 로그 수집 API
│   │   ├── app.py                #   FastAPI 앱 (Prometheus 메트릭 내장)
│   │   ├── models.py             #   이벤트 스키마 (Pydantic)
│   │   └── publisher.py          #   Pub/Sub 퍼블리셔
│   │
│   ├── pipelines/                # 데이터 파이프라인
│   │   ├── cdc_realtime.py       #   실시간 CDC 파이프라인 (Debezium → BQ)
│   │   ├── batch_pipeline.py     #   일일 배치 ETL (Raw → Staging → Mart)
│   │   └── event_pipeline.py     #   Apache Beam 이벤트 처리 (Dataflow)
│   │
│   ├── bigquery/                 # BigQuery 관리
│   │   ├── schema_manager.py     #   스키마 생성/마이그레이션
│   │   └── queries/              #   분석 SQL 쿼리
│   │       ├── user_behavior.sql #     사용자 행동 분석
│   │       ├── product_analytics.sql   상품 성과 분석
│   │       └── funnel_analysis.sql     전환 퍼널 분석
│   │
│   ├── genai/                    # GenAI/AX 모듈
│   │   ├── data_quality_agent.py #   AI 데이터 품질 에이전트
│   │   ├── sql_optimizer.py      #   AI SQL 최적화
│   │   └── pipeline_doc_generator.py  AI 문서 자동 생성
│   │
│   ├── observability/            # 모니터링
│   │   └── metrics.py            #   Prometheus 커스텀 메트릭
│   │
│   └── scripts/
│       └── event_generator.py    # 테스트 이벤트 생성기
│
├── dags/                         # Airflow DAGs
│   ├── daily_batch_etl.py        #   일일 배치 ETL DAG
│   └── data_quality_check.py     #   품질 체크 DAG (30분 주기)
│
├── kubernetes/                   # K8s 매니페스트
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml
│   ├── event-collector/          #   Event Collector Deployment + HPA
│   ├── cdc-pipeline/             #   CDC Pipeline Deployment
│   ├── airflow/                  #   Airflow Helm values
│   └── monitoring/               #   Prometheus + Grafana + CronJob
│
├── terraform/                    # GCP Infrastructure as Code
│   ├── main.tf                   #   Provider, APIs
│   ├── bigquery.tf               #   BigQuery datasets/tables
│   ├── pubsub.tf                 #   Pub/Sub topics/subscriptions
│   ├── gke.tf                    #   GKE cluster + node pools + VPC
│   ├── iam.tf                    #   Service accounts + Workload Identity
│   ├── variables.tf
│   └── outputs.tf
│
├── tests/                        # 테스트
├── scripts/                      # DB 초기화, Debezium 설정
├── docker-compose.yml            # 로컬 개발 환경
├── Dockerfile                    # 멀티스테이지 빌드
├── Makefile                      # 개발 편의 커맨드
└── pyproject.toml                # Python 프로젝트 설정
```

---

## 🔑 주요 구현 상세

### 1. BigQuery 기반 데이터 파이프라인 (GAP: BigQuery/GCP 경험)

#### 3-Layer 데이터 아키텍처
- **Raw Layer**: CDC 이벤트와 사용자 행동 로그를 append-only로 적재. 일별 파티셔닝.
- **Staging Layer**: 중복 제거, 데이터 타입 정규화, 품질 검증 완료된 데이터.
- **Mart Layer**: 비즈니스 분석용 사전 집계 테이블 (일별 매출, 전환 퍼널 등).

#### 실시간 CDC 파이프라인
```
PostgreSQL → Debezium → Kafka → CDC Pipeline → Pub/Sub → BigQuery (Raw)
```
- Debezium의 `pgoutput` 플러그인으로 논리적 복제
- 버퍼링 + 배치 전략으로 BigQuery Streaming Insert 비용 최적화
- Dead Letter Queue로 실패 이벤트 격리

#### 기술 트레이드오프 분석
| 선택 | 대안 | 채택 이유 |
|------|------|-----------|
| BigQuery Streaming Insert | Storage Write API | 낮은 복잡도, 소규모에서 비용 효율적 |
| Pub/Sub | Kafka (직접 연동) | GCP 네이티브 통합, 운영 부담 최소화 |
| Beam/Dataflow | Spark Streaming | GCP 네이티브, 자동 스케일링 |
| Daily CTAS | Incremental MERGE | 구현 단순성, 데이터 정합성 보장 |

### 2. Kubernetes 클러스터 운영 (GAP: Kubernetes 미경험)

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

### 3. GenAI 도구 활용 (GAP: GenAI 도구 활용 미명시)

#### 개발 워크플로우에서의 GenAI 활용
| 도구 | 활용 영역 | 구체적 사례 |
|------|-----------|-------------|
| **GitHub Copilot** | 코드 생성/리팩토링 | Pydantic 모델, BigQuery 스키마, K8s 매니페스트 자동 생성 |
| **Claude** | 설계 리뷰/프롬프트 엔지니어링 | 아키텍처 트레이드오프 분석, SQL 쿼리 최적화 |
| **Gemini** | 런타임 LLM | 데이터 품질 이상 분석, 파이프라인 문서 자동 생성 |

#### 프로덕션 GenAI 에이전트

**1. Data Quality Agent** (`src/genai/data_quality_agent.py`)
- 규칙 기반 품질 체크 (freshness, volume anomaly, null rate, duplicates)
- Gemini LLM으로 이상 징후 자연어 분석 + 조치 방안 제시
- BigQuery `monitoring.data_quality_checks` 테이블에 결과 이력 저장
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

### 로컬 개발 환경 설정

```bash
# 1. 프로젝트 클론
git clone https://github.com/your-org/ecommerce-data-platform.git
cd ecommerce-data-platform

# 2. Python 환경 설정
pip install -e ".[dev]"

# 3. 환경 변수 설정
cp .env.example .env
# .env 파일에서 GCP_PROJECT_ID 등 수정

# 4. 로컬 인프라 실행 (PostgreSQL + BigQuery Emulator + Grafana)
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
make tf-plan
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

## 📊 Observability

### 모니터링 대시보드
- **Grafana**: `http://localhost:3000` (admin/admin)
- **Prometheus**: Event Collector `/metrics` 엔드포인트
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

# 특정 모듈 테스트
pytest tests/test_event_collector.py -v
pytest tests/test_pipelines.py -v
pytest tests/test_genai.py -v

# 커버리지 리포트
pytest --cov=src --cov-report=html
```

---

## 🛠️ 기술 의사결정 기록

### Why BigQuery?
- 컬리의 핵심 데이터 웨어하우스 기술 스택
- 서버리스 → 인프라 운영 부담 최소화
- 파티셔닝/클러스터링으로 비용 최적화 가능
- BI Engine으로 서브초 쿼리 가능

### Why GKE (Kubernetes)?
- 마이크로서비스 아키텍처 → 파이프라인 컴포넌트 독립 배포/스케일링
- HPA로 트래픽 기반 자동 스케일링 (이벤트 수집기)
- Spot Instance로 배치 파이프라인 비용 절감
- Helm + ArgoCD로 GitOps 배포 가능

### Why GenAI Agent?
- 반복적 데이터 품질 체크 자동화 → 인적 비용 절감
- 이상 징후의 자연어 분석 → 비기술 이해관계자 커뮤니케이션 개선
- SQL 최적화 → BigQuery 비용 절감 (실질적 ROI)
- 파이프라인 문서 자동 유지 → 온보딩 시간 단축

---

## 📝 License

MIT License
