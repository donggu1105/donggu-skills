---
name: get-stock-image
description: Use when a blog/Obsidian post, SNS body, or 대표이미지 needs a free stock photo, illustration, or real-subject image found by keyword — 무료 이미지·스톡 사진·삽화를 글 주제에 맞게 검색/다운로드. Covers Unsplash·Pexels·Pixabay·Wikimedia Commons·Openverse. NOT for 카드뉴스/carousel (use make-insta-card-news) or AI image generation.
---

# get-stock-image

## Overview
키워드 + 이미지 종류(`--kind`)를 주면 **적절한 무료 스톡 소스를 자동 라우팅**해 관련 이미지 1장을 내려받는다. 소스마다 강점이 달라, 종류별 폴백 ladder로 "앞 소스가 비거나 키가 없으면 다음"으로 넘어간다. 단일 진입점은 `get_stock.py`.

**핵심 원칙: 종류가 소스를 고른다.** 무드 사진은 Unsplash, 실사는 Commons, 추상 개념은 Pixabay — 사용자는 소스를 외울 필요 없이 `--kind`만 고르면 된다.

## When to Use
- 블로그/옵시디언 글·SNS 본문에 넣을 **사진·일러스트·실사 이미지**가 필요할 때
- "이 글에 어울리는 이미지 찾아줘", 대표이미지(hero), 본문 삽화
- **When NOT:** 카드뉴스/캐러셀 → `make-insta-card-news` · 동구님이 직접 찍은 스크린샷·결과물이 있으면 **그게 1순위**(이 스킬은 그게 없을 때)

## 소스별 특징 (라우팅 근거)
| 소스 | 강점 | 키 | 라이선스 |
|---|---|---|---|
| Unsplash | 감성·브랜드 무드 사진, alt 제공 | `UNSPLASH_ACCESS_KEY` | 무료·상업, 표기 권장 |
| Pexels | 폭넓고 실용적, 사진+영상 | `PEXELS_API_KEY` (보유) | 무료·상업, 표기 불필요 |
| Pixabay | 종류 최다(사진·벡터·일러스트) | `PIXABAY_API_KEY` | 무료·상업, 표기 불필요 |
| Commons | 실제 사물·인물·역사 "진짜 그것" | 무키 | CC/PD (항목별 — `license` 확인) |
| Openverse | CC 수억 장 메타검색, 최후 폴백 | 무키 | CC (항목별 표기 조건 상이) |

## kind → 폴백 순서
- `photo` (무드 사진): unsplash → pexels → pixabay
- `illustration` (벡터·삽화): pixabay → openverse
- `real` (실사·역사): commons → openverse → pexels
- `concept` (추상 개념): pixabay → unsplash → pexels

## 사용법
```bash
python3 get_stock.py "<영어 키워드>" <out.jpg> --kind photo|illustration|real|concept \
        [--orientation portrait|landscape|square] [--index N] [--source <강제>]
```
- 한국어 글이면 **영어 키워드로 변환**해 검색한다(스톡은 영어 인덱스). 예: "개발자 책상" → `developer desk`.
- 저장 후 **반드시 Read로 주제 적합성을 눈으로 확인** → 어긋나면 `--index` 를 올려 다른 결과로 재시도.
- 반환 JSON의 `license`·`credit`·`page` 를 발행 시 출처표기 판단에 쓴다(특히 commons·openverse는 CC라 표기가 필요할 수 있음).
- 키 없는 소스는 자동 skip → 폴백 진행. 전체 옵션은 `python3 get_stock.py --help`.

반환 예: `{"source":"pexels","credit":"...","page":"...","license":"...","saved":"out.jpg","fallback_order":[...]}`

## Common Mistakes
| 실수 | 수정 |
|---|---|
| 한국어 키워드로 검색 | 영어로 변환 (결과 인덱스가 영어) |
| 저장만 하고 Read 안 함 | 항상 눈으로 주제 확인 후 사용 |
| commons/openverse(CC) 출처표기 누락 | `license` 확인 후 표기 |
| 카드뉴스에 이 스킬 사용 | `make-insta-card-news` 로 |

## Setup
`.env`에 키 추가(없는 건 해당 소스만 skip, 나머지는 정상 동작):
- `PEXELS_API_KEY` — ✅ 이미 보유
- `UNSPLASH_ACCESS_KEY` — unsplash.com/developers (앱 등록, 무료)
- `PIXABAY_API_KEY` — pixabay.com/api/docs (무료)
- Commons·Openverse — 키 불필요

**키 자동 로드**: 키는 `~/workspace/projects/n8n/.env`에 한 줄씩 넣으면 실행 시 자동 로드된다(`export` 불필요). 다른 경로면 `GET_STOCK_ENV=/path/to/.env` 로 지정. 이미 환경에 있으면 그 값을 우선한다.

Pexels·Commons·Openverse만으로도 photo/real은 바로 동작하고, Unsplash·Pixabay는 키를 넣는 순간 폴백 ladder에 자동 합류한다.
