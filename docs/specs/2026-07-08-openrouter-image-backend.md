# get-ai-image: OpenRouter 백엔드 추가 (Hermes 키 통일)

- 날짜: 2026-07-08
- 대상 스킬: `donggu-sns:get-ai-image` (`gen_image.py`)
- 소스 레포: `donggu1105/donggu-skills` → `donggu-sns/skills/get-ai-image/`

## 목적

블로그/메일리 글에 들어가는 AI 생성 이미지를, **Hermes에 이미 있는 OpenRouter 키 하나**로
만들 수 있게 한다. 별도 `GEMINI_API_KEY` 없이 Hermes(`~/.hermes/.env`)의 `OPENROUTER_API_KEY`
하나로 청구·관측을 통일하는 것이 핵심.

## 현재 상태 (as-is)

`gen_image.py`는 이미 프롬프트→이미지 1장을 만드는 **백엔드/모델 선택형** 도구다.
기존 백엔드: `comfyui`(로컬 무료·무제한) · `pollinations`(무료) · `cf`(Cloudflare) ·
`gemini`(nano-banana 직결, `GEMINI_API_KEY`) · `fal`(유료). `get-stock-image`와 동일 계약
(프롬프트→파일 저장 + JSON 1줄)이라 블로그 이미지 파이프라인(`prepare_blog_images`)에 그대로 끼워진다.
`writing-social-content`에 이미 stock|ai 소스 분기가 존재한다 → **그 흐름은 건드리지 않는다.**

**빠진 것:** OpenRouter 백엔드. 그리고 `load_env()`가 `~/.hermes/.env`를 읽지 않음.

## 사실 확인 (실측)

- OpenRouter `/api/v1/models` 343개 중 **이미지 출력(생성) 가능 10개**가 전부.
  나머지 169개는 이미지 **입력(비전)**이라 생성 불가. Flux·SDXL·SD·Ideogram·Recraft·DALL·E·
  Imagen·Seedream 등은 OpenRouter에 **0개**(전용 디퓨전은 fal/로컬 ComfyUI 영역).
- 생성 10개 = 사실상 2계열: **Google Gemini 이미지 6종** + **OpenAI GPT 이미지 3종** + `openrouter/auto`.
- 현재 기준 최고 성능 티어: **`google/gemini-3-pro-image`** (기본값으로 채택).

## 설계 (to-be)

### 1. 새 백엔드 `gen_openrouter(prompt, out, model, w, h, seed)`
- `POST https://openrouter.ai/api/v1/chat/completions`
- 헤더: `Authorization: Bearer $OPENROUTER_API_KEY`, `Content-Type: application/json`
- 바디: `{"model": <슬러그>, "messages":[{"role":"user","content": <프롬프트 + 비율 힌트>}], "modalities":["image","text"]}`
- 응답에서 이미지(data URI base64) 추출 → base64 디코드 → `_save(...)`.
  - 예상 경로: `choices[0].message.images[0].image_url.url` (=`data:image/...;base64,...`).
    **구현 시 실호출 1건으로 정확한 필드 경로를 확정**하고, 대체 경로(content parts의 inline data)도 방어적으로 파싱한다.
- 반환: `{"backend":"openrouter","model":<슬러그>}` (+ 가능하면 aspect ratio)
- 키 없으면 `RuntimeError("openrouter_key_missing")`.

### 2. 모델 별칭 맵 (`--model`)
| 별칭 | 슬러그 | 비고 |
|---|---|---|
| (기본, openrouter) | `google/gemini-3-pro-image` | **현재 최고 성능** |
| `pro` | `google/gemini-3-pro-image` | |
| `flash` | `google/gemini-3.1-flash-image` | 빠름·저렴 |
| `flash-lite` | `google/gemini-3.1-flash-lite-image` | 최저비용 |
| `nano-banana` | `google/gemini-2.5-flash-image` | 구세대 저가 |
| `gpt-image` | `openai/gpt-5-image` | OpenAI 계열 |
| `gpt-image-hi` | `openai/gpt-5.4-image-2` | OpenAI 최신 |
| `auto` | `openrouter/auto` | 자동 라우팅 |
| `*/*` (슬래시 포함) | 입력값 그대로 | 임의 모델 통과 |

기본 해석 규칙: 별칭 맵에 있으면 그 슬러그, `/` 포함이면 그대로, 그 외(예: `flux-schnell`
같은 타 백엔드 기본값)는 openrouter 기본값(`gemini-3-pro-image`)으로 폴백.

### 3. 기본 동작 / 폴백 체인 (사용자 결정 반영: OpenRouter 우선, ComfyUI 폴백, 선택 가능)
```
choose_backend: --backend 명시 > env GEN_IMAGE_BACKEND > 기본 "openrouter"
자동 폴백 체인(--backend 미지정 시): openrouter → comfyui(comfy_reachable()일 때만) → pollinations(무키 최후 보루)
--backend X 명시: X로 고정 + 기존 --fallback 동작 유지 (선택 자유)
```
- `comfyui`는 로컬 서버가 떠 있을 때만 체인에 넣어 30초 헛대기를 피한다(`comfy_reachable()` 선검사).
- 기존 `--fallback` 단일 인자 동작은 명시 백엔드 사용 시 그대로 유지(하위호환).

### 4. 키 자동 로드 — Hermes 통일
`load_env()` 수정:
- `need` 튜플에 `OPENROUTER_API_KEY` 추가.
- 탐색 경로에 **`~/.hermes/.env` 추가** (기존 `GEN_IMAGE_ENV`, `~/workspace/projects/n8n/.env`, `~/.env` 앞/뒤 적절 위치).
→ 설정 없이 Hermes 키 자동 인식.

### 5. 종횡비 처리
OpenRouter 챗-이미지 경로는 픽셀 정확 크기를 보장하지 않는다(현 `gemini` 백엔드와 동일 한계).
요청 `w/h`에 가장 가까운 비율을 **프롬프트에 힌트로 주입**(예: "wide 16:9 landscape, ~1200x630 composition").
stdlib만 사용(PIL 의존성 추가 안 함) → 리사이즈/크롭은 하지 않고 파이프라인 기존 동작과 일치시킨다.

### 6. 문서
- `SKILL.md`: 백엔드 표에 `openrouter` 행(비용=OpenRouter 종량, 키=`OPENROUTER_API_KEY`(Hermes), 특징=Gemini3/GPT image), 선택 우선순위·env·모델 별칭 갱신.
- `gen_image.py` docstring 갱신(백엔드·env 목록).

## 변경 파일
- `donggu-sns/skills/get-ai-image/gen_image.py` (백엔드 추가·env·choose_backend·모델맵)
- `donggu-sns/skills/get-ai-image/SKILL.md` (문서)
- `donggu-sns/.claude-plugin/plugin.json` (version `2.2.0` → `2.3.0`)

## 하지 않는 것 (YAGNI / 범위 밖)
- Flux/SDXL을 OpenRouter로 (불가 — ComfyUI/fal 유지)
- fal 모델 맵 확장(Ideogram/Recraft 등) — 이번 범위 아님(추후 별건)
- `writing-social-content` 흐름 개편 — 이미 stock|ai 분기 존재
- 픽셀 정확 리사이즈(PIL 도입)

## 검증
1. `python3 gen_image.py "a calm minimal wooden desk, soft daylight, wide 16:9 landscape" /tmp/or_test.jpg --backend openrouter` → JSON 1줄 + 파일 >1KB, `backend=openrouter`, `model=google/gemini-3-pro-image`.
2. `--model flash` / `--model gpt-image` 별칭이 올바른 슬러그로 호출되는지.
3. 폴백: 잘못된 키(임시)로 openrouter 실패 시 comfyui(떠 있으면)/pollinations로 폴백되는지.
4. 키 자동 로드: 셸 env 없이도 `~/.hermes/.env`에서 `OPENROUTER_API_KEY`가 잡히는지.
5. 회귀: 기존 `--backend comfyui`, `pollinations` 정상 동작(계약·JSON 형식 불변).

## 롤아웃
1. 소스 레포(`marketplaces/donggu-skills`) 편집 → 커밋.
2. 즉시 사용 위해 캐시(`cache/donggu-skills/donggu-sns/2.2.0/...`)에 편집분 동기화(또는 버전 범프 후 재설치).
3. 필요 시 `origin/main` 푸시.

## 리스크
- OpenRouter 이미지 응답 스키마가 문서와 다를 수 있음 → 구현 첫 실호출로 확정 + 방어적 파싱.
- pro 모델은 flash보다 장당 비용 큼 → 기본이 최고화질이라 대량 생성 시 `--model flash`로 낮추는 것을 문서에 명시.
