# Bounded maintenance

Maintenance protects retrieval quality; it is not a daily productivity ritual.

## Default policy

- **매일 전체 Vault를 스캔하지 않는다.**
- **정상 결과는 알리지 않는다.**
- Notify only when there is an actionable issue or the check itself fails.
- Never mutate the Vault during a check.
- Never move or delete Inbox notes because of age or quantity.

## Publish event

A 발행 이벤트 reads only the approved source post, the CORE index needed for relationship search, the most relevant CORE excerpts, and relevant MOC metadata. It proposes at most 최대 3개 reusable candidates and changes nothing. If no candidate exists, record success internally and send no Discord message.

Event processing must not invoke a general changed-note sweep, full-Vault audit, or healthy-state report.

## Weekly bounded check

Run only when explicitly requested or when a separately approved schedule exists. Scope it to Personal Branding and return at most 최대 3개 important issues. Prefer broken retrieval paths, source-trace loss, and high-confidence schema conflicts over cosmetic cleanup.

## Duplicate review

Duplicate search happens before every new CORE proposal. A broader semantic duplicate review is monthly or on demand, not daily. Start with a named folder, MOC, or theme; expand only when evidence requires it.

For each possible duplicate, explain whether the relationship is identical, overlapping, complementary, or conflicting. Do not auto-merge. Show one merge or link candidate with an actual diff and use the mutation gate.

## Failure reporting

On failure, report the failed boundary, whether any write occurred, and the retry or rollback action. Do not print credentials, private excerpts, internal member identifiers, or transaction payloads.
