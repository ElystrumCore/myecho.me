"""Conversation ingest — parses Claude and ChatGPT exports, builds profile per-user."""
from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UserMessage:
    text: str
    source: str  # "claude" | "chatgpt" | "email" | "linkedin" | "facebook"
    conversation_title: str = ""
    word_count: int = 0


def extract_claude_messages(data: list[dict]) -> list[UserMessage]:
    """Extract user messages from Claude export JSON (already parsed)."""
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
                        text=text.strip(), source="claude",
                        conversation_title=title, word_count=len(text.split()),
                    ))
    return messages


def extract_chatgpt_messages(data: list[dict]) -> list[UserMessage]:
    """Extract user messages from ChatGPT export JSON (already parsed)."""
    messages = []
    for conv in data:
        title = conv.get("title", "untitled")
        for node in conv.get("mapping", {}).values():
            msg = node.get("message")
            if not msg or msg.get("author", {}).get("role") != "user":
                continue
            parts = msg.get("content", {}).get("parts", [])
            text = "".join(p for p in parts if isinstance(p, str))
            if text.strip():
                messages.append(UserMessage(
                    text=text.strip(), source="chatgpt",
                    conversation_title=title, word_count=len(text.split()),
                ))
    return messages


def build_style_fingerprint(messages: list[UserMessage]) -> dict[str, Any]:
    """Build StyleFingerprint from user messages."""
    if not messages:
        return {"vocabulary": {}, "structure": {}, "tone": {}, "sources": {}}

    texts = [m.text for m in messages]
    all_text = " ".join(texts)
    words = all_text.lower().split()
    text_lower = all_text.lower()

    lengths = [m.word_count for m in messages]
    median_len = sorted(lengths)[len(lengths) // 2] if lengths else 0
    short = sum(1 for l in lengths if l <= 20) / len(lengths)
    medium = sum(1 for l in lengths if 20 < l <= 100) / len(lengths)
    long_pct = sum(1 for l in lengths if l > 100) / len(lengths)

    openers = Counter()
    for t in texts:
        first = t.split()[:1]
        if first:
            openers[first[0].lower().rstrip(".,!?")] += 1

    phrases_to_check = [
        "for sure", "definitely", "at the moment", "sounds good", "let's",
        "yeah", "makes sense", "that's", "I think", "we need", "let me",
        "actually", "basically", "honestly", "the thing is", "what if",
        "how about", "nice", "perfect", "exactly", "right", "cool",
        "good call", "fair enough",
    ]
    phrase_counts = {p: text_lower.count(p) for p in phrases_to_check if text_lower.count(p) > 0}

    questions = sum(1 for t in texts if "?" in t)
    question_rate = questions / len(texts)

    formal_markers = ["please", "would you", "could you", "thank you", "regards"]
    informal_markers = ["yeah", "gonna", "wanna", "gotta", "lol", "haha", "man", "dude"]
    formal_count = sum(text_lower.count(m) for m in formal_markers)
    informal_count = sum(text_lower.count(m) for m in informal_markers)
    formality = formal_count / (formal_count + informal_count or 1)

    tech_terms = [
        "api", "docker", "pipeline", "database", "model", "training",
        "deploy", "endpoint", "schema", "llm", "embedding", "vector",
        "agent", "cyclone", "slipstream", "substrate", "harmonic",
    ]
    tech_count = sum(text_lower.count(t) for t in tech_terms)

    industry_terms = [
        "welder", "pipefitter", "inspector", "turnaround", "fabrication",
        "spool", "nde", "hydro", "pipeline", "construction", "drilling",
    ]
    industry_count = sum(text_lower.count(t) for t in industry_terms)

    return {
        "vocabulary": {
            "top_openers": dict(openers.most_common(20)),
            "signature_phrases": dict(sorted(phrase_counts.items(), key=lambda x: x[1], reverse=True)[:20]),
        },
        "structure": {
            "total_messages": len(messages),
            "median_word_count": median_len,
            "short_pct": round(short * 100, 1),
            "medium_pct": round(medium * 100, 1),
            "long_pct": round(long_pct * 100, 1),
            "question_rate": round(question_rate, 3),
        },
        "tone": {
            "formality": round(formality, 3),
            "directness": round(1 - question_rate, 3),
            "tech_density": round(tech_count / len(words), 4) if words else 0,
            "industry_density": round(industry_count / len(words), 4) if words else 0,
        },
        "sources": dict(Counter(m.source for m in messages)),
    }


def build_belief_graph(messages: list[UserMessage]) -> dict[str, Any]:
    """Extract topics and positions from messages."""
    if not messages:
        return {"topics": [], "total_topics": 0, "total_messages_analyzed": 0}

    topic_keywords = {
        "AI/ML Systems": ["ai", "llm", "model", "training", "agent", "embedding", "prompt"],
        "Technology Infrastructure": ["docker", "kubernetes", "api", "database", "deploy", "server"],
        "Oil & Gas Construction": ["pipeline", "turnaround", "commissioning", "fabrication", "welder", "inspector"],
        "Architecture/Systems": ["architecture", "schema", "graph", "harmonic", "toroidal", "codec"],
        "Content/Marketing": ["linkedin", "facebook", "post", "content", "engagement", "follower"],
        "Business Strategy": ["revenue", "pricing", "market", "customer", "product", "launch"],
        "Workforce/Hiring": ["hiring", "contractor", "trades", "certification", "workforce"],
    }

    topic_counts: dict[str, int] = {}
    for msg in messages:
        text_lower = msg.text.lower()
        for topic, keywords in topic_keywords.items():
            if sum(1 for kw in keywords if kw in text_lower) >= 2:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1

    topics = [
        {"name": t, "mention_count": c, "confidence": min(1.0, c / 50)}
        for t, c in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    return {"topics": topics, "total_topics": len(topics), "total_messages_analyzed": len(messages)}


def process_conversation_export(
    data: list[dict],
    source_type: str,  # "claude" or "chatgpt"
) -> tuple[list[UserMessage], dict[str, Any], dict[str, Any]]:
    """Process a conversation export: extract messages, build fingerprint and belief graph."""
    if source_type == "claude":
        messages = extract_claude_messages(data)
    elif source_type == "chatgpt":
        messages = extract_chatgpt_messages(data)
    else:
        messages = []

    fingerprint = build_style_fingerprint(messages)
    beliefs = build_belief_graph(messages)

    return messages, fingerprint, beliefs


def merge_fingerprints(fingerprints: list[dict]) -> dict[str, Any]:
    """Merge multiple StyleFingerprints (from different sources) into one."""
    if not fingerprints:
        return {}
    if len(fingerprints) == 1:
        return fingerprints[0]

    # Merge openers
    merged_openers: Counter = Counter()
    merged_phrases: Counter = Counter()
    total_messages = 0
    total_short = 0
    total_medium = 0
    total_long = 0
    total_questions = 0
    all_sources: Counter = Counter()

    for fp in fingerprints:
        n = fp.get("structure", {}).get("total_messages", 0)
        total_messages += n

        for k, v in fp.get("vocabulary", {}).get("top_openers", {}).items():
            merged_openers[k] += v
        for k, v in fp.get("vocabulary", {}).get("signature_phrases", {}).items():
            merged_phrases[k] += v

        total_short += fp.get("structure", {}).get("short_pct", 0) * n / 100
        total_medium += fp.get("structure", {}).get("medium_pct", 0) * n / 100
        total_long += fp.get("structure", {}).get("long_pct", 0) * n / 100
        total_questions += fp.get("structure", {}).get("question_rate", 0) * n

        for src, cnt in fp.get("sources", {}).items():
            all_sources[src] += cnt

    n = total_messages or 1
    return {
        "vocabulary": {
            "top_openers": dict(merged_openers.most_common(20)),
            "signature_phrases": dict(merged_phrases.most_common(20)),
        },
        "structure": {
            "total_messages": total_messages,
            "median_word_count": sum(fp.get("structure", {}).get("median_word_count", 0) for fp in fingerprints) // len(fingerprints),
            "short_pct": round(total_short / n * 100, 1),
            "medium_pct": round(total_medium / n * 100, 1),
            "long_pct": round(total_long / n * 100, 1),
            "question_rate": round(total_questions / n, 3),
        },
        "tone": {
            "formality": round(sum(fp.get("tone", {}).get("formality", 0) for fp in fingerprints) / len(fingerprints), 3),
            "directness": round(1 - total_questions / n, 3),
            "tech_density": round(sum(fp.get("tone", {}).get("tech_density", 0) for fp in fingerprints) / len(fingerprints), 4),
            "industry_density": round(sum(fp.get("tone", {}).get("industry_density", 0) for fp in fingerprints) / len(fingerprints), 4),
        },
        "sources": dict(all_sources),
    }
