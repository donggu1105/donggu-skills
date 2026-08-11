# Writing Social Content Persona Selection Design

**Date:** 2026-08-11
**Status:** Approved by user direction

## Goal

Make `writing-social-content` choose one public author persona before drafting while keeping every supported channel available to both personas.

The two personas are:

1. `FDE` — writes from customer and organizational fieldwork: problem discovery, AX delivery, adoption, outcomes, and durable operation.
2. `1인 빌더` — writes from building and validating one's own product, workflow, or business hypothesis.

## Positioning Boundaries

- `DA` remains an internal Wishket role and is not a public persona option in this skill.
- `AX Engineer` is a shared expertise/category descriptor, not a third persona.
- `AI Product Engineering`, field-first practice, and evidence-first validation are shared capabilities.
- `솔로프리뉴어`, `1인 개발자`, and `1인 창업가` may appear as contextual labels, but the canonical second persona is `1인 빌더`.
- A draft has exactly one primary persona. Material may connect the two, but it must still choose the perspective that owns the claim.

## Interaction Design

Persona resolution happens before source locking.

1. If the user explicitly names `FDE` or `1인 빌더`, use it without asking again.
2. If the brief clearly establishes one persona, infer it and state the choice briefly when useful.
3. If the choice would materially change the article and remains ambiguous, ask one concise question with the two options.
4. Do not offer `DA`, `AX Engineer`, or a hybrid as additional persona options.
5. Resolve the primary audience independently. Channels do not own personas or audiences.

The selection affects the lens, claims, proof, and boundary checks. It does not mechanically change channel availability or invent facts.

## Persona Reference

Add a bundled `references/personas.md` so the skill stays portable and does not depend on the Obsidian vault.

Each persona definition contains:

- canonical name and aliases;
- central question;
- valid source material and proof;
- characteristic point of view;
- likely audiences without binding them to channels;
- claims and identity drift to avoid;
- a rule for cross-persona material.

The reference defines content perspective, not a separate tone. `references/common-voice.md` remains the shared voice authority, and channel references remain the format authority.

## Workflow Changes

The skill loads `references/personas.md` at startup, then follows this order:

1. resolve persona;
2. resolve target channel and `origin` or `adapt`;
3. resolve the primary audience when material;
4. load common voice and requested channel rules;
5. build the evidence ledger;
6. lock one channel-native thesis from the selected persona's perspective;
7. load channel examples;
8. draft and validate.

The evidence ledger remains authoritative. Persona selection may frame supported facts but may not add experiences, customer details, outcomes, or business results.

## Validation Changes

Add persona checks to the final review:

- exactly one primary persona is resolved;
- the thesis fits that persona's central question;
- audience and channel were not used as substitutes for persona;
- no internal Wishket `DA` identity is exposed as a public persona;
- FDE content does not fabricate field experience or confidential company/customer detail;
- 1인 빌더 content does not imply launches, revenue, customers, or business success without evidence;
- shared AX/product-engineering language does not create a third persona.

## Files

- Modify `donggu-sns/skills/writing-social-content/SKILL.md`.
- Add `donggu-sns/skills/writing-social-content/references/personas.md`.
- Update plugin/marketplace version metadata only if required for the installed plugin to receive the change.
- Add or update focused validation fixtures/tests using existing repository conventions.

## Non-goals

- Do not map a persona exclusively to LinkedIn, Blog, Threads, or Maily.
- Do not change channel voice, length, or output contracts.
- Do not read the user's Obsidian vault automatically.
- Do not store or publish content.
- Do not add `DA` to public personal-branding choices.
- Do not restore the removed vault-wide `persona`, `audience`, `arc`, or `track` schema in this change.

## Acceptance Criteria

1. A direct request such as “FDE 관점으로 LinkedIn 글” proceeds without a persona question.
2. A direct request such as “1인 빌더 관점으로 Blog 글” proceeds without a persona question.
3. An ambiguous writing request asks only `FDE` versus `1인 빌더` when the choice changes the result.
4. Both personas can target all four supported channels.
5. Audience is resolved per draft rather than hard-coded by persona or channel.
6. Cross-persona material selects one primary lens instead of emitting a blended identity.
7. Existing evidence, safety, portability, and channel-reference contracts continue to pass.
