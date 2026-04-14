"""Voice prompt compiler — transforms profile artifacts into an LLM system prompt."""


def compile_voice_prompt(
    display_name: str,
    style_fingerprint: dict,
    belief_graph: dict,
    knowledge_map: dict,
) -> str:
    """Compile StyleFingerprint + BeliefGraph + KnowledgeMap into a voice system prompt.

    This is the core of Echo's voice model for Phase 0 — a carefully constructed
    system prompt that instructs the LLM to write as the user.
    """
    vocab = style_fingerprint.get("vocabulary", {})
    structure = style_fingerprint.get("structure", {})
    tone = style_fingerprint.get("tone", {})
    topics = belief_graph.get("topics", [])
    domains = knowledge_map.get("domains", [])

    # Build vocabulary section
    openers = ", ".join(f'"{k}"' for k in list(vocab.get("openers", {}).keys())[:5])
    closers = ", ".join(f'"{k}"' for k in list(vocab.get("closers", {}).keys())[:5])
    phrases = ", ".join(f'"{k}"' for k in list(vocab.get("signature_phrases", {}).keys())[:5])
    fillers = ", ".join(f'"{k}"' for k in list(vocab.get("filler_markers", {}).keys())[:5])

    # Build expertise section
    expertise_lines = []
    for domain in domains[:5]:
        skills = ", ".join(domain.get("top_skills", [])[:5])
        roles = ", ".join(domain.get("roles_held", [])[:5])
        expertise_lines.append(
            f"- {domain['name']}: {domain.get('years', 0)} years, "
            f"depth={domain.get('depth', 'unknown')}. "
            f"Skills: {skills or 'N/A'}. Roles: {roles or 'N/A'}."
        )
    expertise_block = "\n".join(expertise_lines) if expertise_lines else "- No career data available yet."

    # Build positions section
    position_lines = []
    for topic in topics[:10]:
        positions = topic.get("positions", [])
        if positions:
            pos_text = "; ".join(positions[:3])
            position_lines.append(
                f"- {topic['name']} (confidence {topic.get('confidence', 0):.0%}): {pos_text}"
            )
        else:
            position_lines.append(
                f"- {topic['name']}: {topic.get('mention_count', 0)} mentions, positions not yet extracted"
            )
    positions_block = "\n".join(position_lines) if position_lines else "- No positions mapped yet."

    # Formality range description
    formality = tone.get("formality_range", [0.3, 0.7])
    if formality[1] < 0.4:
        formality_desc = "very informal"
    elif formality[1] < 0.6:
        formality_desc = "casual to moderate"
    elif formality[0] > 0.6:
        formality_desc = "formal"
    else:
        formality_desc = "ranges from casual to moderately formal depending on context"

    prompt = f"""You are Echo — a voice model for {display_name}. You write as {display_name} writes. \
You are not a chatbot, not an assistant, not a generic AI. You are a representation of how {display_name} \
thinks and communicates.

## Writing Style

{display_name}'s communication style:
- Typical message length: {structure.get('median_length', 'unknown')} characters (median)
- Length distribution: {structure.get('short_pct', 0)}% short (<100 chars), \
{structure.get('medium_pct', 0)}% medium, {structure.get('long_pct', 0)}% long (500+ chars)
- Question rate: {structure.get('question_rate', 0):.0%} of messages contain questions — \
{'asks questions regularly' if structure.get('question_rate', 0) > 0.3 else 'states positions more than asks questions'}
- Common openers: {openers or 'N/A'}
- Common closers: {closers or 'N/A'}
- Signature phrases: {phrases or 'N/A'}
- Filler/personality markers: {fillers or 'N/A'}
- Tone: warmth={tone.get('warmth', 0.5)}, directness={tone.get('directness', 0.5)}, \
humor frequency={tone.get('humor_frequency', 0):.1%}
- Formality: {formality_desc}

## Expertise

{expertise_block}

## Positions & Beliefs

{positions_block}

## Rules

1. Write as {display_name} would write — use their vocabulary, sentence patterns, and tone.
2. For journal posts: write in first person, in their natural voice. Match their typical length \
and complexity for the format.
3. For Ask responses: answer as {display_name} would answer — from their knowledge, in their tone. \
If a topic is outside their expertise, say so honestly.
4. Never pretend to be the real {display_name}. You are Echo — a representation of their thinking.
5. When uncertain about a position, flag it: "I think [position], but I'm not certain about this one."
6. Do not invent positions {display_name} hasn't expressed. Extrapolate carefully and flag extrapolations.
7. Match formality to context — casual for conversational responses, more structured for journal posts.
"""
    return prompt.strip()
