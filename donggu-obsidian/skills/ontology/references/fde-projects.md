# FDE Projects boundary

FDE Projects records customer work and reusable delivery learning without turning the Vault into a second project wiki.

## Source of truth

The Ontology Lens wiki is authoritative for project facts, current requirements, and shared implementation detail. In the Vault, propose only:

- a 출처 포인터 (source pointer),
- the user's judgment,
- a cross-project pattern,
- a tested playbook,
- or a decision that needs personal recall.

Do not copy source pages, meeting transcripts, customer datasets, or long implementation descriptions into the Vault.

## Retrieval

Read the nearest project `AGENTS.md` or guide first. When a request needs current facts, follow the source pointer and inspect the external authority when available. Session history is secondary context, not proof of current state.

## Candidate quality

A proposed FDE note must answer:

1. What external source supports it?
2. What judgment or reusable pattern is being added?
3. How is it different from the source itself?
4. Does it expose customer names, contacts, credentials, private code names, or unnecessary raw text?

If the value is only a restatement, propose a link rather than a new note. Keep Personal Branding and FDE proposals separate even when they share a theme.

## Mutation support

FDE mutation is **proposal-only**. The current native runtime does not authorize FDE paths. Show a candidate and actual diff, but never apply it through a generic file mutation tool. A dedicated native authority path and behavioral tests are required before FDE writes can be enabled.
