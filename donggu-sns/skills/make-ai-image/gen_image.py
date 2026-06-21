#!/usr/bin/env python3
"""gen_image.py — 프롬프트 → AI 생성 이미지 1장. 백엔드·모델 선택형.

get-stock-image와 같은 계약(프롬프트→파일 저장 + JSON 1줄)이라, 블로그 이미지
파이프라인(prepare_blog_images)에 스톡 대신 그대로 끼울 수 있다.

사용:
  python3 gen_image.py "<프롬프트>" <out.jpg> [--backend ...] [--model ...]
                       [--size 1200x630] [--seed N]

백엔드(--backend, 생략 시 자동):
  comfyui      로컬 ComfyUI(127.0.0.1:8188) — 무료·무제한 (기본 우선)
  pollinations 무료 API, 키 불필요 — 로컬 꺼졌을 때 폴백
  cf           Cloudflare Workers AI 무료티어 — CF_ACCOUNT_ID·CF_API_TOKEN 필요
  fal          fal.ai 유료(nano-banana 등) — FAL_KEY 필요
자동 규칙: --backend 없으면 env GEN_IMAGE_BACKEND → 그래도 없으면
           ComfyUI 응답하면 comfyui, 아니면 pollinations.

모델(--model): flux-schnell(빠름)·flux-dev(고품질)·sdxl. 백엔드별로 매핑된다.
ComfyUI는 workflows/<model>.json 템플릿을 써서 그래프를 구성(모델 교체가 쉬움).

환경변수: GEN_IMAGE_BACKEND, COMFYUI_URL(기본 127.0.0.1:8188),
          CF_ACCOUNT_ID, CF_API_TOKEN, FAL_KEY (없으면 n8n .env 자동 로드).
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
DEFAULT_COMFY = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")


def log(o):
    sys.stderr.write(json.dumps(o, ensure_ascii=False) + "\n")


def load_env():
    need = ("CF_ACCOUNT_ID", "CF_API_TOKEN", "FAL_KEY", "GEN_IMAGE_BACKEND")
    if all(os.environ.get(k) for k in need):
        return
    for c in (os.environ.get("GEN_IMAGE_ENV"),
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
        _get(DEFAULT_COMFY + "/system_stats", timeout=2)
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
    resp = json.loads(_post_json(DEFAULT_COMFY + "/prompt", {"prompt": graph}, timeout=30))
    pid = resp.get("prompt_id")
    if not pid:
        raise RuntimeError(f"comfy_enqueue_failed: {str(resp)[:160]}")
    # /history 폴링 → 결과 이미지 파일명
    for _ in range(180):  # ~3분
        time.sleep(1)
        hist = json.loads(_get(f"{DEFAULT_COMFY}/history/{pid}", timeout=10) or b"{}")
        if pid in hist:
            outs = hist[pid].get("outputs", {})
            for node in outs.values():
                for im in node.get("images", []):
                    fn = urllib.parse.urlencode(
                        {"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                         "type": im.get("type", "output")})
                    _save(_get(f"{DEFAULT_COMFY}/view?{fn}", timeout=30), out)
                    return {"backend": "comfyui", "model": model}
            raise RuntimeError("comfy_no_image_in_history")
    raise RuntimeError("comfy_timeout")


BACKENDS = {"comfyui": gen_comfyui, "pollinations": gen_pollinations,
            "cf": gen_cf, "fal": gen_fal}


def choose_backend(explicit):
    if explicit:
        return explicit
    env = os.environ.get("GEN_IMAGE_BACKEND")
    if env:
        return env
    return "comfyui" if comfy_reachable() else "pollinations"


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

    backend = choose_backend(a.backend)
    order = [backend]
    if a.fallback and a.fallback != "none" and a.fallback != backend:
        order.append(a.fallback)

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
