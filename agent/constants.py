from __future__ import annotations


DEFAULT_STYLE = "clean deterministic vector rendering"
DEFAULT_TITLE_BY_CAPABILITY = {
    "feedback": "Validation Badge",
    "memory": "Image Agent Benchmark",
    "plan": "Context Gap Toolkit",
    "reason": "Reasoning Result",
    "search": "Image-Agent",
}
MEMORY_VISUAL_KEYS = {
    "accent_color",
    "color",
    "density",
    "palette",
    "spacing",
    "tone",
    "typography",
}
STOPWORDS = {
    "a",
    "about",
    "agent",
    "and",
    "badge",
    "card",
    "create",
    "exact",
    "for",
    "image",
    "of",
    "project",
    "result",
    "shows",
    "small",
    "that",
    "the",
    "using",
    "validation",
    "with",
}
VARIANT_CONFIGS = (
    {
        "focus": "balanced hierarchy with comfortable spacing",
        "density": "comfortable",
        "accent": "#2563eb",
        "panel_fill": "#dbeafe",
    },
    {
        "focus": "compact hierarchy with stronger title emphasis",
        "density": "compact",
        "accent": "#7c3aed",
        "panel_fill": "#ede9fe",
    },
)
