# layout-recipes — 카드 골격 5종

각 카드는 아래 골격 하나를 쓴다. 매 카드를 같은 "제목+카드" 반복으로 만들지 말 것. 클래스는 card-template.html에 정의됨. 토큰(색·폰트·radius)은 DESIGN.md에서 온다 — 레시피는 **구조만** 규정한다.

## R1 · Cover (표지)
훅 한 방. 카테고리 라벨(라틴 UPPERCASE 허용) → 메인 타이틀(2~4줄, 포인트색 강조 1곳) → 한 줄 서브 → 푸터(핸들·1/N).
```html
<section class="card" id="card-1">
  <div class="card-pad stack between">
    <div class="stack g-sm">
      <span class="eyebrow">CATEGORY</span>
      <h1 class="t-display">메인 타이틀<br><em>포인트</em> 강조</h1>
      <p class="t-sub">한 줄 서브헤드</p>
    </div>
    <div class="foot"><span>@handle</span><span>1 / N</span></div>
  </div>
</section>
```

## R2 · Numbered (넘버링 인사이트)
"N가지" 콘텐츠. 큰 숫자 + 제목 + 한두 줄. 1카드에 1~3항목.
구조: eyebrow → 항목들(`.num-row`: 번호 / 제목+설명) → foot.

## R3 · Rows (비교·경고·단계)
가로 행 반복(벽 3개, 트랩, 단계 등). 왼쪽 라벨/번호 + 오른쪽 결과. 행 사이 헤어라인.
구조: 제목 → `.row`×3 (좌 마커 / 우 텍스트) + `<hr class="hairline">` → foot.

## R4 · Quote (인용·결론)
핵심 문장 한 방. 큰 인용 + 출처/맥락 한 줄 + 헤어라인. 여백 의도적 — 단 출처·메타·헤어라인 3개 앵커는 필수(빈 공간이 "내용 누락"으로 안 보이게).
구조: eyebrow → `.t-quote` 큰 문장 → hairline → meta → foot.

## R5 · CTA (마무리)
행동 유도. 결론 문장 → CTA 블록(프로필 링크·블로그·앱) → 푸터. 포인트색을 CTA 블록에 (단 DESIGN.md가 포인트색을 액션에 허용할 때만; BMW류는 아웃라인 버튼).
구조: 제목 → `.cta-block`(라벨+설명) → foot(N/N).

---
**배정 가이드**: 표지=R1, "N가지"=R2, "세 가지 벽/문제"=R3, 결론 한 문장=R4, 마지막=R5. 6장이면 R1·R2·R2·R3·R4·R5 식으로 섞는다.
