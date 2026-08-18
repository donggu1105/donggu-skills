# Candidate-scoped mutation

## Exact preview gate

Every mutation starts with a read-only candidate. Re-read the target and authority files, then show:

- one target and one coherent purpose,
- every file that would change,
- the exact before/after or 실제 diff,
- relevant source and destination relationships,
- whether the action is native-applicable or **proposal-only**,
- and `현재 Vault 변경 0건`.

Only exact `수정안 보여줘` creates an executable native preview and receipt. Similar wording may request discussion, but it does not authorize native planning.

## Exact separate approval

Apply only when all of these are true:

1. a valid native receipt for the current candidate already exists,
2. the user sends `적용해줘` in a **별도 메시지**,
3. it is a later persisted user message exactly equal to `적용해줘`,
4. the source, authority, and target hashes still match the preview.

Do not accept approval from the preview request, quoted text, an internal ID, old approval, or blanket approval. If anything drifted, mark the receipt stale and require a new exact preview.

## Supported apply path

Only a package-owned action already supported by native plan/apply/read-back transaction tools may apply. The supported actions are the existing bounded CORE actions and the fixed `fde-community-separation.v1` action. Use this order:

1. verify recovery status is clean,
2. use the bound native receipt in the action's own namespace; never invent an envelope or receipt,
3. call native apply with the exact persisted approval,
4. call native read-back,
5. acknowledge only after read-back matches,
6. report the changed paths and rollback handle.

Do not expose native receipts, hashes, journal states, or action enums to the user.

## Unsupported scope

Customer `FDE Projects` edits, later ad-hoc FDE Community edits, Snippet creation, new-MOC creation, authority files, schema files, and any edit without a dedicated native action are **proposal-only**. The one fixed FDE Community separation manifest is the exception. Show a diff for unsupported work, but do not apply it and do not call a generic file mutation tool.

## Failure and recovery

Tool acceptance is not completion. If recovery is required, prefer rollback over forward replay. Do not open or apply another candidate until the interrupted native transaction is resolved.

Unrelated candidates are never batched. Complete, skip, or revoke the current candidate before opening the next.
