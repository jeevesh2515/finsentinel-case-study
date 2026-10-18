# Public Threat Model

This is a public-safe summary of the security thinking behind FinSentinel. It is written to show judgement, not configuration. It deliberately excludes exploit detail, private findings, and control configuration.

## Assets being protected

1. **Tenant data.** Transaction records and everything derived from them belong to exactly one tenant; leakage across tenants is the highest-severity failure.
2. **Evidence integrity.** Retrieved guidance, citations, and case evidence must be traceable to their source; a fabricated or mismatched citation corrupts the investigation record.
3. **The audit trail.** Who reviewed what, when, and with what outcome must survive attempts to quietly rewrite history.
4. **Risk-tier integrity.** The machine triage tier must be stable: nothing downstream, especially generated text, may change it.
5. **Credentials.** Authentication material must never appear in source, logs, examples, or generated output.
6. **Availability of processing.** A defective event or repeated provider failure must not be able to stall the pipeline indefinitely.

## Trust boundaries

```mermaid
flowchart TD
    subgraph External["External Untrusted Zone"]
        CLIENT["External Caller / Integration Client"]
    end

    subgraph B1["1. API Boundary"]
        CLIENT -->|Untrusted Payload| API["FastAPI Intake / Validation Engine"]
        AUTH["Server Authentication & Tenant Derivation"] --> API
    end

    subgraph B2["2. Tenant Data Isolation Boundary"]
        API -->|Scoped Application Role| DB[("PostgreSQL Multi-Tenant Store\n(Row-Level Isolation & Split Roles)")]
    end

    subgraph B34["3 & 4. Worker, Guidance & Model Boundary"]
        DB --> WORKER["Background Worker"]
        REGISTRY["Regulatory Guidance Registry\n(Treated as Data, Never Executable)"] -->|Untrusted Content| WORKER
        WORKER -->|Redacted Payload\nSpend Guard Enforced| MODEL["Provider / Mock Engine"]
    end

    subgraph B5["5. Grounding & State Primacy Boundary"]
        MODEL -->|Display Material Only| GROUND{"Grounding Verifier"}
        GROUND -->|Grounding Passed| PACK["Grounded Draft Pack"]
        GROUND -->|Weak Evidence| ABSTAIN["Explicit Abstention"]
    end

    subgraph B6["6. Human Decision Boundary"]
        PACK --> HUMAN["Named Human Reviewer"]
        ABSTAIN --> HUMAN
        HUMAN -->|Attributed Transition| AUDIT[("Append-Only Audit Trail")]
    end

    classDef default fill:#101418,stroke:#3a4750,color:#e8edf2,font-size:12px;
    classDef alert fill:#241c22,stroke:#ef4444,color:#fca5a5;
    classDef safe fill:#1d2a1f,stroke:#4ade80,color:#86efac,font-weight:bold;
    classDef boundary fill:#1b232b,stroke:#d97706,color:#f5c17a;

    class CLIENT alert;
    class HUMAN safe;
    class GROUND boundary;
```

- **Client to API**: all external input is untrusted; strict validation, authentication, authorization, rate limits.
- **API to database**: runtime uses a least-privilege role; migrations use a separate role; tenant scope is enforced at the data layer.
- **Application to external provider**: outbound content is redacted first; provider usage is disabled by default and bounded by a spend guard when enabled.
- **Retrieved text to application**: retrieved regulatory text is untrusted input and is treated as data, never instructions.
- **Generated text to control plane**: generated prose cannot mutate state, tiers, or citations.
- **System to human**: disposition and escalation are human transitions, recorded with reviewer identity.

## High-level threats and design responses

| Threat class | Public-safe design response |
|---|---|
| Spoofing identity | Credential material is never stored or logged in recoverable form; tenant identity is derived from the authenticated principal, never from client input |
| Tampering with case data | Risk tiers are immutable after scoring; review transitions follow an explicit state machine; exported records carry tamper-evidence markers |
| Repudiation of review actions | Every transition appends an audit record with reviewer identity, states, and timestamp; anonymous transitions are impossible by construction |
| Information disclosure across tenants | Tenant scope is enforced at the data layer for reads and writes; isolation failures do not reveal the existence of other tenants' records; outbound payloads are redacted before any provider call |
| Denial of service and runaway cost | Rate limiting on public entry points; bounded retries with terminal failure states; provider spend bounded by a reservation guard before any call; no unbounded result sets |
| Elevation of privilege | Read and write permissions checked per route; the review state machine is the only path between statuses; terminal states have no out-edges |
| Prompt injection via retrieved content | Deterministic tier primacy; citations must match verified sources or the request fails closed; injected instructions in retrieved text cannot become application behaviour |
| Unsupported regulatory claims | Grounding validation: a draft referencing an unknown or mismatched citation is rejected rather than shown; weak evidence produces abstention |

## Residual risks (honest list)

1. **Administrator access.** Audit records are append-only by application privilege, but a database administrator can rewrite rows. The design provides tamper-evidence, not immutability. External anchoring is undecided.
2. **Restart resilience.** Workflow resume position does not currently survive a process restart; durable processing effects are idempotent, which bounds the impact. Durable checkpointing is future work.
3. **Regulatory retrieval is demonstrative.** The recorded gates use a small stub registry rather than a complete, verified regulatory corpus; retrieved guidance is illustrative, not a legal reference.
4. **Provider spend control is single-process.** It does not survive restart or span instances. Paid provider access is disabled in the recorded configuration, so the current blast radius is zero.
5. **Local identity scope.** The recorded configuration uses a local identity model suitable for a loopback demonstration. Production identity, transport security, and internet-facing abuse controls are separate scopes with their own review.
6. **No independent security testing.** The threat model is a design audit backed by the project's own tests. There has been no external penetration test or code audit.

## Excluded from this document

- exploit techniques, attack payloads, and reproduction steps;
- private security findings and their remediation history;
- exact control values, thresholds, and configuration;
- internal service names, hosts, and infrastructure identifiers.

See [LIMITATIONS.md](LIMITATIONS.md) for product-level limits and [DISCLOSURE.md](DISCLOSURE.md) for what this repository is and is not.
