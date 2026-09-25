# ADR 0002 — Milestone criteria reviewed, rewritten or reopened

- **Status:** accepted (2026-09-25)
- **Context:** PLAN.md phase 2; AUDIT.md §10 (milestones J1–J9); reports in
  [`docs/revues/`](../revues/index.md).

## Context

Milestones 1 to 9 were declared done against criteria written before the phase 1
fixes. Phase 1 showed that some checks could not fail (a load-bearing predicate that
compared a wall with itself, a gradient checkpoint measured against the oracle the
network was trained on). A criterion that cannot fail proves nothing; a criterion that
was met by an easier test than the one written is not met.

## Decision

Each milestone is replayed against its criterion **as written**. When the criterion is
kept, the report says so. When it is changed, the change is listed here, with its
reason; `MILESTONE-N.md` keeps its original text and points to this ADR.

| Milestone | Change | Reason |
|---|---|---|
| J1 | Criterion extended: the round trip is tested on outputs of `legalize` (walls, bound with regime), and the JSON schema is published and tested. **Schema v2 (batch E5) serializes the `Contexte`.** | A certificate file does not carry the minimum areas and structure it was checked against, so nobody can re-check it from the file ([j1](../revues/j1.md)). |
| J2 | Criterion replayed as written (arbitrary plans and contexts) and with walls, minimum areas and one fault; read as "every returned plan is valid and every refusal is typed". **"Enough for a first publishable paper" withdrawn.** | The closing test drew already-valid plans; as written, 371 of 500 inputs are refused (none certified wrongly). The 3-generator baseline was two hand-made plans ([j2](../revues/j2.md)). |

## Consequences

- A milestone reopened here is not "done" in the README or the documentation until its
  new criterion is met.
- Every figure quoted from a reopened milestone carries the date and revision it was
  measured at.
