"""LinkedIn CSV parsers for messages, endorsements, and connections."""

import csv
import io
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class MessageStats:
    total_messages: int = 0
    user_messages: int = 0
    median_length: float = 0.0
    openers: dict[str, int] = field(default_factory=dict)
    closers: dict[str, int] = field(default_factory=dict)
    signature_phrases: dict[str, int] = field(default_factory=dict)
    filler_markers: dict[str, int] = field(default_factory=dict)
    topic_signals: dict[str, int] = field(default_factory=dict)
    question_rate: float = 0.0
    length_distribution: dict[str, float] = field(default_factory=dict)
    raw_messages: list[str] = field(default_factory=list)


@dataclass
class EndorsementStats:
    total_endorsements: int = 0
    unique_endorsers: int = 0
    skills: dict[str, int] = field(default_factory=dict)


@dataclass
class ConnectionStats:
    total_connections: int = 0
    companies: dict[str, int] = field(default_factory=dict)
    positions: dict[str, int] = field(default_factory=dict)
    yearly_growth: dict[str, int] = field(default_factory=dict)


COMMON_OPENERS = [
    "hey", "yeah", "sounds good", "thanks", "hi", "hello",
    "sure", "no worries", "absolutely", "ok", "okay",
]

SIGNATURE_PHRASES = [
    "for sure", "definitely", "at the moment", "to be honest",
    "at the end of the day", "in terms of", "moving forward",
]

FILLER_MARKERS = ["man", "haha", "lol", "hah", "lmao", "dude", "bro"]

TOPIC_KEYWORDS = {
    "ai": ["ai", "artificial intelligence", "machine learning", "ml", "llm", "gpt", "model"],
    "project": ["project", "scope", "deliverable", "milestone"],
    "pipeline": ["pipeline", "piping", "spool", "weld"],
    "business": ["business", "revenue", "margin", "profit", "client"],
    "construction": ["construction", "site", "turnaround", "shutdown", "commissioning"],
}


def parse_messages(csv_content: str, user_name: str) -> MessageStats:
    """Parse LinkedIn messages.csv and extract voice/tone data.

    Filters to messages FROM the specified user for style analysis.
    """
    stats = MessageStats()
    reader = csv.DictReader(io.StringIO(csv_content))

    user_messages: list[str] = []
    lengths: list[int] = []

    for row in reader:
        stats.total_messages += 1
        sender = (row.get("FROM") or "").strip()

        if user_name.lower() not in sender.lower():
            continue

        content = (row.get("CONTENT") or "").strip()
        if not content:
            continue

        stats.user_messages += 1
        user_messages.append(content)
        lengths.append(len(content))

    if not user_messages:
        return stats

    stats.raw_messages = user_messages

    # Length distribution
    lengths.sort()
    mid = len(lengths) // 2
    stats.median_length = lengths[mid] if len(lengths) % 2 else (lengths[mid - 1] + lengths[mid]) / 2

    short = sum(1 for l in lengths if l < 100)
    medium = sum(1 for l in lengths if 100 <= l < 500)
    long = sum(1 for l in lengths if l >= 500)
    total = len(lengths)
    stats.length_distribution = {
        "short_pct": round(short / total * 100, 1),
        "medium_pct": round(medium / total * 100, 1),
        "long_pct": round(long / total * 100, 1),
    }

    # Questions
    question_count = sum(1 for m in user_messages if "?" in m)
    stats.question_rate = round(question_count / len(user_messages), 3)

    # Openers
    opener_counter = Counter()
    for msg in user_messages:
        first_word = msg.split()[0].lower().rstrip("!,.")
        for opener in COMMON_OPENERS:
            if msg.lower().startswith(opener):
                opener_counter[opener] += 1
                break
    stats.openers = dict(opener_counter.most_common(10))

    # Closers — last word/phrase of messages
    closer_counter = Counter()
    for msg in user_messages:
        last_words = msg.strip().rstrip(".!?").split()[-2:] if len(msg.split()) >= 2 else msg.split()
        last_phrase = " ".join(last_words).lower()
        closer_counter[last_phrase] += 1
    stats.closers = dict(closer_counter.most_common(10))

    # Signature phrases
    phrase_counter = Counter()
    lower_messages = [m.lower() for m in user_messages]
    for phrase in SIGNATURE_PHRASES:
        count = sum(1 for m in lower_messages if phrase in m)
        if count > 0:
            phrase_counter[phrase] = count
    stats.signature_phrases = dict(phrase_counter.most_common(10))

    # Filler markers
    filler_counter = Counter()
    for marker in FILLER_MARKERS:
        count = sum(1 for m in lower_messages if marker in m.split())
        if count > 0:
            filler_counter[marker] = count
    stats.filler_markers = dict(filler_counter.most_common(10))

    # Topic signals
    topic_counter = Counter()
    for topic, keywords in TOPIC_KEYWORDS.items():
        count = sum(
            1 for m in lower_messages if any(kw in m for kw in keywords)
        )
        if count > 0:
            topic_counter[topic] = count
    stats.topic_signals = dict(topic_counter.most_common())

    return stats


def parse_endorsements(csv_content: str) -> EndorsementStats:
    """Parse LinkedIn Endorsement_Received_Info.csv."""
    stats = EndorsementStats()
    reader = csv.DictReader(io.StringIO(csv_content))

    endorsers = set()
    skill_counter = Counter()

    for row in reader:
        stats.total_endorsements += 1
        skill = (row.get("Skill Name") or "").strip()
        endorser_first = (row.get("Endorser First Name") or "").strip()
        endorser_last = (row.get("Endorser Last Name") or "").strip()

        if skill:
            skill_counter[skill] += 1
        if endorser_first or endorser_last:
            endorsers.add(f"{endorser_first} {endorser_last}")

    stats.unique_endorsers = len(endorsers)
    stats.skills = dict(skill_counter.most_common())
    return stats


def parse_connections(csv_content: str) -> ConnectionStats:
    """Parse LinkedIn Connections.csv.

    Note: LinkedIn exports have 3 header/note lines before the actual CSV header.
    """
    stats = ConnectionStats()

    # Skip the first 3 lines (notes), then parse CSV
    lines = csv_content.strip().split("\n")
    # Find the actual header line (contains "First Name")
    header_idx = 0
    for i, line in enumerate(lines):
        if "First Name" in line:
            header_idx = i
            break

    csv_body = "\n".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(csv_body))

    company_counter = Counter()
    position_counter = Counter()
    year_counter = Counter()

    for row in reader:
        stats.total_connections += 1
        company = (row.get("Company") or "").strip()
        position = (row.get("Position") or "").strip()
        connected_on = (row.get("Connected On") or "").strip()

        if company:
            company_counter[company] += 1
        if position:
            position_counter[position] += 1
        if connected_on:
            # Format varies but year is typically last or parseable
            parts = connected_on.split()
            for part in parts:
                if part.isdigit() and len(part) == 4:
                    year_counter[part] += 1
                    break

    stats.companies = dict(company_counter.most_common(20))
    stats.positions = dict(position_counter.most_common(20))
    stats.yearly_growth = dict(sorted(year_counter.items()))
    return stats
