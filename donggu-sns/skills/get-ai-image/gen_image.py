#!/usr/bin/env python3
"""gen_image.py — 프롬프트 → AI 생성 이미지 1장. 백엔드·모델 선택형.

get-stock-image와 같은 계약(프롬프트→파일 저장 + JSON 1줄)이라, 블로그 이미지
파이프라인(prepare_blog_images)에 스톡 대신 그대로 끼울 수 있다.

사용:
  python3 gen_image.py "<프롬프트>" <out.jpg> [--backend ...] [--model ...]
                       [--size 1200x630] [--seed N]

백엔드(--backend, 생략 시 자동):
  openrouter   OpenRouter 종량 — OPENROUTER_API_KEY(헤르메스 키) 하나로 Gemini3/GPT 이미지 (기본 우선)
  comfyui      로컬 ComfyUI(127.0.0.1:8188) — 무료·무제한, Flux/SDXL
  pollinations 무료 API, 키 불필요 — 무키 최후 폴백
  cf           Cloudflare Workers AI 무료티어 — CF_ACCOUNT_ID·CF_API_TOKEN 필요
  fal          fal.ai 유료(nano-banana 등) — FAL_KEY 필요
  gemini       Google Gemini(nano-banana) 직결 — GEMINI_API_KEY 필요
자동 규칙: --backend 없으면 env GEN_IMAGE_BACKEND → 그래도 없으면 기본 openrouter,
           폴백 체인 openrouter → comfyui(로컬 떠 있을 때) → pollinations.

모델(--model): openrouter는 별칭 pro(기본, gemini-3-pro-image)·flash·flash-lite·
  nano-banana·gpt-image·gpt-image-hi·auto, 또는 슬러그(예: google/gemini-3-pro-image) 통과.
  그 외 백엔드는 flux-schnell·flux-dev·sdxl 등 백엔드별 매핑.
ComfyUI는 workflows/<model>.json 템플릿을 써서 그래프를 구성(모델 교체가 쉬움).

환경변수: GEN_IMAGE_BACKEND, COMFYUI_URL(기본 127.0.0.1:8188), OPENROUTER_API_KEY,
          CF_ACCOUNT_ID, CF_API_TOKEN, FAL_KEY, GEMINI_API_KEY
          (없으면 ~/.hermes/.env → n8n .env → ~/.env 순으로 자동 로드).
출력(stdout): {"backend","model","saved","prompt","seed"} JSON 1줄.
종료코드: 0 성공 / 2 실패(백엔드 불가·생성 실패).
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def comfy_base():
    """ComfyUI 서버 주소 — env COMFYUI_URL(.env 자동로드), 기본 호스트 127.0.0.1:8188.
    컨테이너에서 부르면 compose가 host.docker.internal 로 주입한다."""
    return os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")


def log(o):
    sys.stderr.write(json.dumps(o, ensure_ascii=False) + "\n")


def load_env():
    need = ("OPENROUTER_API_KEY", "CF_ACCOUNT_ID", "CF_API_TOKEN", "FAL_KEY",
            "GEMINI_API_KEY", "GEN_IMAGE_BACKEND", "COMFYUI_URL")
    if all(os.environ.get(k) for k in need):
        return
    for c in (os.environ.get("GEN_IMAGE_ENV"),
              os.path.expanduser("~/.hermes/.env"),
              os.path.expanduser("~/workspace/projects/n8n/.env"),
              os.path.expanduser("~/.env")):
        if not c or not os.path.isfile(c):
            continue
        for line in open(c, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            if k in need and not os.environ.get(k):
                os.environ[k] = v.strip().strip('"').strip("'")


def _save(data: bytes, out: str):
    with open(out, "wb") as f:
        f.write(data)


def _get(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _post_json(url, payload, headers=None, timeout=180):
    body = json.dumps(payload).encode()
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def comfy_reachable():
    try:
        _get(comfy_base() + "/system_stats", timeout=2)
        return True
    except Exception:
        return False


# ---- 백엔드 구현 ----

def gen_pollinations(prompt, out, model, w, h, seed):
    m = {"flux-schnell": "flux", "flux-dev": "flux", "sdxl": "flux"}.get(model, "flux")
    q = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{q}?width={w}&height={h}&model={m}&nologo=true"
    if seed is not None:
        url += f"&seed={seed}"
    _save(_get(url, timeout=120), out)
    return {"backend": "pollinations", "model": m}


def gen_cf(prompt, out, model, w, h, seed):
    acct = os.environ.get("CF_ACCOUNT_ID")
    tok = os.environ.get("CF_API_TOKEN")
    if not (acct and tok):
        raise RuntimeError("cf_creds_missing (CF_ACCOUNT_ID/CF_API_TOKEN)")
    cf_model = {
        "flux-schnell": "@cf/black-forest-labs/flux-1-schnell",
        "flux-dev": "@cf/black-forest-labs/flux-1-schnell",
        "sdxl": "@cf/stabilityai/stable-diffusion-xl-base-1.0",
    }.get(model, "@cf/black-forest-labs/flux-1-schnell")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{cf_model}"
    payload = {"prompt": prompt}
    if "flux" in cf_model:
        payload["steps"] = 6
    raw = _post_json(url, payload, headers={"Authorization": f"Bearer {tok}"}, timeout=120)
    # flux: {result:{image:<b64>}} · sdxl: 바이너리(png) 직접
    try:
        j = json.loads(raw)
        b64 = j.get("result", {}).get("image")
        if b64:
            _save(base64.b64decode(b64), out)
        else:
            raise RuntimeError(f"cf_no_image: {str(j)[:160]}")
    except json.JSONDecodeError:
        _save(raw, out)  # sdxl 바이너리
    return {"backend": "cf", "model": cf_model}


def gen_fal(prompt, out, model, w, h, seed):
    key = os.environ.get("FAL_KEY")
    if not key:
        raise RuntimeError("fal_key_missing")
    fal_model = {
        "flux-schnell": "fal-ai/flux/schnell",
        "flux-dev": "fal-ai/flux/dev",
        "nano-banana": "fal-ai/nano-banana-pro",
        "sdxl": "fal-ai/fast-sdxl",
    }.get(model, "fal-ai/flux/schnell")
    raw = _post_json(f"https://fal.run/{fal_model}",
                     {"prompt": prompt, "image_size": {"width": w, "height": h}},
                     headers={"Authorization": f"Key {key}"}, timeout=180)
    j = json.loads(raw)
    img_url = (j.get("images") or [{}])[0].get("url")
    if not img_url:
        raise RuntimeError(f"fal_no_image: {str(j)[:160]}")
    _save(_get(img_url, timeout=120), out)
    return {"backend": "fal", "model": fal_model}


def gen_gemini(prompt, out, model, w, h, seed):
    """Google Gemini API 이미지 생성 (nano-banana = gemini-2.5-flash-image).
    구독과 무관 — AI Studio API 키(GEMINI_API_KEY). 무료 티어(하루 제한)/유료 ~$0.04/장.
    정확한 픽셀 크기 대신 종횡비만 지원 → 요청 크기에 가장 가까운 비율로 매핑."""
    import base64
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("gemini_key_missing")
    gem_model = model if str(model).startswith("gemini") else "gemini-2.5-flash-image"
    ratios = {"1:1": 1.0, "2:3": 2/3, "3:2": 3/2, "3:4": 3/4, "4:3": 4/3,
              "4:5": 4/5, "5:4": 5/4, "9:16": 9/16, "16:9": 16/9, "21:9": 21/9}
    ar = min(ratios, key=lambda k: abs(ratios[k] - (w / h)))
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"],
                             "imageConfig": {"aspectRatio": ar}},
    }
    raw = _post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{gem_model}:generateContent",
        body, headers={"x-goog-api-key": key}, timeout=180)
    j = json.loads(raw)
    for cand in j.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            data = (part.get("inlineData") or part.get("inline_data") or {}).get("data")
            if data:
                _save(base64.b64decode(data), out)
                return {"backend": "gemini", "model": gem_model, "aspect_ratio": ar}
    raise RuntimeError(f"gemini_no_image: {str(j)[:200]}")


def gen_comfyui(prompt, out, model, w, h, seed):
    tpl_path = os.path.join(HERE, "workflows", f"{model}.json")
    if not os.path.isfile(tpl_path):
        raise RuntimeError(f"no_workflow_template: {model}.json")
    tpl = open(tpl_path, encoding="utf-8").read()
    graph = json.loads(
        tpl.replace("{PROMPT}", json.dumps(prompt)[1:-1])
           .replace("{WIDTH}", str(w)).replace("{HEIGHT}", str(h))
           .replace("{SEED}", str(seed if seed is not None else 0))
    )
    resp = json.loads(_post_json(comfy_base() + "/prompt", {"prompt": graph}, timeout=30))
    pid = resp.get("prompt_id")
    if not pid:
        raise RuntimeError(f"comfy_enqueue_failed: {str(resp)[:160]}")
    # /history 폴링 → 결과 이미지 파일명
    for _ in range(180):  # ~3분
        time.sleep(1)
        hist = json.loads(_get(f"{comfy_base()}/history/{pid}", timeout=10) or b"{}")
        if pid in hist:
            outs = hist[pid].get("outputs", {})
            for node in outs.values():
                for im in node.get("images", []):
                    fn = urllib.parse.urlencode(
                        {"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                         "type": im.get("type", "output")})
                    _save(_get(f"{comfy_base()}/view?{fn}", timeout=30), out)
                    return {"backend": "comfyui", "model": model}
            raise RuntimeError("comfy_no_image_in_history")
    raise RuntimeError("comfy_timeout")


# ---- OpenRouter (헤르메스 키 하나로 Gemini3/GPT 이미지) ----

OPENROUTER_MODEL_MAP = {
    "pro": "google/gemini-3-pro-image",
    "flash": "google/gemini-3.1-flash-image",
    "flash-lite": "google/gemini-3.1-flash-lite-image",
    "nano-banana": "google/gemini-2.5-flash-image",
    "gpt-image": "openai/gpt-5-image",
    "gpt-image-hi": "openai/gpt-5.4-image-2",
    "auto": "openrouter/auto",
}
OPENROUTER_DEFAULT_MODEL = "google/gemini-3-pro-image"  # 현재 기준 최고 성능

_ASPECT_RATIOS = {"1:1": 1.0, "2:3": 2/3, "3:2": 3/2, "3:4": 3/4, "4:3": 4/3,
                  "4:5": 4/5, "5:4": 5/4, "9:16": 9/16, "16:9": 16/9, "21:9": 21/9}


def _openrouter_model(model):
    """별칭 → 슬러그. 슬래시 포함이면 그대로 통과. 타 백엔드 기본값(flux-*)은 기본 모델로."""
    if not model:
        return OPENROUTER_DEFAULT_MODEL
    if model in OPENROUTER_MODEL_MAP:
        return OPENROUTER_MODEL_MAP[model]
    if "/" in model:
        return model
    return OPENROUTER_DEFAULT_MODEL


def _nearest_ratio(w, h):
    return min(_ASPECT_RATIOS, key=lambda k: abs(_ASPECT_RATIOS[k] - (w / h)))


def _decode_data_uri(u):
    b64 = u.split(",", 1)[1] if "," in u else u
    return base64.b64decode(b64)


def _extract_openrouter_image(j):
    """OpenRouter 챗-이미지 응답에서 data URI를 방어적으로 추출.
    형태 편차 대비: message.images[].image_url.url / content parts의 image_url / inline_data."""
    for ch in j.get("choices", []):
        msg = ch.get("message", {}) or {}
        for im in (msg.get("images") or []):
            u = (im.get("image_url") or {}).get("url") or im.get("url")
            if isinstance(u, str) and u.startswith("data:"):
                return u
        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                u = (part.get("image_url") or {}).get("url")
                if isinstance(u, str) and u.startswith("data:"):
                    return u
                inl = part.get("inlineData") or part.get("inline_data")
                if inl and inl.get("data"):
                    mt = inl.get("mimeType") or inl.get("mime_type") or "image/png"
                    return f"data:{mt};base64,{inl['data']}"
    return None


def gen_openrouter(prompt, out, model, w, h, seed):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("openrouter_key_missing")
    slug = _openrouter_model(model)
    ar = _nearest_ratio(w, h)
    hint = (f"\n\n(Aspect ratio {ar}, wide landscape composition for a {w}x{h} blog hero image.)"
            if w >= h else f"\n\n(Aspect ratio {ar}, portrait composition.)")
    body = {"model": slug,
            "messages": [{"role": "user", "content": prompt + hint}],
            "modalities": ["image", "text"]}
    raw = _post_json("https://openrouter.ai/api/v1/chat/completions", body,
                     headers={"Authorization": f"Bearer {key}",
                              "HTTP-Referer": "https://github.com/donggu1105/donggu-skills",
                              "X-Title": "donggu-sns get-ai-image"}, timeout=180)
    j = json.loads(raw)
    uri = _extract_openrouter_image(j)
    if not uri:
        err = j.get("error") or {}
        raise RuntimeError(f"openrouter_no_image: {err or str(j)[:200]}")
    _save(_decode_data_uri(uri), out)
    return {"backend": "openrouter", "model": slug, "aspect_ratio": ar}


BACKENDS = {"openrouter": gen_openrouter, "comfyui": gen_comfyui,
            "pollinations": gen_pollinations, "cf": gen_cf, "fal": gen_fal,
            "gemini": gen_gemini}


def choose_backend(explicit):
    if explicit:
        return explicit
    env = os.environ.get("GEN_IMAGE_BACKEND")
    if env:
        return env
    return "openrouter"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("out")
    ap.add_argument("--backend", default=None, choices=list(BACKENDS))
    ap.add_argument("--model", default="flux-schnell")
    ap.add_argument("--size", default="1200x630")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--fallback", default="pollinations",
                    help="선택 백엔드 실패 시 폴백(none이면 폴백 안 함)")
    a = ap.parse_args()
    load_env()
    w, h = (int(x) for x in a.size.lower().split("x"))

    explicit = a.backend or os.environ.get("GEN_IMAGE_BACKEND")
    backend = choose_backend(a.backend)
    if explicit:
        order = [backend]
        if a.fallback and a.fallback != "none" and a.fallback != backend:
            order.append(a.fallback)
    else:
        # 자동 기본: openrouter 우선 → comfyui(로컬 떠 있을 때만) → pollinations(무키 최후 보루)
        order = ["openrouter"]
        if comfy_reachable():
            order.append("comfyui")
        order.append("pollinations")
    seen = set()
    order = [b for b in order if not (b in seen or seen.add(b))]

    last_err = None
    for b in order:
        try:
            meta = BACKENDS[b](a.prompt, a.out, a.model, w, h, a.seed)
            sz = os.path.getsize(a.out) if os.path.isfile(a.out) else 0
            if sz < 1000:
                raise RuntimeError(f"image_too_small({sz}b)")
            res = {"saved": a.out, "prompt": a.prompt, "seed": a.seed,
                   "size": f"{w}x{h}", **meta}
            print(json.dumps(res, ensure_ascii=False))
            return
        except Exception as e:
            last_err = f"{b}: {e}"
            log({"backend_failed": last_err})
    log({"error": "all_backends_failed", "detail": last_err})
    sys.exit(2)


if __name__ == "__main__":
    main()
