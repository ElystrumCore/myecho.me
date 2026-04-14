"""Theme generation engine — natural language to visual identity."""

import json

from echo.engine.voice import generate_text

# --- Base theme presets ---
# 5 starter themes as defined in CLAUDE.md. Each is a complete ThemeConfig.config value.

BASE_THEMES: dict[str, dict] = {
    "dark": {
        "colors": {
            "bg_primary": "#0d0d0d",
            "bg_secondary": "#151515",
            "text_primary": "#e0e0e0",
            "text_secondary": "#808080",
            "accent": "#7eb8da",
            "accent_secondary": "#a0d0f0",
        },
        "typography": {
            "heading_font": "Georgia",
            "body_font": "Georgia",
            "mono_font": "JetBrains Mono",
            "base_size": "17px",
            "scale_ratio": 1.25,
        },
        "layout": {
            "max_width": "680px",
            "component_order": ["stream", "positions", "ask", "timeline", "about"],
            "sidebar": False,
            "header_style": "minimal",
        },
        "vibe": {
            "border_radius": "4px",
            "shadow_intensity": "none",
            "texture": "none",
            "mood": "clean",
        },
    },
    "light": {
        "colors": {
            "bg_primary": "#fafaf9",
            "bg_secondary": "#f5f5f4",
            "text_primary": "#1c1917",
            "text_secondary": "#78716c",
            "accent": "#2563eb",
            "accent_secondary": "#3b82f6",
        },
        "typography": {
            "heading_font": "Georgia",
            "body_font": "Georgia",
            "mono_font": "JetBrains Mono",
            "base_size": "17px",
            "scale_ratio": 1.25,
        },
        "layout": {
            "max_width": "680px",
            "component_order": ["stream", "positions", "ask", "timeline", "about"],
            "sidebar": False,
            "header_style": "minimal",
        },
        "vibe": {
            "border_radius": "6px",
            "shadow_intensity": "subtle",
            "texture": "none",
            "mood": "airy",
        },
    },
    "minimal": {
        "colors": {
            "bg_primary": "#ffffff",
            "bg_secondary": "#fafafa",
            "text_primary": "#111111",
            "text_secondary": "#999999",
            "accent": "#111111",
            "accent_secondary": "#444444",
        },
        "typography": {
            "heading_font": "Helvetica Neue",
            "body_font": "Helvetica Neue",
            "mono_font": "SF Mono",
            "base_size": "16px",
            "scale_ratio": 1.2,
        },
        "layout": {
            "max_width": "600px",
            "component_order": ["stream", "ask", "about"],
            "sidebar": False,
            "header_style": "hidden",
        },
        "vibe": {
            "border_radius": "0px",
            "shadow_intensity": "none",
            "texture": "none",
            "mood": "stark",
        },
    },
    "warm": {
        "colors": {
            "bg_primary": "#1a1410",
            "bg_secondary": "#231d17",
            "text_primary": "#e8ddd0",
            "text_secondary": "#a89882",
            "accent": "#d4a574",
            "accent_secondary": "#e8c49a",
        },
        "typography": {
            "heading_font": "Playfair Display",
            "body_font": "Lora",
            "mono_font": "Fira Code",
            "base_size": "18px",
            "scale_ratio": 1.333,
        },
        "layout": {
            "max_width": "720px",
            "component_order": ["stream", "positions", "timeline", "ask", "about"],
            "sidebar": False,
            "header_style": "classic",
        },
        "vibe": {
            "border_radius": "8px",
            "shadow_intensity": "warm",
            "texture": "paper",
            "mood": "leather-bound",
        },
    },
    "editorial": {
        "colors": {
            "bg_primary": "#0a0f1a",
            "bg_secondary": "#111827",
            "text_primary": "#e5e7eb",
            "text_secondary": "#9ca3af",
            "accent": "#00FFF0",
            "accent_secondary": "#7B61FF",
        },
        "typography": {
            "heading_font": "Space Grotesk",
            "body_font": "Inter",
            "mono_font": "JetBrains Mono",
            "base_size": "16px",
            "scale_ratio": 1.25,
        },
        "layout": {
            "max_width": "720px",
            "component_order": ["stream", "positions", "ask", "timeline", "about"],
            "sidebar": False,
            "header_style": "minimal",
        },
        "vibe": {
            "border_radius": "0px",
            "shadow_intensity": "none",
            "texture": "grid",
            "mood": "industrial",
        },
    },
}


def get_base_theme(name: str) -> dict:
    """Get a base theme by name. Falls back to 'dark' if not found."""
    return BASE_THEMES.get(name, BASE_THEMES["dark"]).copy()


def generate_theme(
    description: str,
    style_fingerprint: dict | None = None,
) -> dict:
    """Generate a theme config from a natural language description.

    Uses the LLM to translate a description like "dark theme, industrial feel,
    monospace fonts, no curves" into a complete theme config JSON.

    If a StyleFingerprint is provided, the generation is informed by the user's
    communication style — a terse, direct communicator gets a cleaner layout.
    """
    style_context = ""
    if style_fingerprint:
        tone = style_fingerprint.get("tone", {})
        structure = style_fingerprint.get("structure", {})
        style_context = f"""
The user's communication style (use this to inform the visual design):
- Directness: {tone.get('directness', 0.5)} (1.0 = very direct)
- Warmth: {tone.get('warmth', 0.5)}
- Formality range: {tone.get('formality_range', [0.3, 0.7])}
- Typical message length: {structure.get('median_length', 'unknown')} chars
- Humor frequency: {tone.get('humor_frequency', 0)}

A direct, terse communicator should get a clean, uncluttered layout.
A warm, verbose writer might suit a more ornate, generous design.
"""

    prompt = f"""Generate a theme configuration for a personal journal website.

The user describes their desired look as: "{description}"

{style_context}

Return ONLY a valid JSON object with this exact structure (no markdown, no explanation):
{{
  "colors": {{
    "bg_primary": "#hex",
    "bg_secondary": "#hex",
    "text_primary": "#hex",
    "text_secondary": "#hex",
    "accent": "#hex",
    "accent_secondary": "#hex"
  }},
  "typography": {{
    "heading_font": "font name",
    "body_font": "font name",
    "mono_font": "font name",
    "base_size": "Npx",
    "scale_ratio": 1.25
  }},
  "layout": {{
    "max_width": "Npx",
    "component_order": ["stream", "positions", "ask", "timeline", "about"],
    "sidebar": false,
    "header_style": "minimal|classic|hidden"
  }},
  "vibe": {{
    "border_radius": "Npx",
    "shadow_intensity": "none|subtle|warm|dramatic",
    "texture": "none|grid|paper|noise",
    "mood": "one-word description"
  }}
}}

Use web-safe or Google Fonts names. Ensure sufficient contrast between text and background colors.
The design should feel like a personal journal, not a corporate website or social media feed."""

    # Use a simpler system prompt for theme generation — not the voice model
    system = (
        "You are a web design assistant. You generate theme configurations as JSON. "
        "You have excellent taste — clean, readable, distinctive. Never generic. "
        "Return only the JSON object, no other text."
    )

    raw = generate_text(system, prompt, max_tokens=1024)

    # Parse the JSON from the response
    # Strip any markdown fencing if the model wrapped it
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    return json.loads(text)


def theme_to_css_vars(config: dict) -> str:
    """Convert a theme config JSON into CSS custom property declarations.

    This is what gets injected into the page <style> tag to apply the theme.
    """
    colors = config.get("colors", {})
    typography = config.get("typography", {})
    layout = config.get("layout", {})
    vibe = config.get("vibe", {})

    lines = [":root {"]

    # Colors
    for key, value in colors.items():
        css_name = key.replace("_", "-")
        lines.append(f"    --{css_name}: {value};")

    # Typography
    if typography.get("heading_font"):
        lines.append(f"    --font-heading: '{typography['heading_font']}', serif;")
    if typography.get("body_font"):
        lines.append(f"    --font-body: '{typography['body_font']}', serif;")
    if typography.get("mono_font"):
        lines.append(f"    --font-mono: '{typography['mono_font']}', monospace;")
    if typography.get("base_size"):
        lines.append(f"    --base-size: {typography['base_size']};")

    # Layout
    if layout.get("max_width"):
        lines.append(f"    --max-width: {layout['max_width']};")

    # Vibe
    if vibe.get("border_radius"):
        lines.append(f"    --border-radius: {vibe['border_radius']};")

    lines.append("}")
    return "\n".join(lines)
