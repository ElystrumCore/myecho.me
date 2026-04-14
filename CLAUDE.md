# CLAUDE.md — Echo (myecho.me) Phase 0

## Project Overview

Echo is a living journal platform. Users upload their digital history (social exports, writing samples, career data) and Echo builds a profile that can journal in their voice, answer questions as them, and track how their thinking evolves over time.

This is Phase 0 — the smallest thing that proves the concept works. We are building a FastAPI backend + journal frontend that ingests LinkedIn data, builds a user profile (StyleFingerprint, BeliefGraph, KnowledgeMap), and serves a public journal page where the Echo can publish posts and answer questions in the user's voice.

**Product URL:** myecho.me
**Tagline:** Your voice, persisting.
**What it is:** A time capsule with a pulse — the blog you always meant to keep, written by someone who actually knows you.
**What it is NOT:** A chatbot, a digital employee, a deepfake, social media, a content mill, or the metaverse.

---

## Architecture Context

Echo lives in the ElystrumCore monorepo. It follows the same patterns as existing services:

- **FastAPI** service (like Cyclone on :8000, BridgeDeck on :8003)
- **Cyclone (VRAG)** as the memory/artifact store for Echo profiles and journal entries
- **HyperSchool atomization patterns** for content ingestion — same pipeline concept, different input source

Pick a port that doesn't conflict (suggest :8004).

---

## Phase 0 Scope — What To Build

### 1. Ingest Pipeline

Build parsers for LinkedIn data exports. The user uploads CSV files. We have real sample data to work from:

**messages.csv** — LinkedIn DMs
- Columns: CONVERSATION ID, CONVERSATION TITLE, FROM, SENDER PROFILE URL, TO, RECIPIENT PROFILE URLS, DATE, SUBJECT, CONTENT, FOLDER, ATTACHMENTS, IS MESSAGE DRAFT
- Use: Extract all messages FROM the user. These are the primary voice/tone training data.
- Key analysis already done on sample data:
  - 2,083 substantive messages from the user
  - Median message length: 69 chars (terse communicator)
  - Top openers: "Hey" (187), "Yeah" (152), "Sounds good" (131), "Thanks" (106)
  - Signature phrases: "for sure" (135), "definitely" (92), "man" (181), "haha" (63)
  - Closing pattern: "Thanks" (481 messages)
  - Only 16% of messages contain questions — user states positions, doesn't interview
  - Topic signals: AI (332 mentions), project (75), pipeline (45), business (37)

**Endorsement_Received_Info.csv** — Skill endorsements
- Columns: Endorsement Date, Skill Name, Endorser First Name, Endorser Last Name, Endorser Public Url, Endorsement Status
- Use: Build KnowledgeMap — what skills the user is recognized for and by how many people
- Key data: 554 endorsements from 125 unique endorsers
- Top skills: Piping (75), Gas (74), Pipelines (61), Commissioning (46), Oil & Gas (32), Construction (27)

**Connections.csv** — Professional network
- Columns: First Name, Last Name, URL, Email Address, Company, Position, Connected On
- Note: Has 3 header/note lines before the actual CSV header
- Use: Build network graph — what industries/companies/roles the user is connected to
- Key data: 19,483 connections. Top companies: Self-employed (242), Cenovus (212), FLINT (200), CNRL (187), Pembina (175), TC Energy (170)
- Growth curve: 188 connections in 2013 → 6,627 in 2025

**Career History** (manual input or structured data):
- 18 positions from 2005-present
- Trajectory: Pipefitter Apprentice → Lead Hand → Operator → Planner → Engineering Tech → Project Controls → Superintendent → Fab Manager → PM → District Manager → Division Manager → Construction Manager → SVP
- This needs a structured input format — JSON or form-based

Additional ingest sources (future, not Phase 0):
- Twitter/X archive JSON
- Facebook takeout
- Blog post uploads (markdown/text)
- Voice declarations (free-form text the user writes to seed positions)

### 2. Profile Builder

From ingested data, construct three core profile artifacts:

**StyleFingerprint**
```json
{
  "vocabulary": {
    "openers": {"hey": 187, "yeah": 152, "sounds good": 131},
    "closers": {"thanks": 481, "best": 25, "let me know": 21},
    "signature_phrases": {"for sure": 135, "definitely": 92, "at the moment": 40},
    "filler_markers": {"man": 181, "haha": 63, "lol": 46}
  },
  "structure": {
    "median_length": 69,
    "short_pct": 62.7,
    "medium_pct": 34.9,
    "long_pct": 2.4,
    "question_rate": 0.165
  },
  "tone": {
    "formality_range": [0.2, 0.6],
    "warmth": 0.8,
    "directness": 0.9,
    "humor_frequency": 0.05
  }
}
```

**BeliefGraph**
```json
{
  "topics": [
    {
      "name": "AI deployment",
      "mention_count": 332,
      "recency_weight": 0.95,
      "confidence": 0.85,
      "positions": [
        "Primary constraint is deployment readiness not model capability",
        "Data sovereignty matters more than model performance for enterprise",
        "Local models are viable for production when properly configured"
      ],
      "evidence_refs": ["msg_id_123", "msg_id_456"]
    }
  ],
  "meta": {
    "total_topics": 10,
    "last_updated": "2026-04-13",
    "drift_alerts": []
  }
}
```

**KnowledgeMap**
```json
{
  "domains": [
    {
      "name": "Oil & Gas Construction",
      "depth": "expert",
      "years": 20,
      "endorsement_count": 234,
      "top_skills": ["Piping", "Gas", "Pipelines", "Commissioning"],
      "roles_held": ["Pipefitter", "Superintendent", "PM", "District Manager", "SVP"]
    },
    {
      "name": "AI/ML Systems",
      "depth": "practitioner",
      "years": 2,
      "endorsement_count": 0,
      "top_skills": ["LLM deployment", "Agent frameworks", "VRAG"],
      "roles_held": []
    }
  ],
  "network": {
    "total_connections": 19483,
    "top_industries": ["Oil & Gas", "Construction", "Engineering"],
    "geographic_center": "Grande Prairie, AB"
  }
}
```

### 3. Voice Model / Echo Engine

The component that generates text in the user's voice. For Phase 0 this is a prompt engineering layer, not fine-tuning:

- Build a system prompt constructor that takes StyleFingerprint + BeliefGraph + KnowledgeMap and produces an LLM system prompt
- The prompt should instruct the model to write as the user — using their vocabulary patterns, sentence length distribution, tone markers, and topical positions
- Use Claude API (or configurable LLM backend) for generation
- Two modes:
  - **Journal mode**: Generate a blog post on a topic in the user's voice. User provides topic or Echo suggests based on BeliefGraph topics.
  - **Ask mode**: Answer a visitor's question in the user's voice, drawing from BeliefGraph positions and KnowledgeMap expertise.

### 4. Journal Surface (Frontend)

Public-facing journal page at `/echo/{username}`. This is the product.

**Visitor views:**
- **Stream**: Chronological list of Echo-generated posts (approved by user). Clean, minimal blog layout. Think old-school LiveJournal meets modern readability — not a social media feed.
- **About**: KnowledgeMap summary — who this person is, what they know, their career arc
- **Ask**: Text input where visitor types a question → Echo responds in the user's voice
- **Timeline**: Visual representation of career + topic evolution over time

**Owner views (authenticated):**
- **Dashboard**: Pending posts for review/approval, recent Ask interactions, drift alerts
- **Profile**: View/edit StyleFingerprint, BeliefGraph, KnowledgeMap
- **Ingest**: Upload new data sources, see processing status
- **Settings**: Privacy controls, what Ask can/can't answer, voice tuning

**Design direction:**
- Dark mode default, clean typography, generous whitespace
- NOT social media aesthetic — no avatars, no likes, no follower counts
- Think: a well-designed personal blog that happens to be AI-powered
- Reference the LiveJournal simplicity — content first, chrome second
- The original LJ codebase is archived at https://github.com/apparentlymart/livejournal — the Perl code isn't useful but the data models and journal entry schema are worth studying for conceptual reference
- The living fork Dreamwidth (dreamwidth.org) shows how the journal model evolved

---

## Data Models

### User
```
- id: uuid
- username: string (unique, URL-safe)
- display_name: string
- email: string
- created_at: datetime
- profile_version: int
```

### EchoProfile
```
- user_id: uuid (FK)
- style_fingerprint: jsonb
- belief_graph: jsonb
- knowledge_map: jsonb
- voice_prompt: text (compiled system prompt)
- version: int
- created_at: datetime
- updated_at: datetime
```

### IngestSource
```
- id: uuid
- user_id: uuid (FK)
- source_type: enum (linkedin_messages, linkedin_endorsements, linkedin_connections, career_history, writing_sample, voice_declaration)
- file_path: string
- status: enum (pending, processing, completed, failed)
- record_count: int
- created_at: datetime
- processed_at: datetime
```

### JournalEntry (metadata — lean, for listing queries)
Follows LJ pattern: separate content from metadata. LJ split `log2` (metadata) from `logtext2` (body). We do the same.
```
- id: uuid
- user_id: uuid (FK)
- title: string
- status: enum (draft, pending_review, published, archived)
- security: enum (public, private, selected)     # LJ pattern: per-entry visibility, not global
- generated_by: enum (echo, user, hybrid)
- generation_prompt: text (what triggered this post)
- pub_year: int                                   # LJ pattern: date denormalization for archive/timeline queries
- pub_month: int
- pub_day: int
- published_at: datetime
- created_at: datetime
- updated_at: datetime
```

### JournalContent (heavy content — loaded on demand)
```
- entry_id: uuid (FK → JournalEntry)
- body: text (markdown)
- body_html: text (pre-rendered, optional)
```

### EntryProp (extensible metadata — LJ props pattern)
Instead of adding columns for every new attribute, use a key-value store with a registered catalog.
LJ used `logprop2` + `logproplist` for moods, music, location, tags, etc. without schema migrations.
Our JSONB fields serve a similar purpose, but formalizing the catalog prevents drift.
```
- entry_id: uuid (FK → JournalEntry)
- prop_key: string                                # registered key from PropCatalog
- prop_value: text
```

### PropCatalog (registry of known property types)
```
- key: string (PK)                                # e.g. "topic_tags", "echo_mood", "confidence", "belief_refs"
- data_type: enum (string, string_array, float, int, boolean, json)
- description: string
- created_at: datetime
```

Default props to register at init:
- `topic_tags` (string_array) — topics this entry relates to
- `echo_mood` (string) — inferred emotional state when generating (for drift tracking, inspired by LJ mood system)
- `echo_confidence` (float) — how confident Echo was in this generation
- `belief_refs` (string_array) — which BeliefGraph nodes were drawn on
- `generation_model` (string) — which LLM was used
- `revision_count` (int) — how many times owner edited before publishing

### AskInteraction
```
- id: uuid
- user_id: uuid (FK, whose Echo was asked)
- visitor_id: string (anonymous hash or session)
- question: text
- response: text
- node_type: string (default "ask")               # LJ pattern: generic nodetype for threading
- parent_id: uuid (nullable, FK → self)            # for follow-up questions / threading
- belief_refs: string[] (which BeliefGraph nodes were used)
- confidence: float
- created_at: datetime
```

### DriftEvent
```
- id: uuid
- user_id: uuid (FK)
- topic: string
- original_position: text
- current_position: text
- drift_score: float
- echo_mood_at_drift: string (nullable)            # what was Echo's inferred state when drift occurred
- acknowledged: boolean
- created_at: datetime
```

---

## API Endpoints

### Ingest
- `POST /api/ingest/linkedin/messages` — upload messages.csv
- `POST /api/ingest/linkedin/endorsements` — upload endorsements CSV
- `POST /api/ingest/linkedin/connections` — upload connections CSV
- `POST /api/ingest/career` — submit career history JSON
- `POST /api/ingest/writing` — upload writing samples
- `POST /api/ingest/declaration` — submit voice declaration text
- `GET /api/ingest/status/{user_id}` — check ingest pipeline status

### Profile
- `GET /api/profile/{user_id}` — full EchoProfile
- `GET /api/profile/{user_id}/fingerprint` — StyleFingerprint only
- `GET /api/profile/{user_id}/beliefs` — BeliefGraph only
- `GET /api/profile/{user_id}/knowledge` — KnowledgeMap only
- `PUT /api/profile/{user_id}/beliefs` — manually update/confirm positions
- `POST /api/profile/{user_id}/rebuild` — trigger profile rebuild from all sources

### Echo Engine
- `POST /api/echo/{user_id}/generate` — generate a journal post (topic optional)
- `POST /api/echo/{user_id}/ask` — ask the Echo a question, get response
- `POST /api/echo/{user_id}/assist` — inline editor AI assist (selected text + instruction → rewritten in voice)
- `GET /api/echo/{user_id}/drafts` — list pending drafts
- `PUT /api/echo/{user_id}/drafts/{entry_id}` — approve/edit/reject draft

### Journal (Public)
- `GET /api/journal/{username}` — published entries for a user
- `GET /api/journal/{username}/entry/{id}` — single entry
- `GET /api/journal/{username}/positions` — public BeliefGraph summary
- `GET /api/journal/{username}/timeline` — career + topic timeline
- `POST /api/journal/{username}/ask` — public Ask endpoint

### Owner Dashboard
- `GET /api/dashboard/{user_id}/overview` — stats, pending items, drift alerts
- `GET /api/dashboard/{user_id}/drift` — drift events
- `PUT /api/dashboard/{user_id}/drift/{event_id}/acknowledge` — acknowledge drift

---

## Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL with jsonb for profile data
- **Storage**: Cyclone VRAG for journal entries and profile artifacts (if available), else local file storage
- **LLM**: Claude API for voice generation (configurable, support OpenAI/local model fallback)
- **Frontend (public)**: Server-rendered Jinja2 templates — fast, readable, SEO-friendly. The journal page is the product; it must load instantly.
- **Frontend (owner)**: React app with BlockNote editor. Vite build, served by FastAPI at `/dashboard/*`. The editing experience is where the AI collaboration happens.
- **Editor**: [BlockNote](https://github.com/TypeCellOS/BlockNote) — block-based rich text editor built on ProseMirror/Tiptap. AI integration via `@blocknote/xl-ai` wired to Echo's voice engine. The editor doesn't know it's writing as the user — it calls Echo's `/assist` endpoint, and Echo handles the voice.
- **Auth**: Simple session-based for MVP. Owner login only. Visitors don't need accounts.

### Editor Architecture (BlockNote + Echo)

The owner dashboard uses BlockNote as a collaborative writing environment where Echo is an inline AI assistant:

**How AI actions flow:**
1. Owner writes/edits a post in BlockNote
2. Owner selects text → clicks AI button (or types `/ai rewrite this more casually`)
3. BlockNote calls `POST /api/echo/{user_id}/assist` with the selected text + instruction
4. Echo's assist endpoint loads the user's voice prompt (StyleFingerprint + BeliefGraph + KnowledgeMap)
5. Claude rewrites the text in the user's voice, following the instruction
6. BlockNote replaces the selection with the result

**AI actions available in the editor:**
- **Rewrite in my voice** — takes any text and rewrites it matching the StyleFingerprint
- **Continue this thought** — extends from cursor position using BeliefGraph context
- **Make more direct / casual / formal** — tone adjustments within the user's natural range
- **Add evidence** — pulls supporting details from KnowledgeMap expertise
- **What would I say about...** — generates a paragraph on a topic from BeliefGraph positions

**Why BlockNote specifically:**
- Block-based editing maps to journal entries as composed content, not raw text
- AI inline in the document, not in a sidebar — the LLM is a collaborator
- RAG integration built in — plugs into Echo's retrieval pipeline
- ProseMirror foundation (Google Docs-grade)
- Themeable UI matches the owner's generated journal theme
- Core is MPL-2.0, AI integration is GPL-3.0 (fine for Echo's open source model)

---

## File Structure (suggested)

```
echo/
├── CLAUDE.md              # this file
├── README.md
├── pyproject.toml
├── echo/
│   ├── __init__.py
│   ├── main.py            # FastAPI app
│   ├── config.py           # settings, env vars
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── profile.py
│   │   ├── journal.py
│   │   ├── theme.py
│   │   └── ingest.py
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── linkedin.py     # LinkedIn CSV parsers
│   │   ├── career.py       # Career history parser
│   │   ├── writing.py      # Writing sample processor
│   │   └── pipeline.py     # Orchestrates full ingest
│   ├── profile/
│   │   ├── __init__.py
│   │   ├── fingerprint.py  # StyleFingerprint builder
│   │   ├── beliefs.py      # BeliefGraph builder
│   │   ├── knowledge.py    # KnowledgeMap builder
│   │   └── compiler.py     # Compiles profile → voice prompt
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── voice.py        # LLM voice generation
│   │   ├── journal.py      # Journal post generation
│   │   ├── ask.py          # Ask response generation
│   │   ├── assist.py       # Inline editor AI assist
│   │   ├── themes.py       # Theme generation engine
│   │   └── drift.py        # Drift detection
│   ├── api/
│   │   ├── __init__.py
│   │   ├── ingest.py       # Ingest endpoints
│   │   ├── profile.py      # Profile endpoints
│   │   ├── echo.py         # Generation endpoints
│   │   ├── theme.py        # Theme endpoints
│   │   ├── journal.py      # Public journal endpoints
│   │   └── dashboard.py    # Owner dashboard endpoints
│   └── templates/          # Jinja2 for public pages
│       ├── base.html
│       ├── journal.html
│       ├── entry.html
│       ├── ask.html
│       ├── timeline.html
│       └── dashboard.html
├── frontend/               # React app for owner dashboard
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api.ts           # Echo API client
│       └── components/
│           └── EchoEditor.tsx  # BlockNote editor wired to Echo voice engine
├── tests/
│   ├── test_ingest.py
│   ├── test_profile.py
│   └── test_engine.py
├── data/
│   ├── sample/             # Sample LinkedIn CSVs for testing
│   └── reference/
│       └── livejournal/    # Cloned LJ repo (gitignored) — schema reference only
└── alembic/                # DB migrations
```

---

## LiveJournal Schema Reference

The original LJ codebase is cloned at `data/reference/livejournal/` (gitignored). The main schema file is `bin/upgrading/update-db-general.pl`. Six patterns were extracted and adopted:

1. **Separate content from metadata.** LJ splits `log2` (metadata, security, dates, reply counts) from `logtext2` (subject + body text). Echo does the same — JournalEntry is lean for listing queries, JournalContent holds the body and loads on demand.

2. **The props system.** Instead of adding columns for every new entry attribute, LJ uses a `propid → value` key-value store (`logprop2` + `logproplist`). This let them add moods, music, location, tags, comment screening, and revision tracking without schema migrations. Echo formalizes this with EntryProp + PropCatalog.

3. **Security via per-entry control.** LJ uses `security` enum (public/private/usemask) + a 32-bit allowmask for friend groups. Echo adopts the three-tier model (public / owner-only / selected) without the friend group bitmask in Phase 0.

4. **Comment threading with generic nodetype.** LJ's `talk2` uses `parenttalkid` for nesting and `nodetype` to make comments attachable to different content types. When Echo adds comment support on Ask responses or journal entries, this is the pattern. AskInteraction already has `node_type` and `parent_id` for this.

5. **Date denormalization.** LJ stores year/month/day as separate columns alongside the datetime for fast archive queries ("show me all posts from March 2024"). JournalEntry includes `pub_year`, `pub_month`, `pub_day` for the timeline view.

6. **Mood as structured metadata.** LJ's hierarchical moods with parent-child relationships. Echo's BeliefGraph topics serve a similar purpose, but the idea of an `echo_mood` signal per journal entry — what was the Echo's inferred state when generating — is adopted for drift tracking via the props system.

**What LJ got right that Echo preserves:**
- Journal entries are the atomic unit, not posts in a feed
- Security is per-entry, not global
- Metadata is extensible without schema changes
- The owner controls visibility, not an algorithm

**What Echo does differently:**
- No friends list / social graph — the journal is the product, not the network
- AI-generated content with approval workflow (LJ was human-authored only)
- BeliefGraph / StyleFingerprint replace mood/music metadata with something deeper
- Drift detection has no LJ equivalent — this is new territory

---

## Key Design Principles

1. **Content first.** The journal page should be readable and clean. No UI chrome that distracts from the writing.
2. **Honest by default.** When Echo doesn't know, it says so. When it extrapolates, it flags uncertainty. When it drifts, it alerts the owner.
3. **Owner controls everything.** Nothing publishes without approval (in Phase 0). The owner sees everything Echo generates before it goes live.
4. **Transparency always.** Every Echo response is labeled as Echo-generated. No pretending to be the real person.
5. **Data sovereignty.** User owns all data. Full export, full delete. No training on user data without explicit opt-in.

---

## First Sprint Priority

1. LinkedIn ingest parsers (messages, endorsements, connections)
2. StyleFingerprint builder from message data
3. BeliefGraph builder (basic topic extraction + position mapping)
4. KnowledgeMap builder from endorsements + career data
5. Voice prompt compiler (profile → system prompt)
6. Journal post generation endpoint
7. Ask endpoint
8. Public journal page (simple, clean, functional)
9. Owner dashboard (review drafts, see drift)

Start with ingest → profile → engine → frontend. Each layer builds on the one before it.
