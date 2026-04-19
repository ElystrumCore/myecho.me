# EXCHANGE.md — Echo Mailbox + Ghost Writer (Phase 0.5)

## Context

This spec extends the Phase 0 Echo build (see `CLAUDE.md`). Phase 0 delivers ingest, profile construction (StyleFingerprint, BeliefGraph, KnowledgeMap), and a public journal surface. This phase adds the correspondence layer — how anyone communicates with the holder of an Echo account — and reserves the namespace for Echo-to-Echo agent correspondence in Phase 2.

**Branding:** The correspondence surface is called **The Exchange**. The AI-composition feature inside it is called **Ghost Writer**.

**Core thesis:** Echo is not real-time chat. The Exchange is the opposite of a DM — a correspondence surface with postal cadence, dignified attribution, and a voice that answers when the holder is quiet. Chrome leans on ICQ-era and analog-mail references, but the primitives are Echo-native.

---

## Primitives

Four correspondence primitives. Each has a distinct mental model — keep them distinct in data, UI, and naming.

| Primitive      | Binds to         | Threaded?       | Default visibility      | Ghost-eligible? |
|----------------|------------------|-----------------|-------------------------|-----------------|
| **Letter**     | Holder's mailbox | No (one-shot)   | Private to holder       | Yes             |
| **Response**   | Journal entry    | Yes (per entry) | Holder + entry readers  | Yes             |
| **Guestbook**  | Echo profile     | No (flat list)  | Public on profile       | No              |
| **FutureLetter** | Holder's mailbox | No             | Private until delivery  | Yes (on delivery) |

First-contact messages always route as Letters. Responses are reserved for correspondents who have already exchanged at least one Letter with the holder and who have been granted read access to the entry. Guestbook is open, short, unthreaded — optimize it for "signatures and hellos," not conversation.

---

## Ghost Writer

Pro-gated. Three modes:

- **Off** — all incoming correspondence routes to holder personally. No AI composition.
- **Draft** — Ghost composes a reply using StyleFingerprint + BeliefGraph + thread context. Holder reviews, edits, approves, or discards. Nothing leaves the system without holder action.
- **Auto** — Ghost composes and sends without holder intervention. Requires eligibility gate (below).

**Auto eligibility (locked in Phase 0.5):**
- Holder has >= 30 Ghost drafts approved
- Send-as-written rate >= 90% across those 30
- Correspondent must be established (>= 1 prior Letter from this correspondent already read by holder)
- Holder has explicitly opted into Auto for *this correspondent* or for a correspondent tag

Do not enable Auto on the first release. Ship Off and Draft first; Auto ships once telemetry confirms the eligibility thresholds are meaningful.

**Ghost is never enabled for first-contact Letters, regardless of holder settings.** First contacts always route personally.

---

## Data Model

All models live in the existing Echo FastAPI service (`:8004`). Persist in Postgres; mirror letter bodies and Ghost drafts into Cyclone for retrieval by the voice pipeline.

### EchoAddress

Canonical identity for any participant in the Exchange. Formed at account creation.

```
echo_address: str  # "echo://{uin}@myecho.me"
uin: int           # monotonic, assigned at signup, immutable
pubkey: bytes      # ed25519, generated at signup — unused in Phase 0.5 but reserved
```

Every Letter, Response, FutureLetter, and GuestbookEntry references sender and recipient by `echo_address`, not by email or user_id. Email is a **transport**, not an identity. This is the single most important data-model decision for Phase 2 compatibility.

### Letter

```
id: uuid
from_address: echo_address           # sender (may be external — see Transport)
to_address: echo_address             # recipient (holder's Echo)
subject: str | None
body: markdown
ghost_metadata: GhostEnvelope | None # present iff Ghost composed or drafted
thread_root_id: uuid | None          # null for top-level letters
in_reply_to_id: uuid | None
transport: enum(web, email, a2a)     # how it arrived / will leave
sender_mood: str | None              # mood-flower snapshot at send time
created_at: timestamp
delivered_at: timestamp | None
read_at: timestamp | None            # holder-controlled; read-receipts off by default
```

### GhostEnvelope

Extensible metadata block. Versioned from day one so Phase 2 A2A can extend without migrations.

```
schema_version: str                  # "0.5"
composed_by: enum(holder, ghost)
mode: enum(draft_approved, auto_sent)
style_fingerprint_version: str
belief_graph_refs: list[str]         # Cyclone artifact IDs used during composition
holder_approved_at: timestamp | None
signature: bytes | None              # reserved for Phase 2 A2A signing
```

### GhostDraft

```
id: uuid
incoming_letter_id: uuid
draft_body: markdown
generated_envelope: GhostEnvelope
status: enum(pending, approved, edited_and_sent, rejected, expired)
holder_decision_at: timestamp | None
edit_diff: json | None               # capture holder edits for StyleFingerprint feedback
```

Every holder decision on a GhostDraft is a training signal. Route decisions back into the StyleFingerprint pipeline — this is how the voice improves.

### Response

```
id: uuid
entry_id: uuid                       # journal entry this responds to
from_address: echo_address
body: markdown
ghost_metadata: GhostEnvelope | None
parent_response_id: uuid | None
created_at: timestamp
```

### GuestbookEntry

```
id: uuid
echo_address: echo_address           # whose guestbook
from_address: echo_address
body: str                            # enforce short limit — e.g., 280 chars
from_mood: str | None
created_at: timestamp
```

No Ghost on guestbook. Keep it human.

### FutureLetter

```
id: uuid
from_address: echo_address
to_address: echo_address
body: markdown
ghost_metadata: GhostEnvelope | None  # only populated at delivery if Ghost-composed at send
deliver_at: timestamp | None
deliver_condition: str | None         # free-form for Phase 0.5 (e.g., "on 10th entry anniversary")
delivered_at: timestamp | None
created_at: timestamp
```

---

## API Surface

All routes under `/exchange`. Authenticate holder by session; authenticate correspondents by Echo address + transport-specific verification (email magic link in Phase 0.5; signed A2A envelope in Phase 2).

**Letters**
- `POST /exchange/letters` — compose and send
- `GET /exchange/letters` — holder's mailbox (filters: unread, from, ghost_status)
- `GET /exchange/letters/{id}` — single letter
- `POST /exchange/letters/{id}/read` — explicit mark-read (read receipts off by default)

**Ghost Drafts**
- `GET /exchange/ghost/drafts` — pending drafts for holder
- `POST /exchange/ghost/drafts/{id}/approve` — send as-is
- `POST /exchange/ghost/drafts/{id}/edit-and-send` — body + edit_diff
- `POST /exchange/ghost/drafts/{id}/reject` — discard; feedback signal

**Ghost Settings** (Pro-gated)
- `GET /exchange/ghost/settings`
- `PUT /exchange/ghost/settings` — mode (off/draft/auto), per-correspondent overrides

**Responses**
- `POST /exchange/entries/{entry_id}/responses`
- `GET /exchange/entries/{entry_id}/responses`

**Guestbook**
- `POST /exchange/guestbook/{uin}`
- `GET /exchange/guestbook/{uin}` — public

**Future Letters**
- `POST /exchange/future`
- `GET /exchange/future` — scheduled items (holder's view of incoming+outgoing)

**Capabilities (A2A seam — stub in Phase 0.5)**
- `GET /echo/{uin}/capabilities` — returns `{accept_ghost, accept_a2a, quiet_mode, require_human_review}`; not consumed by anyone yet, but exposed.

---

## BridgeDeck Workflow

Wire through the existing `WorkflowCoordinator`. Follows the same pattern as the ContentScout ingestion workflow.

**Workflow: `IncomingLetterPipeline`**

```
LetterReceiver
    -> CorrespondentClassifier       # first-contact? established? tagged?
    -> GhostEligibilityGate          # mode, correspondent rules, eligibility thresholds
    -> [branch]
        |-- PersonalOnlyRouter       # deliver to mailbox, notify holder
        |-- GhostDraftComposer       # generate draft, persist, notify holder
        |-- GhostAutoComposer        # generate, sign envelope, deliver, notify
    -> CyclonePublisher              # checkpoint letter + draft + envelope
    -> HolderNotifier                # notify on chosen-circle letters
```

Fan-out semantics: CyclonePublisher and HolderNotifier run in parallel after the branch resolves. Partial-failure policy: notification failure must not block delivery; Cyclone failure must not block holder visibility in the mailbox (retry async).

**Workflow: `FutureLetterDispatcher`**

Scheduled job. On trigger (time or condition), runs through the standard `IncomingLetterPipeline` with `transport=future` origin flag.

---

## Cyclone Integration

Every Letter body, Response, and approved Ghost draft is indexed into Cyclone on send/approve. This is what makes the voice engine improve over time and what lets the holder's future journal entries reference correspondence naturally ("someone asked me about X, I've been thinking about that").

Namespace pattern: `echo/{uin}/exchange/{primitive}/{id}`.

Feedback signals (GhostDraft approvals, edits, rejections) are written as Cyclone annotations on the draft artifact. The StyleFingerprint pipeline consumes these on its next refresh cycle.

---

## Tier Gating

Enforce at the API layer. Single feature flag source — a `user.tier` column with `free | pro`. Ghost-related endpoints return `402 Payment Required` with a structured body (`{feature: "ghost_writer", upgrade_url}`) when called by a free user.

**Free:**
- Letters (send, receive, read)
- Responses (send, receive)
- Guestbook (sign, read)
- Future Letters (limited — e.g., 5 outstanding)

**Pro:**
- All of the above, unlimited Future Letters
- Ghost Writer (Off / Draft / Auto with eligibility)
- Higher StyleFingerprint resolution
- Longer Cyclone memory horizon

---

## Attribution & Consent

Three surfaces, non-negotiable.

**Correspondent-facing attribution (in-message):**
Every Ghost-involved Letter or Response carries a small marker next to the mood flower.
- No quill -> written personally by holder
- Outline quill -> drafted by Ghost, approved by holder
- Filled quill -> composed and sent by Ghost (Auto)

Marker links to a short public explainer page at `/about/ghost-writer`. Tone: dignified, not apologetic.

**Privacy policy (legal surface):**
- Ghost Writer composes responses using holder-provided data and the content of incoming correspondence.
- Correspondents' letter contents are processed by an LLM as part of Ghost composition.
- Retention: letter content stored indefinitely for Pro; exportable and deletable.
- On Pro downgrade: Ghost composition halts immediately; existing drafts expire; letter history remains accessible to holder.

**Holder-facing consent (onboarding):**
- First-time Ghost enable: one-screen explainer (what Ghost does, what correspondents see, attribution examples, checkbox).
- First-time Auto enable: second consent screen with a clearer risk frame ("Ghost will send letters as you, without review. Correspondents will see the filled-quill marker."). Checkbox + cooldown (24h) before Auto actually activates on any correspondent.

---

## A2A Protocol Seams (Phase 2 preparation)

Do not build Phase 2. Do reserve namespace so the Phase 2 evolution is additive rather than a rewrite.

**Must be true at end of Phase 0.5:**

1. **All correspondence is addressed by `echo_address`.** Email addresses, where present, live in a separate `transport` column. Never the primary key.
2. **`GhostEnvelope` is versioned and extensible.** Unknown fields on read must be preserved, not dropped.
3. **Ed25519 keypair is generated at account creation.** Store pubkey, store privkey encrypted with server-side KEK. Do not sign anything yet; the capability to sign must exist.
4. **Transport is an adapter pattern**, not inlined. Implement `WebTransport` and `EmailTransport` as sibling classes behind a common `LetterTransport` interface. `A2ATransport` is a Phase 2 sibling — its absence now should be obvious at the interface boundary, not a refactor.
5. **`/echo/{uin}/capabilities` is live and stubbed.** Returns real data about the holder's settings. Unused in Phase 0.5; consumed by Phase 2 peers.

**Explicit out-of-scope for Phase 0.5:**
- Actual signing of outgoing envelopes
- Verification of inbound signatures
- Echo-to-Echo transport
- Capabilities-based negotiation between Ghosts
- Any protocol docs published externally

---

## Acceptance Criteria

- Holder can receive and read Letters from external senders via web and email transports.
- Holder can send Letters to any `echo_address`; email transport resolves to the holder's confirmed email.
- Responses can be posted to any entry the correspondent has read access to.
- Guestbook is public, short, unthreaded, non-Ghost.
- FutureLetters schedule and deliver on time; "on condition" entries are stored and surface in a scheduled-items view (condition evaluation out of scope).
- Pro user can toggle Ghost mode (Off / Draft). Auto mode UI exists but is gated behind the eligibility threshold and the cooldown-protected consent flow.
- Ghost Draft approvals, edits, and rejections are persisted as StyleFingerprint feedback in Cyclone.
- Every Letter and Response carries the correct attribution marker in the default UI theme.
- Every Echo account has a valid ed25519 keypair persisted.
- `/echo/{uin}/capabilities` returns live data.
- Free users calling Ghost endpoints get `402` with a structured upgrade payload.
- No code path assumes email is a primary identifier.

---

## Out of Scope (explicit)

- Typing indicators. Ever.
- Online/offline presence beyond the existing mood flower.
- Read receipts by default (opt-in only, per-letter).
- Real-time delivery guarantees.
- Group correspondence (all primitives are 1:1 in Phase 0.5).
- Moderation tooling beyond block/report on guestbook.
- Ghost composition for Guestbook entries.
- Any public-facing Phase 2 protocol documentation.

---

## Naming Decisions Locked

- **The Exchange** — the correspondence surface as a whole
- **Letter** / **Response** / **Guestbook** / **Future Letter** — the four primitives
- **Ghost Writer** — the AI composition feature
- **Off / Draft / Auto** — the three Ghost modes
- **Quill markers** — the attribution iconography
