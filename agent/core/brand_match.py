"""Brand / model matching — owns the brand registry shared by skills + harness.

Originally this state lived in ``harness/line_ui_factory`` and was imported by
``skills/tools.py``, which created a reverse dependency
(``skills → harness``). RP2.2 moves the state and the pure matching helpers
here so:

  * ``skills.tools`` imports ``core.brand_match`` (clean: leaf → core)
  * ``harness.line_ui_factory`` imports ``core.brand_match`` and provides
    LINE-Quick-Reply specific UI helpers on top.

The registry is loaded once at app startup via ``set_brands()`` and is read
by both layers thereafter.
"""

from __future__ import annotations

# Module-level state — populated once at app startup via ``set_brands()``.
# Both ``harness.line_ui_factory.init_quick_reply()`` and any test harness
# should call ``set_brands()`` before requesting matches.
_brand_items: list[dict] = []
_brand_models: dict[str, list[str]] = {}


def set_brands(brand_items: list[dict]) -> None:
    """Inject the canonical brand list (from config.toml ``[quick_reply.brands]``).

    Each dict should have ``text`` (the canonical brand name) and optionally
    ``models`` (a list of model names). Calling this overwrites the previous
    state and rebuilds the brand→models index.
    """
    global _brand_items, _brand_models
    _brand_items = list(brand_items)
    _brand_models = {
        b["text"]: list(b["models"])
        for b in brand_items
        if b.get("models")
    }


def match_brand(text: str) -> str | None:
    """Return the canonical brand name if ``text`` exactly matches one (case-insensitive)."""
    text_lower = text.strip().lower()
    for b in _brand_items:
        if text_lower == b["text"].lower():
            return b["text"]
    return None


def match_model(brand: str, text: str) -> str | None:
    """Return the canonical model name if ``text`` exactly matches a model under ``brand``."""
    models = _brand_models.get(brand, [])
    text_stripped = text.strip()
    for m in models:
        if text_stripped == m:
            return m
    return None


def get_brand_models(brand: str) -> list[str]:
    """Return the model list for ``brand`` (empty list if brand unknown / no models)."""
    return list(_brand_models.get(brand, []))


def get_all_brand_models() -> dict[str, list[str]]:
    """Return a defensive copy of the full ``brand → models`` index."""
    return {k: list(v) for k, v in _brand_models.items()}


def get_brand_items() -> list[dict]:
    """Return a defensive copy of the raw brand items (for UI builders that need ``label``)."""
    return [dict(b) for b in _brand_items]


def infer_brand_from_text(text: str) -> tuple[str | None, str | None]:
    """Scan free-form text for a known model (preferred) or brand name.

    Model match wins because it disambiguates the brand for free; brand
    fallback returns ``(brand, None)``.
    """
    for brand, models in _brand_models.items():
        for m in models:
            if m in text:
                return brand, m
    text_lower = text.lower()
    for b in _brand_items:
        if b["text"].lower() in text_lower:
            return b["text"], None
    return None, None
