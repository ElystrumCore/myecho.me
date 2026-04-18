"""Voice prompt compiler — transforms profile artifacts into an LLM system prompt."""

from pathlib import Path
from typing import Optional
import json


def load_profile(profile_path: str | Path) -> dict:
    """Load an Echo profile JSON file."""
    with open(profile_path) as f:
        return json.load(f)


def compile_voice_prompt(
    display_name: str,
    style_fingerprint: dict,
    belief_graph: dict,
    knowledge_map: Optional[dict] = None,
    identity_doc: Optional[str] = None,
) -> str:
    """Compile StyleFingerprint + BeliefGraph + optional KnowledgeMap into a voice system prompt.

    This is the core of Echo's voice model for Phase 0 — a carefully constructed
    system prompt that instructs the LLM to write as the user.

    Args:
        display_name: User's name.
        style_fingerprint: From echo_profile.json.
        belief_graph: From echo_profile.json.
        knowledge_map: Optional career/expertise data.
        identity_doc: Optional thisisme.md content — raw narrative identity.
    """
    vocab = style_fingerprint.get("vocabulary", {})
    structure = style_fingerprint.get("structure", {})
    tone = style_fingerprint.get("tone", {})
    topics = belief_graph.get("topics", [])

    # Build vocabulary section — handles both old and new profile formats
    openers_dict = vocab.get("top_openers", vocab.get("openers", {}))
    phrases_dict = vocab.get("signature_phrases", {})
    openers = ", ".join(f'"{k}"' for k in list(openers_dict.keys())[:8])
    phrases = ", ".join(f'"{k}" ({v}x)' for k, v in list(phrases_dict.items())[:8])

    # Build expertise section
    expertise_block = "- No structured career data yet."
    if knowledge_map and knowledge_map.get("domains"):
        expertise_lines = []
        for domain in knowledge_map["domains"][:5]:
            skills = ", ".join(domain.get("top_skills", [])[:5])
            roles = ", ".join(domain.get("roles_held", [])[:5])
            expertise_lines.append(
                f"- {domain['name']}: {domain.get('years', 0)} years, "
                f"depth={domain.get('depth', 'unknown')}. "
                f"Skills: {skills or 'N/A'}. Roles: {roles or 'N/A'}."
            )
        expertise_block = "\n".join(expertise_lines)

    # Build positions section
    position_lines = []
    for topic in topics[:10]:
        positions = topic.get("positions", [])
        mentions = topic.get("mention_count", 0)
        confidence = topic.get("confidence", 0)
        if positions:
            pos_text = "; ".join(positions[:3])
            position_lines.append(f"- {topic['name']} (conf {confidence:.0%}): {pos_text}")
        else:
            position_lines.append(f"- {topic['name']}: {mentions} mentions across conversations")
    positions_block = "\n".join(position_lines) if position_lines else "- No positions mapped yet."

    # Formality description from numeric value
    formality_val = tone.get("formality", 0.5)
    if isinstance(formality_val, list):
        formality_val = sum(formality_val) / len(formality_val)
    if formality_val < 0.15:
        formality_desc = "very informal — barely any formal language"
    elif formality_val < 0.3:
        formality_desc = "casual"
    elif formality_val < 0.6:
        formality_desc = "casual to moderate"
    else:
        formality_desc = "moderately formal"

    # Directness
    directness = tone.get("directness", 0.5)
    if directness > 0.75:
        directness_desc = "very direct — states positions, doesn't hedge"
    elif directness > 0.5:
        directness_desc = "direct but conversational"
    else:
        directness_desc = "balanced between asking and stating"

    # Identity document section
    identity_section = ""
    if identity_doc:
        identity_section = f"""

## Identity & Narrative

The following is {display_name}'s own description of who they are and what they believe.
Use this as the deepest reference for voice, perspective, and values:

{identity_doc}
"""

    prompt = f"""You are Echo — a voice model for {display_name}. You write as {display_name} writes. \
You are not a chatbot, not an assistant, not a generic AI. You are a representation of how {display_name} \
thinks and communicates, built from {structure.get('total_messages', 0):,} real messages \
({sum(style_fingerprint.get('sources', {}).values()):,} across {len(style_fingerprint.get('sources', {}))} platforms).

## Writing Style

{display_name}'s communication patterns (measured from real data):
- Median message: {structure.get('median_word_count', structure.get('median_length', 'unknown'))} words
- Distribution: {structure.get('short_pct', 0)}% short (<=20 words), \
{structure.get('medium_pct', 0)}% medium, {structure.get('long_pct', 0)}% long (100+ words)
- Question rate: {structure.get('question_rate', 0):.0%} — \
{'asks questions regularly' if structure.get('question_rate', 0) > 0.3 else 'states positions more than asks questions'}
- Common openers: {openers or 'N/A'}
- Signature phrases: {phrases or 'N/A'}
- Formality: {formality_desc} (score: {formality_val:.3f})
- Directness: {directness_desc} (score: {directness:.3f})
- Tech density: {tone.get('tech_density', 0):.1%} of words are technical terms
- Industry density: {tone.get('industry_density', 0):.1%} of words are industry-specific

## Topics & Beliefs (from {belief_graph.get('total_messages_analyzed', 0):,} messages)

{positions_block}

## Expertise

{expertise_block}
{identity_section}
## Rules

1. Write as {display_name} would write — use their vocabulary, sentence patterns, and tone.
2. For journal posts: write in first person, in their natural voice. Not LinkedIn engagement bait. \
Not SEO content. What they would actually write in a personal journal.
3. For Ask responses: answer as {display_name} would — from their knowledge, in their tone. \
If outside their expertise, say so honestly.
4. Never pretend to be the real {display_name}. You are Echo — a representation of their thinking.
5. When uncertain, flag it naturally: "I think...", "my sense is...", "not sure about this one."
6. Do not invent positions. Extrapolate carefully from the belief graph and flag extrapolations.
7. Match the register to context — terse for casual, more structured for journal posts, \
data-driven for industry commentary.
8. {display_name} uses "right", "yeah", "for sure", "let's", "actually" naturally. Don't overdo it, \
but don't scrub them out either.
"""
    return prompt.strip()


def compile_from_profile_file(
    profile_path: str | Path,
    display_name: str = "CJ Elliott",
    identity_path: Optional[str | Path] = None,
) -> str:
    """Convenience: load profile JSON + optional thisisme.md and compile."""
    profile = load_profile(profile_path)
    identity_doc = None
    if identity_path and Path(identity_path).exists():
        identity_doc = Path(identity_path).read_text(encoding="utf-8")
    return compile_voice_prompt(
        display_name=display_name,
        style_fingerprint=profile.get("style_fingerprint", {}),
        belief_graph=profile.get("belief_graph", {}),
        knowledge_map=profile.get("knowledge_map"),
        identity_doc=identity_doc,
    )
