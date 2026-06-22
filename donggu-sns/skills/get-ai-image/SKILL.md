---
name: get-ai-image
description: Use when a blog/SNS post needs an AI-generated image (대표이미지·삽화)
  instead of a stock photo — 프롬프트로 이미지를 만든다. Backends: local ComfyUI(무료·무제한),
  Pollinations(무료 API), Cloudflare(무료티어), fal.ai(유료 nano-banana). 모델 선택형
  (flux-schnell·flux-dev·sdxl). NOT for 카드뉴스(use make-insta-card-news) or
  text-baked thumbnails(글자는 AI 약함 → 카드).
---

# get-ai-image

## Overview
프롬프트 → AI 생성 이미지 1장. `get-stock-image`의 **AI 버전**이다 — 같은 계약
(프롬프트→파일 저장 + JSON 1줄)이라 블로그 이미지 파이프라인(`prepare_blog_images`)에
스톡 대신 그대로 끼운다. 단일 진입점 `gen_image.py`, 백엔드·모델 선택형.

**핵심 원칙: 소스만 바뀌고 계약은 그대로.** 작성자는 stock이냐 ai냐만 고르면 되고,
저장·임베드·발행(대표이미지 포함)은 기존 파이프라인이 그대로 처리한다.

## When to Use
- 블로그 대표이미지·문단 삽화를 **스톡 말고 AI로** 만들고 싶을 때 (`blog` 한정 — 다른 채널은 [[writing-social-content]]의 채널 규칙)
- **When NOT:** 카드뉴스/캐러셀 → `make-insta-card-news` · **글자(한글) 박힌 이미지** → AI는 텍스트 약함, 카드로 · 동구님이 직접 찍은 결과물이 있으면 그게 1순위

## 백엔드 (무료 → 유료)
| backend | 비용 | 키 | 특징 |
|---|---|---|---|
| `comfyui` | **무료·무제한** | 없음(로컬) | M4 Max 로컬. 품질·해상도 최상, 모델 자유. 서버 떠 있어야 함(아래) |
| `pollinations` | 무료 | 없음 | URL 한 방, 즉시. 공용이라 느리거나 가끔 막힘. **폴백 기본값** |
| `cf` | 무료티어(~수백/일) | `CF_ACCOUNT_ID`·`CF_API_TOKEN` | Cloudflare Workers AI(Flux schnell). 안정적 |
| `fal` | **유료**(~$0.05~0.15/장) | `FAL_KEY` | nano-banana 등 최고품질 필요 시 |

**선택 우선순위:** `--backend` 명시 > env `GEN_IMAGE_BACKEND` > 자동(ComfyUI 응답하면 `comfyui`, 아니면 `pollinations`). 선택 백엔드 실패 시 `--fallback`(기본 pollinations)으로 자동 폴백.

## 모델 (`--model`)
- `flux-schnell` (기본) — 빠름(4 step), 블로그 대표이미지에 충분
- `flux-dev` — 고품질·느림
- `sdxl` — 가벼움·빠름, 일러스트풍
ComfyUI는 `workflows/<model>.json` 템플릿으로 그래프를 구성 → 모델 추가는 템플릿 추가로 끝.

## 사용
```
python3 gen_image.py "<영어 프롬프트>" <out.jpg> [--backend ...] [--model ...] \
    [--size 1200x630] [--seed N] [--fallback pollinations|none]
# 출력(stdout): {"backend","model","saved","prompt","seed","size"} JSON 1줄
```
프롬프트는 영어가 품질이 좋다. 대표이미지=가로(1200x630), 본문 삽화도 동일 비율 권장.

## 로컬 ComfyUI 서버
`comfyui` 백엔드는 로컬 서버가 떠 있어야 한다(127.0.0.1:8188):
```
bash start_comfyui.sh        # 떠 있으면 no-op, 아니면 기동 후 준비까지 대기
```
- 설치 위치: `~/ComfyUI` (venv `~/ComfyUI/.venv`, Apple Silicon MPS)
- 모델: `~/ComfyUI/models/checkpoints/flux1-schnell-fp8.safetensors`
- 첫 생성은 모델 로드로 느릴 수 있음(이후 빠름). 로그: `~/ComfyUI/logs/comfyui.log`
- 상시 띄우려면 launchd 등록(요청 시 구성).

### 주소 표준화 — `COMFYUI_URL` (호스트/컨테이너 한 변수)
ComfyUI는 **호스트 네이티브로 GPU**를 쓴다(맥 Docker는 GPU 패스스루 불가 → 컨테이너화하면 CPU로 느려짐). 그래서 스택은 컨테이너로 넣지 않고 **네트워크로 호출**한다. 같은 변수명 `COMFYUI_URL`을 컨텍스트별 값으로 둔다:
- **호스트 도구**(이 스킬 `gen_image.py`): `COMFYUI_URL=http://127.0.0.1:8188` — n8n `.env`에 있고 자동 로드된다.
- **컨테이너**(n8n/api 노드): `COMFYUI_URL=http://host.docker.internal:8188` — `docker-compose.yml`의 `x-n8n-env` 앵커에서 주입. n8n 노드에선 `{{ $env.COMFYUI_URL }}/prompt` 로 호출.
- 미설정 시 스킬 기본값은 `127.0.0.1:8188`. compose 변경은 n8n 컨테이너 재기동 후 반영.

## 블로그 파이프라인 통합
[[writing-social-content]]의 "블로그 이미지 배치"에서 **소스 선택**: stock(`get-stock-image`) | ai(이 스킬). 나머지(vault 저장 위치·임베드·hero=대표이미지)는 동일. 저장 경로·파일명 규칙도 그대로(`_img/<슬러그>/hero.jpg` 등) — `prepare_blog_images`가 업로드·치환, 발행기가 hero를 대표이미지로 올린다.

## Common Mistakes
| 실수 | 수정 |
|---|---|
| 글자 박힌 썸네일을 AI로 | AI는 텍스트 약함 → `make-insta-card-news` 카드 |
| ComfyUI 안 띄우고 `--backend comfyui` | 먼저 `start_comfyui.sh` (또는 자동 폴백에 맡김) |
| 한국어 프롬프트 | 영어로 — 품질 차이 큼 |
| 같은 이미지 재사용/장식용 남발 | 1장=1주제 (get-stock-image 원칙 동일) |

## Related
- 스톡 사진: `donggu-sns:get-stock-image`
- 업로드·치환·발행: `donggu-sns:publish-sns`(prepare_blog_images, cover_image)
- 카드뉴스: `donggu-sns:make-insta-card-news`
