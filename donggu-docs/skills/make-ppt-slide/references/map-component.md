# Tightened Map Component

지리·동선·이벤트 로케이션·매장 네트워크·캠퍼스·도시 간 관계 페이지에 사용. 새 레이아웃이 아니라 **`S08 Duo Compare`의 우측 슬롯 확장**.

## 계약

- 슬라이드에는 `data-layout="S08"` 유지.
- 좌측은 관계 노트·설명 카드로 유지.
- 우측을 map 패널로 교체.
- 마커·연결선·카드·`+`·`-`·`DRAG` 컨트롤 포함.
- 슬라이드 네비게이션 안정을 위해 휠 줌·드래그는 기본 비활성.
- 라이브 맵 자산 실패 시에도 슬라이드가 읽히도록 정적 fallback 제공.

## 최소 HTML

```html
<section class="slide light" data-layout="S08" data-animate="duo-mirror">
  <div class="canvas-card">
    <div class="chrome-min">
      <div class="l">Field Map</div>
      <div class="r">08 / NN</div>
    </div>
    <div class="duo-compare">
      <div>
        <div class="t-meta">Route Logic</div>
        <h2 class="h-xl">One network, three anchors</h2>
        <div class="map-note-list">
          <div class="relation-card">
            <div class="nb">01</div>
            <div>
              <div class="ttl">Anchor A to Anchor B</div>
              <div class="desc">공간·운영 관계를 한 줄로.</div>
            </div>
          </div>
          <div class="relation-card">
            <div class="nb">02</div>
            <div>
              <div class="ttl">Anchor B to Anchor C</div>
              <div class="desc">발표 호흡에 맞춰 짧게.</div>
            </div>
          </div>
        </div>
      </div>
      <div class="map-panel">
        <div class="map-controls">
          <button type="button" data-map-ctrl="zoom-in">+</button>
          <button type="button" data-map-ctrl="zoom-out">-</button>
          <button type="button" data-map-ctrl="drag">DRAG</button>
        </div>
        <div class="map-static">
          <div class="map-line"></div>
          <div class="map-marker" style="left:22%;top:62%">A</div>
          <div class="map-marker" style="left:56%;top:38%">B</div>
          <div class="map-marker" style="left:78%;top:58%">C</div>
        </div>
      </div>
    </div>
  </div>
</section>
```

## 선택 CSS

```css
.map-panel{position:relative;min-height:58vh;background:var(--grey-1);overflow:hidden}
.map-controls{position:absolute;right:16px;top:16px;z-index:2;display:flex;gap:8px}
.map-controls button{border:1px solid var(--ink);background:var(--paper);padding:8px 10px;font:600 12px var(--mono);border-radius:0}
.map-static{position:absolute;inset:0}
.map-line{position:absolute;left:24%;top:52%;width:54%;height:1px;background:var(--ink);transform:rotate(-6deg);transform-origin:left center}
.map-marker{position:absolute;width:34px;height:34px;display:grid;place-items:center;background:var(--accent);color:var(--accent-on);font:600 12px var(--mono)}
.map-note-list{display:grid;gap:16px;margin-top:32px}
.relation-card{display:grid;grid-template-columns:auto 1fr;gap:14px;border-top:1px solid var(--ink);padding-top:14px}
.relation-card .nb{font:600 12px var(--mono);color:var(--accent)}
.relation-card .ttl{font-weight:500}
.relation-card .desc{margin-top:6px;color:var(--text-secondary);font-weight:300;line-height:1.5}
```

## 강의 컨텍스트 사용 예

- 멀티 캠퍼스 워크샵 동선 (장소 A → 장소 B → 장소 C).
- 강의 콘텐츠 파이프라인의 단계 간 관계 (입구·정제·출구·큐레이션 간 흐름).
- 시리즈 강의의 모듈 간 진도 맵.
