#!/usr/bin/env python3
"""AX 산업변화 한 판 요약 카드 렌더러.

usage: python3 render_card.py card.json out.png
card.json 스키마(모든 텍스트는 공개 브리핑과 같은 사실만, 새 숫자 금지):
{
  "tag": "🚚 AX로 바뀌는 산업 · 물류 D1/4",
  "title": "트럭을 <b>얼마나 꽉 채우나</b>가<br>이익을 가른다",   # <b>=주황 강조, <br> 허용
  "subtitle": "XPO(미국 LTL 운송사) — AI가 바꾸는 건 <b>배차 판단</b>",
  "before": {"emoji": "🧑‍💼", "title": "전: 사람의 경험", "text": "..."},
  "after":  {"emoji": "🤖", "title": "후: AI ...", "text": "..."},
  "money": {"heading": "📦 왜 돈이 되나 — ...",            # 선택
            "items": [{"label": "덜 채운 트럭", "pct": 55, "caption": "...", "highlight": false},
                      {"label": "꽉 채운 트럭 ✅", "pct": 92, "caption": "...", "highlight": true}]},
  "numbers": [{"value": "84% → 80%", "desc": "영업비율<br>..."}],   # 최대 3
  "confirmed": ["..."], "unknown": ["..."],
  "question": "🤔 ...",
  "sources": "XPO 2Q26 10-Q · ..."
}
"""
import html, json, os, subprocess, sys, tempfile

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W = 1080

CSS = """*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;background:#f5f1ea;font-family:"Apple SD Gothic Neo","Pretendard",sans-serif;color:#1d2433;padding:56px}
.tag{display:inline-block;background:#1d2433;color:#fff;font-weight:700;font-size:22px;padding:8px 18px;border-radius:30px}
h1{font-size:54px;line-height:1.25;margin:22px 0 10px;font-weight:800}h1 b{color:#e0662a}
.sub{font-size:24px;color:#5b6475;line-height:1.4}.sec{margin-top:40px}.st{font-size:26px;font-weight:800;margin-bottom:16px}
.flow{display:flex;align-items:stretch;gap:18px}.box{flex:1;background:#fff;border-radius:22px;padding:26px;box-shadow:0 4px 0 #e2dbcf}
.box .e{font-size:54px}.box h3{font-size:26px;margin:10px 0 8px}.box p{font-size:21px;line-height:1.5;color:#3a4252}
.arrow{display:flex;align-items:center;font-size:44px;color:#e0662a;font-weight:900}
.before{border-top:8px solid #9aa3b2}.after{border-top:8px solid #e0662a}
.truck{display:flex;gap:30px}.tr{flex:1;background:#fff;border-radius:22px;padding:22px 26px}
.tr .lbl{font-size:21px;font-weight:700;margin-bottom:10px;height:30px;line-height:30px}
.bar{height:38px;background:#ece6db;border-radius:10px;overflow:hidden}.bar span{display:block;height:100%}
.tr .cap{font-size:19px;color:#5b6475;margin-top:8px;line-height:1.4}
.nums{display:flex;gap:18px}.n{flex:1;background:#1d2433;color:#fff;border-radius:22px;padding:24px}
.n .v{font-size:38px;font-weight:800;color:#ffb37a}.n .d{font-size:20px;line-height:1.45;margin-top:8px;color:#d7dbe3}
.chk{display:flex;gap:30px}.c{flex:1;border-radius:22px;padding:22px 24px;font-size:21px;line-height:1.5}
.ok{background:#e3f1e5}.no{background:#fbe4dc}.c b{font-size:23px;display:block;margin-bottom:6px}
.q{margin-top:36px;background:#fff3c9;border-radius:22px;padding:26px 30px;font-size:25px;line-height:1.5;font-weight:700}
.foot{margin-top:22px;font-size:17px;color:#8a92a1}"""


def rich(s):
    """escape, then re-allow only <b>, <br>, <u>."""
    s = html.escape(s or "", quote=False)
    for t in ("b", "u"):
        s = s.replace(f"&lt;{t}&gt;", f"<{t}>").replace(f"&lt;/{t}&gt;", f"</{t}>")
    return s.replace("&lt;br&gt;", "<br>").replace("&lt;br/&gt;", "<br>")


def build(c):
    p = [f'<span class="tag">{rich(c["tag"])}</span>', f'<h1>{rich(c["title"])}</h1>']
    if c.get("subtitle"):
        p.append(f'<div class="sub">{rich(c["subtitle"])}</div>')
    if c.get("before") and c.get("after"):
        b, a = c["before"], c["after"]
        p.append('<div class="sec"><div class="st">🔄 무엇이 바뀌나</div><div class="flow">'
                 f'<div class="box before"><div class="e">{rich(b.get("emoji",""))}</div><h3>{rich(b["title"])}</h3><p>{rich(b["text"])}</p></div>'
                 '<div class="arrow">➜</div>'
                 f'<div class="box after"><div class="e">{rich(a.get("emoji",""))}</div><h3>{rich(a["title"])}</h3><p>{rich(a["text"])}</p></div></div></div>')
    m = c.get("money")
    if m and m.get("items"):
        items = "".join(
            f'<div class="tr"><div class="lbl">{rich(i["label"])}</div><div class="bar"><span style="width:{max(0,min(100,int(i.get("pct",50))))}%;background:{"#e0662a" if i.get("highlight") else "#9aa3b2"}"></span></div><div class="cap">{rich(i.get("caption",""))}</div></div>'
            for i in m["items"][:2])
        p.append(f'<div class="sec"><div class="st">{rich(m.get("heading","💰 돈의 흐름"))}</div><div class="truck">{items}</div></div>')
    if c.get("numbers"):
        ns = "".join(f'<div class="n"><div class="v">{rich(n["value"])}</div><div class="d">{rich(n["desc"])}</div></div>' for n in c["numbers"][:3])
        p.append(f'<div class="sec"><div class="st">🔢 숫자 {len(c["numbers"][:3])}개</div><div class="nums">{ns}</div></div>')
    if c.get("confirmed") or c.get("unknown"):
        ok = "<br>".join(rich(x) for x in c.get("confirmed", []))
        no = "<br>".join(rich(x) for x in c.get("unknown", []))
        p.append('<div class="sec"><div class="st">⚖️ 확인된 것 vs 아직 모르는 것</div><div class="chk">'
                 f'<div class="c ok"><b>✅ 확인</b>{ok}</div><div class="c no"><b>❓ 미확인</b>{no}</div></div></div>')
    if c.get("question"):
        p.append(f'<div class="q">{rich(c["question"])}</div>')
    if c.get("sources"):
        p.append(f'<div class="foot">출처: {rich(c["sources"])}</div>')
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{"".join(p)}</body></html>'


def main():
    src, out = sys.argv[1], os.path.abspath(sys.argv[2])
    c = json.load(open(src, encoding="utf-8"))
    d = tempfile.mkdtemp()
    hp = os.path.join(d, "card.html")
    open(hp, "w", encoding="utf-8").write(build(c))
    # 콘텐츠 높이를 측정한 뒤 그 높이로 스크린샷
    mh = os.path.join(d, "card_m.html")
    open(mh, "w", encoding="utf-8").write(build(c).replace(
        "</body>", "<script>document.title=document.body.scrollHeight</script></body>"))
    r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--dump-dom", "--window-size=1080,4000",
                        "file://" + mh], capture_output=True, text=True, timeout=60)
    import re
    mt = re.search(r"<title>(\d+)</title>", r.stdout)
    h = int(mt.group(1)) + 10 if mt else 1700
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    f"--window-size={W},{h}", f"--screenshot={out}", "file://" + hp],
                   capture_output=True, timeout=60)
    if not os.path.exists(out) or os.path.getsize(out) < 10000:
        sys.exit("render failed")
    print(f"OK {out} {W}x{h}")


if __name__ == "__main__":
    main()
