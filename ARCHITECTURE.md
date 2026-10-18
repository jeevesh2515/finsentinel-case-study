# Public Architecture

This document explains how FinSentinel is designed at a level that is safe for a commercial product to disclose. It is intentionally simplified: it shows components, responsibilities, data flow, and trust boundaries, not the implementation.

![FinSentinel Public Architecture Diagram](assets/architecture-public.svg)

## System architecture and delivery

FinSentinel couples a local-first enterprise backend engine with a client-side public showcase deployed to Vercel's edge network via automated CI/CD:

```mermaid
flowchart LR
    subgraph Enterprise["Enterprise Core (Docker / Local)"]
        direction TB
        API["FastAPI Engine & PG16 RLS"]
        WORKER["Outbox Worker & ML Scorer"]
        DASH["Analyst Review Dashboard"]
        API --> WORKER --> DASH
    end

    subgraph Delivery["Automated CI/CD (GitHub Actions)"]
        direction TB
        CI["CI: check.yml (288 tests)"]
        CD["CD: deploy.yml (Vercel CLI)"]
        CI --> CD
    end

    subgraph Edge["Public Showcase (Vercel)"]
        direction TB
        WEB["Next.js 15 Operations Cockpit"]
        SIM["Interactive AML Sandbox"]
        WEB --> SIM
    end

    Delivery -->|Auto-deploys| Edge

    classDef box fill:#101418,stroke:#3a4750,color:#e8edf2,font-size:11px;
    class API,WORKER,DASH,CI,CD,WEB,SIM box;
```

## Component responsibilities

| Component | Responsibility | Public-safe note |
|---|---|---|
| Intake API | Accepts versioned transaction events, enforces strict validation, returns explicit replay/conflict semantics | Contract shape and error policy are described; exact schemas are not published |
| Identity and tenant checks | Resolves the authenticated principal, membership, and permissions; derives tenant identity server-side | Client-supplied tenant headers are never trusted |
| Tenant-scoped storage | Durable system of record for events, processing state, scores, reviews, and audit | Row-level security and split database roles are used; configuration is not published |
| Feature and triage stage | Builds history-based features and produces a triage priority from a versioned scoring artifact | Triage priority is not a fraud probability; thresholds are not published |
| Evidence and retrieval stage | Finds related historical patterns and retrieves cited guidance chunks with provenance | Weak evidence produces abstention, never a padded citation |
| Draft assembly | Produces review-ready investigation material constrained to supplied evidence | Generated text cannot change a risk tier or invent a citation |
| Human review | Reviewer claims a case and records an explicit transition with identity and notes | No autonomous final action exists anywhere in the pipeline |
| Audit and export | Append-only audit trail; controlled investigation-pack export (JSON and print HTML) | Tamper-evidence for reviewers, not administrator-proof immutability |
| Automated CI/CD | Runs unit, integration, and typecheck gates on commit; deploys public showcase on main | GitHub Actions executes check.yml and deploy.yml with Vercel CLI |
| Public Edge Showcase | Client-side sandbox and operations cockpit hosted at finsentinel-chi.vercel.app | Air-gapped from backend core; executes purely in browser with mock synthetic data |

## Data flow

```mermaid
flowchart LR
    A["1. Intake<br/><sub>Strict validation</sub>"] --> B["2. Storage<br/><sub>Tenant-scoped RLS</sub>"]
    B --> C["3. Triage<br/><sub>Feature & anomaly signal</sub>"]
    C --> D["4. Grounding<br/><sub>Citation check or abstain</sub>"]
    D --> E["5. Human Review<br/><sub>Attributed audit trail</sub>"]

    classDef stage fill:#101418,stroke:#3a4750,color:#e8edf2,font-size:11px;
    class A,B,C,D,E stage;
```

```text
Synthetic transaction input
    -> validation and identity/tenant checks
    -> tenant-scoped persistence (transaction + audit + processing queue entry, atomically)
    -> asynchronous processing: features -> triage signal
    -> similar-case retrieval and cited regulatory guidance
    -> cited draft investigation material
    -> named human review (approve / dismiss / escalate / draft)
    -> audit trail and controlled export
```

Design properties worth noting:

- **Atomic intake.** A new event, its audit record, and its processing-queue entry are written in one transaction. Identical replay and conflicting replay are distinct, explicit outcomes.
- **Asynchronous processing with bounded retries.** Processing failures retry a bounded number of times and then stop in a terminal state; failed items are replayed deliberately, not silently.
- **Deterministic ordering.** A triage tier is fixed after scoring, and no later step (including generated text) can modify it.
- **Abstention as a first-class outcome.** If retrieval is weak or citations cannot be grounded, the pipeline reports insufficient evidence rather than fabricating support.

Mechanisms behind these properties are described at outcome level on purpose; implementation detail is withheld.

## Trust boundaries

```mermaid
flowchart LR
    subgraph Ingress["Ingress & Storage"]
        direction TB
        B1["Boundary 1: API Intake<br/><sub>Untrusted inputs, rate limits</sub>"]
        B2["Boundary 2: Tenant Database<br/><sub>Least-privilege role, tenant isolation</sub>"]
        B1 --> B2
    end

    subgraph Processing["Processing & Grounding"]
        direction TB
        B3["Boundary 3 & 4: Model & Guidance<br/><sub>Redacted payloads, spend guard</sub>"]
        B5["Boundary 5: Control Plane<br/><sub>Display only, grounding check</sub>"]
        B3 --> B5
    end

    subgraph Governance["Human Review & Audit"]
        direction TB
        B6["Boundary 6: Human Authority<br/><sub>Named transitions, no auto-filing</sub>"]
        AUDIT["Audit Trail<br/><sub>Append-only tamper evidence</sub>"]
        B6 --> AUDIT
    end

    Ingress --> Processing --> Governance

    classDef box fill:#101418,stroke:#3a4750,color:#e8edf2,font-size:11px;
    class B1,B2,B3,B5,B6,AUDIT box;
```

1. **Client to API.** Everything arriving from outside is untrusted input: strict validation, size limits, rate limiting, and permission checks apply. Tenant identity comes from the authenticated principal, never the request body or headers.
2. **API to database.** The runtime uses a least-privilege application role; migrations run under a separate role. Reads and writes are scoped to the authenticated tenant at the database layer, with negative tests for cross-tenant access.
3. **Application to provider.** Outbound payloads are redacted before any external model call, and provider use is disabled by default in the recorded configuration. A spend guard bounds any future provider activity.
4. **Retrieved text to application.** Retrieved regulatory text is treated as untrusted data. Injected instructions inside retrieved content cannot become application behaviour; tests assert this.
5. **Generated text to control plane.** Generated prose is display material with a fixed schema. It cannot alter tiers, invent citations, or trigger external action.
6. **System to human.** The review boundary is explicit: a named reviewer performs the state transition. The system has no code path that files, escalates externally, or contacts a regulator.
7. **Public edge showcase to enterprise core.** The public showcase is hosted on Vercel's edge network and runs entirely within the visitor's browser with synthetic data. It has no network route, API keys, or database access into the enterprise core, maintaining an air gap between public demonstration and private systems.

## Human-review boundary

![FinSentinel Human Review Workflow Lifecycle](assets/workflow-public.svg)

```text
triage -> pending review -> in review -> cleared | escalated | drafted-for-review
```

- High and high-critical triage outcomes require human review.
- Every transition records the reviewer, the previous and next state, and the time.
- Terminal states have no outgoing transitions; reopening is a deliberate design decision, not an accident.
- Audit history is append-only by database privilege, and the documentation states plainly that a database administrator can still rewrite rows: this is tamper-evidence, not immutability.

## Deliberately omitted

This public architecture intentionally excludes:

- source code for any product workflow;
- prompts, agent instructions, and tool schemas;
- database schemas, exact validation rules, and configuration values;
- scoring features, thresholds, calibration data, and model artifacts;
- retrieval implementation, ranking logic, and evidence-selection heuristics;
- infrastructure specifics: hosts, networks, account identifiers, bucket or queue names;
- security control configuration beyond what is necessary to explain the design;
- evaluation fixtures and internal evidence files.

The omission list is part of the design: the case study demonstrates engineering judgement, while the implementation recipe stays private.
