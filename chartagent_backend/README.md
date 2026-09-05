# ChartAgent backend

FaceMaxx와 같은 EC2에서 실행하되, 애플리케이션 코드·컨테이너·포트·환경 변수는 분리한 FastAPI 서비스입니다.

## 요청 흐름

1. 이미지 바이트/해상도/형식 검증
2. InsightSentry `/v3/symbols/{symbol}/info`로 심볼 실재 검증
3. 뉴스 옵션을 켠 경우 `/v3/newsfeed?related_symbols=...` 조회
4. Codex CLI로 `gpt-5.6-luna`, reasoning `low`, strict JSON schema 분석
5. Codex 실행·인증·타임아웃·스키마 오류 시 OpenAI Responses API(`gpt-5-mini`)와 같은 스키마로 폴백

OpenAI 및 InsightSentry 키는 앱에 포함하지 않고 서버 환경 변수로만 주입합니다. InsightSentry는 `INSIGHTSENTRY_RAPIDAPI_KEY` / `INSIGHTSENTRY_RAPIDAPI_HOST` 방식을 우선 사용하고, 기존 Bearer API 키도 호환합니다. Codex 프로세스에는 두 API 키가 전달되지 않습니다.

Codex CLI 모델은 요구사항대로 `gpt-5.6-luna`/`low`로 고정하며, OpenAI API 폴백 모델은 `CHARTAGENT_OPENAI_MODEL`로 독립 설정합니다.

## 로컬 실행

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

## FaceMaxx 저장소에서 배포

- SSH 접속 후 FaceMaxx와 분리된 `/opt/chartagent/.env`를 생성합니다. `/opt/facemaxx/.env`를 ChartAgent 용도로 수정하지 않습니다.
- 이 디렉터리는 FaceMaxx 저장소의 독립 Docker build context입니다. FaceMaxx 애플리케이션 코드와 런타임은 섞지 않습니다.
- FaceMaxx compose는 `/opt/facemaxx`에서 실행되며 두 서비스 모두 같은 `codex-home` volume을 `/home/app/.codex`에 마운트합니다.
- FaceMaxx와 ChartAgent 이미지는 각각 `/usr/local/bin/codex`를 포함합니다. 공유하는 것은 `/home/app/.codex`에 마운트되는 인증 volume만입니다.
- 루트의 `deploy/ec2/docker-compose.yml`은 ChartAgent를 localhost `8010`에만 노출합니다.
- 배포 워크플로가 기존 TLS 서버 블록에 `/chartagent/` location을 멱등하게 설치하고 Nginx 검증·리로드까지 수행합니다.
- 외부 API base URL은 `https://facemaxx.nostalgia-drive.com/chartagent/v1`입니다.

배포 후 `GET /chartagent/health`에서 모델, reasoning, 두 외부 서비스의 구성 여부만 확인합니다. 토큰 값은 응답하지 않습니다.

## GitHub Actions 자동 배포

루트의 `.github/workflows/deploy-backend.yml`은 `main` 브랜치의 `chartagent_backend/**` 변경 시 FaceMaxx와 ChartAgent 이미지를 함께 배포합니다.

1. 두 `linux/amd64` Docker 이미지 빌드
2. Docker Hub에 각각 `latest`와 commit SHA tag push
3. compose를 EC2 `/opt/facemaxx`에 업로드
4. 기존 `/opt/facemaxx/.env`와 `/opt/chartagent/.env`의 비밀값은 보존하고 이미지 tag만 교체
5. 두 컨테이너 재시작과 localhost `8000`, `8010` health check

기존 FaceMaxx GitHub secret을 그대로 사용합니다.

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`
- `EC2_HOST`
- `EC2_USER`
- `EC2_SSH_KEY`

Nginx 설정은 `deploy/ec2/install-chartagent-nginx.sh`가 안전하게 식별할 수 있는 기존 FaceMaxx 서버 블록에만 적용합니다.

## 버전별 작도 API

기존 `/v1/analyses`, `/v1/analysis-jobs`, `/v1/follow-ups`의 요청·응답, 프롬프트, 모델 기본값은 유지합니다. 신버전 iOS만 별도 `POST /v2/chart-annotations`를 호출합니다. 기존 앱에는 작도 응답 필드나 추가 작업을 삽입하지 않습니다. 앱의 분석 API base URL은 계속 `/chartagent/v1`이며 작도 요청만 같은 서버의 `/chartagent/v2/chart-annotations`로 보냅니다.

```bash
curl --fail-with-body http://127.0.0.1:8010/v2/chart-annotations \
  -F 'image=@/absolute/path/chart.png' \
  -F 'locale=ko' \
  -F 'report_context=</absolute/path/annotation-context.json'
```

`report_context`는 필수 JSON이며 `consensus`, 순서가 유지된 `scenarios`, `structure`, `trend_evidence`, 선택적 `trigger`·`invalidation`·`target`을 포함합니다. 요청 locale은 앱이 지원하는 16개 언어 코드입니다. 응답은 `locale`, `image_width`, `image_height`, `summary`, 최대 3개의 `annotations`를 포함합니다. 좌표는 EXIF 방향을 정규화한 전체 이미지 기준 0~1이며 원본 이미지는 수정하지 않습니다.

작도 종류는 `line`, `zone`, `arrow`, `channel`입니다. 추세선은 실제 스윙 접점에 연결하고 평행 채널은 두 기준점과 반대 경계 한 점으로 같은 기울기의 두 선을 계산합니다. 각 작도의 `detail`은 관찰 근거, `outlook`은 유지·돌파·이탈에 따른 다음 방향, `scenario_index`는 연결된 기존 분석 시나리오의 0부터 시작하는 인덱스 또는 null입니다. 기존 분석과 충돌하는 방향이나 근거 없는 미래 가격 경로를 만들지 않습니다. 서버와 앱에서 좌표 및 시나리오 범위를 검증합니다.

작도는 전용 provider 인스턴스와 실행 한도를 사용합니다. `CHARTAGENT_ANNOTATION_MODEL` 기본값은 `gpt-6-astra`이고 reasoning은 `medium`입니다. 운영 기본 `CHARTAGENT_ANNOTATION_PROVIDER=openai_api`는 작도 모델의 API를 직접 사용합니다. API 호출 100초(1회), 전체 요청 115초로 제한하며 `CHARTAGENT_ANNOTATION_MAX_CONCURRENCY` 기본값은 2입니다. 한도가 차면 대기열 없이 `503 annotations_busy`를 반환합니다. `CHARTAGENT_ANNOTATIONS_ENABLED=false`로 작도만 중지할 수 있습니다(설정 후 프로세스 재시작 필요). 로컬 QA에서 `CHARTAGENT_ANNOTATION_PROVIDER=codex_cli`를 지정하면 Codex 85초 이후 API 폴백을 사용하되 전체 115초를 넘기지 않습니다. 앱 저장소의 로컬 QA 기본값은 `codex_cli`입니다. 기존 v1 분석 한도와 설정은 변경하지 않습니다. 작도 실패 시 앱은 이미 받은 분석과 원본 차트를 유지하고 재시도를 제공합니다.
