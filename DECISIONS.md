# Public decision notes

Short, public-safe records of the decisions that shaped FinSentinel. Each one states the context, the decision, the consequence, and the cost. Implementation detail, thresholds, and internal identifiers are omitted on purpose.

These are summaries, not the private architecture decision records. They exist so a reviewer can see how the system was reasoned about, not only what it does.

---

## D-001 — Tenant identity comes from the principal, never the request

**Context.** Multi-tenant systems often accept a tenant id in a header or body. That is convenient for demos and wrong for regulated data.

**Decision.** Resolve the tenant from the authenticated credential and membership. Enforce scope in the database with row-level security and a split migration/runtime role. A client-supplied tenant value is never authorization.

**Consequence.** Cross-tenant reads return not-found rather than a permission error, so the system does not confirm that another tenant's record exists. Negative tests exercise this path.

**Cost.** Every query must run inside a tenant context, including background work. Development is slower than a single shared schema, and the migrator role is a separate operational concern.

---

## D-002 — A triage tier is a review priority, not a fraud probability

**Context.** Anomaly scores are easy to present as risk. Buyers and reviewers then treat them as evidence of wrongdoing, which the model cannot support.

**Decision.** Separate the deterministic tier from generated prose and from any disposition. The tier orders review work. It never changes after scoring, and no downstream component can raise or lower it.

**Consequence.** The model can be useful without being sold as a detector. The human decision stays the only disposition. Wording rules ban detection-accuracy claims until an authorised labelled evaluation exists.

**Cost.** The product is less impressive in a demo. It cannot promise prioritisation accuracy, and it must explain its limits in every buyer conversation.

---

## D-003 — Citations resolve to synthetic stubs, and weak evidence abstains

**Context.** Regulatory retrieval looks authoritative even when it is a small local corpus. Quoting a real-sounding rule without provenance is worse than saying nothing.

**Decision.** Use a small versioned stub registry with content hashes. Require a draft citation to match a known stub. If retrieval is weak, return insufficient evidence rather than a padded answer. Call the public metric **citation hash verification**, not grounding.

**Consequence.** The citation path demonstrates mechanics: source id, hash, abstention, and a clear "not regulator text" label. It does not claim legal applicability or coverage.

**Cost.** The system abstains more often than a buyer might like, and the registry cannot be used as a policy reference until an authorised source catalogue, licence and review process exist.

---

## D-004 — The human gate is a code boundary, not a policy statement

**Context.** "Human in the loop" is often a label on a UI. The real question is whether the system has any path to act without a person.

**Decision.** High and critical cases require a named reviewer transition. Only the assignee can close a case. Notes are required. Terminal states have no outgoing transitions. Every transition writes an attributed audit row. The system has no code path that files a report, moves money, or contacts a regulator.

**Consequence.** The workflow can be described as assistive without qualification. Reviewer identity and timing survive in the audit trail.

**Cost.** The product cannot offer fully automated triage, and an absent reviewer is a genuine bottleneck. The audit trail is append-only by application privilege, not administrator-proof.

---

## D-005 — Mock provider by default, paid calls off

**Context.** A demo that depends on a paid external model is hard to reproduce, expensive to run, and risky with synthetic data that still resembles production.

**Decision.** Ship with a mock provider and paid access disabled. Any external call requires an explicit configuration change, a redaction step, and a spend guard. Record every evaluation run with the provider mode and the spend.

**Consequence.** Evaluations are reproducible at zero provider cost, and the safety posture is the default rather than a setting someone must remember.

**Cost.** Model quality under a real provider has never been measured. The spend guard is single-process and does not survive a restart.

---

## D-006 — Evidence tiers before claims

**Context.** Synthetic results are useful for engineering and worthless for detection claims. Teams blur that line under commercial pressure.

**Decision.** Pre-register the model evaluation protocol before looking at labelled results: evidence tiers, data authorisation, temporal splits, typology-level reporting, false-positive burden, calibration, drift, and threshold governance. All current model evidence is synthetic and non-transferable.

**Consequence.** The product is positioned as a triage and investigation-assistance layer. Detection claims are blocked until the protocol has been executed on authorised data and reviewed.

**Cost.** The strongest marketing line is unavailable. Every public claim needs a human read-through, because a pattern list cannot judge a bare capability verb.

---

## D-007 — Bound the retrieval candidate pool

**Context.** Similar-case retrieval originally computed pool statistics inside the candidate loop. Tests passed because the result was correct; latency grew with tenant history.

**Decision.** Keep the ranking correct, hoist the statistics, and bound the candidate set with indexed pre-filters before standardisation. Fail the benchmark when pack-assembly p95 reaches the threshold.

**Consequence.** Pack assembly became effectively independent of tenant history above the cap, and the performance claim is guarded by a test rather than a slide.

**Cost.** The bounded pool can miss a relevant prior case outside the pre-filter. That trade-off is documented, not hidden.

---

## D-008 — The public showcase may read a local API, but must degrade to synthetic

**Context.** A fully static demo is safe but cannot show live behaviour. A live demo is convincing but risks exposing a token or a backend.

**Decision.** Keep the public deployment synthetic by default. An optional server-only bridge can read a local API when a token is configured. The token never reaches the browser, the upstream call times out quickly, and every failure returns the synthetic fixture with an explicit reason.

**Consequence.** The demo can show real responses without making the public edge a proxy for private data. Route tests pin the no-token, timeout and non-leak behaviour.

**Cost.** The live path is not exercised in public. The bridge is an operator feature, not a product feature, and must be reviewed before any customer-facing use.

---

## D-009 — Customer risk profiles provide context, not automated scoring overrides

**Context.** Transaction anomaly scores indicate statistical deviation, not illegality. Analysts evaluate suspicious activity against the customer's known KYC/CDD baseline (declared turnover, expected corridors, risk rating).

**Decision.** Store customer KYC/CDD baselines in a tenant-isolated entity with row-level security. Compute deterministic variance metrics (turnover multiples, corridor mismatches, stale CDD) and surface them as visual context in the triage queue and investigation pack. Profile variance never silently overrides the model's anomaly score.

**Consequence.** Analysts see vital customer background directly within FinSentinel, reducing context switching without blurring the line between statistical anomaly and compliance context.

**Cost.** Customer profiles must be kept in sync by the tenant; out-of-date baselines create misleading variance indicators.

---

## D-010 — External alerts open cases, but the tier stays the model's

**Context.** Regulated institutions already run transaction monitoring systems with existing alert generation. Forcing them to replace existing detectors before using FinSentinel prevents adoption.

**Decision.** Ingest external alerts idempotently on `(tenant_id, source_system, external_alert_id)` and link them to primary trigger transactions. An alert opens a case at any priority, but the case tier strictly reflects FinSentinel's deterministic model tier. The external severity is preserved solely as external context.

**Consequence.** FinSentinel operates as an investigation-acceleration layer over existing detection infrastructure without compromising deterministic scoring invariants or triage predictability.

**Cost.** Trigger transactions must be ingested before or alongside alerts, requiring coordination between customer telemetry feeds.
