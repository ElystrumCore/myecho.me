"""
Test Echo voice engine end-to-end.

Loads the real profile, compiles the voice prompt, and generates
content in CJ's voice using the Anthropic API.

Usage:
    python scripts/test_echo_voice.py                           # Run all tests
    python scripts/test_echo_voice.py --ask "What do you think about AI in construction?"
    python scripts/test_echo_voice.py --journal "the inspector bottleneck"
    python scripts/test_echo_voice.py --prompt-only              # Just show the compiled prompt
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

PROFILE_PATH = Path(__file__).parent.parent / "data" / "profile" / "echo_profile.json"
IDENTITY_PATH = Path(__file__).parent.parent / "thisisme.md"


def main():
    parser = argparse.ArgumentParser(description="Test Echo voice engine")
    parser.add_argument("--ask", help="Ask Echo a question")
    parser.add_argument("--journal", help="Generate a journal post on a topic")
    parser.add_argument("--prompt-only", action="store_true", help="Just show the compiled prompt")
    parser.add_argument("--model", default="claude-sonnet-4-20250514", help="LLM model to use")
    args = parser.parse_args()

    # Check API key
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key and not args.prompt_only:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

    # Compile voice prompt
    from echo.profile.compiler import compile_from_profile_file

    print("Loading profile and compiling voice prompt...")
    voice_prompt = compile_from_profile_file(
        profile_path=PROFILE_PATH,
        display_name="CJ Elliott",
        identity_path=IDENTITY_PATH,
    )

    print(f"Voice prompt: {len(voice_prompt)} chars")
    print()

    if args.prompt_only:
        print("=== COMPILED VOICE PROMPT ===")
        print(voice_prompt)
        return

    # Override settings
    os.environ.setdefault("ECHO_ANTHROPIC_API_KEY", api_key)
    os.environ.setdefault("ECHO_LLM_MODEL", args.model)

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    if args.ask:
        print(f"=== ASK: {args.ask} ===")
        print()
        response = client.messages.create(
            model=args.model,
            max_tokens=1024,
            system=voice_prompt,
            messages=[{
                "role": "user",
                "content": (
                    f'Someone is asking you a question on your public journal page:\n\n'
                    f'"{args.ask}"\n\n'
                    'Answer as yourself — in your natural voice, from your knowledge and positions. '
                    'If you don\'t know something, say so honestly. Keep it conversational but substantive.'
                ),
            }],
        )
        print(response.content[0].text)
        return

    if args.journal:
        print(f"=== JOURNAL: {args.journal} ===")
        print()
        response = client.messages.create(
            model=args.model,
            max_tokens=2048,
            system=voice_prompt,
            messages=[{
                "role": "user",
                "content": (
                    f'Write a journal post about: {args.journal}\n\n'
                    'Write naturally in first person. This is for your personal journal/blog — '
                    'not a LinkedIn post, not SEO content, not engagement bait. '
                    'Write what you actually think about this topic, in your natural voice. '
                    'Keep it honest and substantive. Include a title.'
                ),
            }],
        )
        print(response.content[0].text)
        return

    # Default: run both tests
    print("=== TEST 1: Ask Mode ===")
    print('Question: "What do you think about AI replacing trades workers?"')
    print()

    response = client.messages.create(
        model=args.model,
        max_tokens=1024,
        system=voice_prompt,
        messages=[{
            "role": "user",
            "content": (
                'Someone is asking you a question on your public journal page:\n\n'
                '"What do you think about AI replacing trades workers?"\n\n'
                'Answer as yourself — in your natural voice, from your knowledge and positions. '
                'Keep it conversational but substantive.'
            ),
        }],
    )
    print(response.content[0].text)

    print()
    print("=" * 60)
    print()
    print("=== TEST 2: Journal Mode ===")
    print("Topic: Why I started building AI systems after 20 years in construction")
    print()

    response2 = client.messages.create(
        model=args.model,
        max_tokens=2048,
        system=voice_prompt,
        messages=[{
            "role": "user",
            "content": (
                'Write a journal post about: Why I started building AI systems after 20 years in construction\n\n'
                'Write naturally in first person. This is for your personal journal/blog. '
                'Write what you actually think. Keep it honest and substantive. Include a title.'
            ),
        }],
    )
    print(response2.content[0].text)


if __name__ == "__main__":
    main()
