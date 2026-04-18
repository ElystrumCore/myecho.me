"""
Build Echo Profile from conversation exports.

Parses Claude and ChatGPT exports, extracts the user's messages,
builds StyleFingerprint + BeliefGraph + KnowledgeMap, and ingests
into Cyclone VRAG.

Usage:
    python scripts/build_echo_profile.py                    # Analyze only
    python scripts/build_echo_profile.py --ingest           # Analyze + ingest to Cyclone
    python scripts/build_echo_profile.py --profile-only     # Just build profile JSON
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent / "data" / "exports"
PROFILE_DIR = Path(__file__).parent.parent / "data" / "profile"
CYCLONE_URL = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Message extraction
# ---------------------------------------------------------------------------

@dataclass
class UserMessage:
    """A single message from the user across any platform."""
    text: str
    source: str  # "claude" | "chatgpt" | "linkedin" | "facebook"
    timestamp: float = 0.0
    conversation_title: str = ""
    word_count: int = 0


def extract_claude_messages(path: Path) -> list[UserMessage]:
    """Extract user messages from Claude export."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    messages = []
    for conv in data:
        title = conv.get("name", "untitled")
        for msg in conv.get("chat_messages", []):
            if msg.get("sender") == "human":
                text = ""
                for content in msg.get("content", []):
                    if isinstance(content, dict) and content.get("type") == "text":
                        text += content.get("text", "")
                    elif isinstance(content, str):
                        text += content
                if text.strip():
                    messages.append(UserMessage(
                        text=text.strip(),
                        source="claude",
                        timestamp=0,
                        conversation_title=title,
                        word_count=len(text.split()),
                    ))
    return messages


def extract_chatgpt_messages(path: Path) -> list[UserMessage]:
    """Extract user messages from ChatGPT export."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    messages = []
    for conv in data:
        title = conv.get("title", "untitled")
        mapping = conv.get("mapping", {})
        for node in mapping.values():
            msg = node.get("message")
            if not msg:
                continue
            if msg.get("author", {}).get("role") != "user":
                continue
            parts = msg.get("content", {}).get("parts", [])
            text = ""
            for part in parts:
                if isinstance(part, str):
                    text += part
            if text.strip():
                ts = msg.get("create_time", 0) or 0
                messages.append(UserMessage(
                    text=text.strip(),
                    source="chatgpt",
                    timestamp=ts,
                    conversation_title=title,
                    word_count=len(text.split()),
                ))
    return messages


# ---------------------------------------------------------------------------
# StyleFingerprint
# ---------------------------------------------------------------------------

def build_style_fingerprint(messages: list[UserMessage]) -> dict[str, Any]:
    """Build StyleFingerprint from all user messages."""
    texts = [m.text for m in messages]
    all_text = " ".join(texts)
    words = all_text.lower().split()

    # Length distribution
    lengths = [m.word_count for m in messages]
    short = sum(1 for l in lengths if l <= 20) / len(lengths)
    medium = sum(1 for l in lengths if 20 < l <= 100) / len(lengths)
    long = sum(1 for l in lengths if l > 100) / len(lengths)
    median_len = sorted(lengths)[len(lengths) // 2] if lengths else 0

    # Opener analysis (first word/phrase of each message)
    openers = Counter()
    for t in texts:
        first_words = t.split()[:3]
        if first_words:
            opener = first_words[0].lower().rstrip(".,!?")
            openers[opener] += 1

    # Signature phrases
    phrase_counts = Counter()
    phrases_to_check = [
        "for sure", "definitely", "at the moment", "sounds good",
        "let's", "yeah", "makes sense", "that's", "I think",
        "we need", "let me", "actually", "basically", "honestly",
        "the thing is", "what if", "how about", "nice", "perfect",
        "exactly", "right", "cool", "good call", "fair enough",
    ]
    text_lower = all_text.lower()
    for phrase in phrases_to_check:
        count = text_lower.count(phrase)
        if count > 0:
            phrase_counts[phrase] = count

    # Question rate
    questions = sum(1 for t in texts if "?" in t)
    question_rate = questions / len(texts) if texts else 0

    # Directness: ratio of statements to questions
    # Formality: presence of formal markers
    formal_markers = ["please", "would you", "could you", "thank you", "regards"]
    informal_markers = ["yeah", "gonna", "wanna", "gotta", "lol", "haha", "man", "dude"]
    formal_count = sum(text_lower.count(m) for m in formal_markers)
    informal_count = sum(text_lower.count(m) for m in informal_markers)
    total_markers = formal_count + informal_count or 1
    formality = formal_count / total_markers

    # Technical density
    tech_terms = [
        "api", "docker", "kubernetes", "pipeline", "database", "server",
        "model", "training", "deploy", "endpoint", "schema", "query",
        "commit", "branch", "merge", "test", "debug", "config",
        "llm", "embedding", "vector", "token", "prompt", "agent",
        "cyclone", "slipstream", "bridgedeck", "substrate", "harmonic",
        "kuramoto", "toroidal", "codec", "usl", "vrag",
    ]
    tech_count = sum(text_lower.count(t) for t in tech_terms)
    tech_density = tech_count / len(words) if words else 0

    # Industry terms
    industry_terms = [
        "welder", "pipefitter", "inspector", "turnaround", "commissioning",
        "fabrication", "spool", "nde", "hydro", "b pressure", "cwb",
        "absa", "iso", "p&id", "mtr", "grande prairie", "montney",
        "drilling", "operator", "contractor", "certification", "h2s",
        "pipeline", "construction", "trades", "rig",
    ]
    industry_count = sum(text_lower.count(t) for t in industry_terms)
    industry_density = industry_count / len(words) if words else 0

    return {
        "vocabulary": {
            "top_openers": dict(openers.most_common(20)),
            "signature_phrases": dict(phrase_counts.most_common(20)),
        },
        "structure": {
            "total_messages": len(messages),
            "median_word_count": median_len,
            "short_pct": round(short * 100, 1),
            "medium_pct": round(medium * 100, 1),
            "long_pct": round(long * 100, 1),
            "question_rate": round(question_rate, 3),
        },
        "tone": {
            "formality": round(formality, 3),
            "directness": round(1 - question_rate, 3),
            "tech_density": round(tech_density, 4),
            "industry_density": round(industry_density, 4),
        },
        "sources": dict(Counter(m.source for m in messages)),
    }


# ---------------------------------------------------------------------------
# BeliefGraph
# ---------------------------------------------------------------------------

def build_belief_graph(messages: list[UserMessage]) -> dict[str, Any]:
    """Extract topics and positions from user messages."""
    # Topic detection with keyword clusters
    topic_keywords = {
        "AI/ML Systems": ["ai", "llm", "model", "training", "agent", "embedding", "prompt", "neural", "transformer", "fine-tune"],
        "Oil & Gas Construction": ["pipeline", "turnaround", "commissioning", "fabrication", "welder", "inspector", "spool", "nde", "rig"],
        "Peace Region Market": ["grande prairie", "peace region", "montney", "fort st. john", "dawson creek", "peace river"],
        "Workforce/Hiring": ["hiring", "contractor", "trades", "certification", "h2s", "cwb", "absa", "b pressure", "workforce"],
        "Technology Infrastructure": ["docker", "kubernetes", "api", "database", "deploy", "server", "cyclone", "slipstream", "substrate"],
        "Business Strategy": ["revenue", "pricing", "market", "customer", "product", "launch", "monetize", "subscription"],
        "Architecture/Systems": ["architecture", "schema", "graph", "harmonic", "toroidal", "codec", "lattice", "oscillator", "kuramoto"],
        "Content/Marketing": ["linkedin", "facebook", "post", "content", "engagement", "follower", "audience", "brand"],
    }

    topic_counts: dict[str, int] = {}
    topic_messages: dict[str, list[str]] = defaultdict(list)

    for msg in messages:
        text_lower = msg.text.lower()
        for topic, keywords in topic_keywords.items():
            hits = sum(1 for kw in keywords if kw in text_lower)
            if hits >= 2:  # At least 2 keyword hits to count
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
                if len(topic_messages[topic]) < 5:  # Keep 5 sample messages per topic
                    topic_messages[topic].append(msg.text[:200])

    # Sort by frequency
    topics = []
    for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
        topics.append({
            "name": topic,
            "mention_count": count,
            "confidence": min(1.0, count / 50),  # Normalize to 50+ mentions = full confidence
            "sample_messages": topic_messages.get(topic, []),
        })

    return {
        "topics": topics,
        "total_topics": len(topics),
        "total_messages_analyzed": len(messages),
    }


# ---------------------------------------------------------------------------
# Conversation summaries for Cyclone
# ---------------------------------------------------------------------------

def build_conversation_summaries(messages: list[UserMessage]) -> list[dict[str, Any]]:
    """Group messages by conversation and build summaries for Cyclone ingestion."""
    by_conv: dict[str, list[UserMessage]] = defaultdict(list)
    for msg in messages:
        key = f"{msg.source}::{msg.conversation_title}"
        by_conv[key].append(msg)

    summaries = []
    for key, msgs in by_conv.items():
        source, title = key.split("::", 1)
        total_words = sum(m.word_count for m in msgs)
        if total_words < 20:
            continue

        # Concatenate user messages for this conversation
        user_text = "\n\n".join(m.text for m in msgs)
        if len(user_text) > 8000:
            user_text = user_text[:8000] + "\n\n[truncated]"

        summaries.append({
            "title": f"Echo:{source}:{title}"[:200],
            "content": user_text,
            "content_type": "echo_conversation",
            "metadata": {
                "source": source,
                "source_project": "echo",
                "conversation_title": title,
                "message_count": len(msgs),
                "total_words": total_words,
                "content_hash": hashlib.sha256(user_text[:500].encode()).hexdigest()[:16],
            },
        })

    return summaries


# ---------------------------------------------------------------------------
# Cyclone ingestion
# ---------------------------------------------------------------------------

def ingest_to_cyclone(summaries: list[dict], profile: dict, cyclone_url: str) -> dict:
    """Ingest conversation summaries and profile into Cyclone."""
    import requests

    results = {"ingested": 0, "skipped": 0, "errors": 0}

    # Ingest conversations
    for i, doc in enumerate(summaries):
        try:
            resp = requests.post(f"{cyclone_url}/api/documents/", json=doc, timeout=10)
            if resp.status_code in (200, 201):
                results["ingested"] += 1
            else:
                results["errors"] += 1
        except Exception:
            results["errors"] += 1

        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(summaries)} ({results['ingested']} ingested)")
            time.sleep(0.1)

    # Ingest profile as a document
    profile_doc = {
        "title": "Echo Profile — CJ Elliott (StyleFingerprint + BeliefGraph)",
        "content": json.dumps(profile, indent=2, default=str),
        "content_type": "echo_profile",
        "metadata": {
            "source": "echo_builder",
            "source_project": "echo",
            "profile_type": "style_fingerprint_belief_graph",
        },
    }
    try:
        requests.post(f"{cyclone_url}/api/documents/", json=profile_doc, timeout=10)
        results["ingested"] += 1
    except Exception:
        results["errors"] += 1

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build Echo profile from conversation exports")
    parser.add_argument("--ingest", action="store_true", help="Ingest to Cyclone")
    parser.add_argument("--profile-only", action="store_true", help="Just build profile JSON")
    parser.add_argument("--cyclone-url", default=CYCLONE_URL)
    args = parser.parse_args()

    print("=== Echo Profile Builder ===")
    print()

    # Extract messages from all sources
    all_messages: list[UserMessage] = []

    claude_path = DATA_DIR / "claude" / "conversations.json"
    if claude_path.exists():
        claude_msgs = extract_claude_messages(claude_path)
        print(f"Claude: {len(claude_msgs)} user messages extracted")
        all_messages.extend(claude_msgs)

    chatgpt_path = DATA_DIR / "chatgpt" / "conversations.json"
    if chatgpt_path.exists():
        chatgpt_msgs = extract_chatgpt_messages(chatgpt_path)
        print(f"ChatGPT: {len(chatgpt_msgs)} user messages extracted")
        all_messages.extend(chatgpt_msgs)

    print(f"\nTotal: {len(all_messages)} messages across {len(set(m.source for m in all_messages))} sources")
    total_words = sum(m.word_count for m in all_messages)
    print(f"Total words: {total_words:,}")
    print()

    # Build profile
    print("Building StyleFingerprint...")
    fingerprint = build_style_fingerprint(all_messages)

    print("Building BeliefGraph...")
    beliefs = build_belief_graph(all_messages)

    profile = {
        "user": "CJ Elliott",
        "built_at": datetime.now().isoformat(),
        "style_fingerprint": fingerprint,
        "belief_graph": beliefs,
    }

    # Save profile
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    profile_path = PROFILE_DIR / "echo_profile.json"
    with open(profile_path, "w") as f:
        json.dump(profile, f, indent=2, default=str)
    print(f"\nProfile saved to {profile_path}")

    # Print summary
    print("\n=== StyleFingerprint ===")
    s = fingerprint["structure"]
    print(f"Messages: {s['total_messages']}")
    print(f"Median words: {s['median_word_count']}")
    print(f"Short/Med/Long: {s['short_pct']}% / {s['medium_pct']}% / {s['long_pct']}%")
    print(f"Question rate: {s['question_rate']}")
    t = fingerprint["tone"]
    print(f"Formality: {t['formality']}")
    print(f"Directness: {t['directness']}")
    print(f"Tech density: {t['tech_density']}")
    print(f"Industry density: {t['industry_density']}")
    print(f"\nTop openers: {list(fingerprint['vocabulary']['top_openers'].items())[:10]}")
    print(f"Signature phrases: {list(fingerprint['vocabulary']['signature_phrases'].items())[:10]}")
    print(f"Sources: {fingerprint['sources']}")

    print("\n=== BeliefGraph ===")
    for topic in beliefs["topics"]:
        print(f"  {topic['name']}: {topic['mention_count']} mentions (conf: {topic['confidence']:.2f})")

    if args.profile_only:
        return

    # Build conversation summaries
    print("\nBuilding conversation summaries...")
    summaries = build_conversation_summaries(all_messages)
    print(f"Conversations: {len(summaries)}")

    if not args.ingest:
        print(f"\nDRY RUN: Would ingest {len(summaries)} conversations + profile to {args.cyclone_url}")
        print("Run with --ingest to execute")
        return

    # Ingest
    print(f"\nIngesting to {args.cyclone_url}...")
    results = ingest_to_cyclone(summaries, profile, args.cyclone_url)
    print(f"\n=== Ingestion Results ===")
    print(f"Ingested: {results['ingested']}")
    print(f"Errors: {results['errors']}")


if __name__ == "__main__":
    main()
