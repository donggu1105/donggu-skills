# 기계 검수 (선택) — 로컬 서버 + 헤드리스 크롬 캡처

기본 검수는 사용자 육안이다. 레이아웃 깨짐을 자체 확인해야 할 때만 이 절차를 쓴다.

```bash
cd <덱 폴더> && (python3 -m http.server 8139 >/dev/null 2>&1 &)
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CHROME" --headless=new --disable-gpu --no-first-run --disable-component-update \
  --disable-background-networking --user-data-dir=/tmp/cr-$RANDOM \
  --window-size=1600,900 --virtual-time-budget=4200 \
  --screenshot=qa-N.png "http://localhost:8139/발표.html?v=임의값#N" >/tmp/cr.log 2>&1
```

## 함정 (전부 실측)

1. **`?v=N` 캐시 버스터 필수** — 없으면 수정 전 판을 캡처하고도 모른다(동일 픽셀 3연속 실사례).
2. **`--user-data-dir`은 호출마다 새 경로** — 재사용하면 두 번째 호출이 행.
3. **크롬 기동이 수십 초 걸릴 수 있다**(업데이터 동작 중엔 about:blank도 40초+). 타임아웃을 넉넉히 잡고 백그라운드로 돌린다. `pkill` 패턴은 `"[h]eadless=new"`처럼 괄호 트릭으로(자기 셸 자살 방지).
4. **Playwright MCP는 프로필 잠금 충돌** — 사용자가 그 창을 열어 두면 못 쓴다. 헤드리스 크롬이 안전한 기본.
5. **zsh 글롭은 빈 매치에서 명령 전체를 중단** — 정리는 `rm *.png`가 아니라 `find -maxdepth 1 -name 'qa-*.png' -delete`.
6. 무한 애니메이션(이동 점 등)은 캡처마다 다른 위치에 찍힌다 — 깨짐이 아니다.
