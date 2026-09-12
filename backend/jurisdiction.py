import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, Pattern

REGISTRY_DIR = Path(__file__).resolve().parent / "data" / "jurisdiction_registry"

_REGISTRY_CACHE: Dict[str, Dict[str, Any]] = {}


def load_registry(force_reload: bool = False) -> Dict[str, Dict[str, Any]]:
    """Loads all JSON jurisdiction registries from backend/data/jurisdiction_registry/."""
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE and not force_reload:
        return _REGISTRY_CACHE

    loaded = {}
    if REGISTRY_DIR.exists():
        for json_file in REGISTRY_DIR.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    slug = data.get("slug", json_file.stem)
                    loaded[slug] = data
            except Exception as e:
                print(f"[Jurisdiction] Warning: failed to load {json_file}: {e}")

    # Ensure default exists
    if "_default" not in loaded:
        loaded["_default"] = {
            "slug": "_default",
            "name": "Generic Jurisdiction",
            "legal_corpus_available": False,
            "default_authority": "Municipal Commissioner / Chief Executive Officer of the local urban local body having jurisdiction over the affected area (verify via local municipal office)"
        }

    _REGISTRY_CACHE = loaded
    return _REGISTRY_CACHE


def normalize_jurisdiction(text: Optional[str]) -> str:
    """
    Normalizes a text string, hint, or document excerpt to a registered jurisdiction slug.
    Rule: Picks the LONGEST matching alias across all registries to guarantee specificity.
    Falls back to '_default' if no alias matches.
    """
    if not text:
        return "_default"

    text_lower = text.lower()
    registry = load_registry()

    best_match_slug = "_default"
    max_len = 0

    for slug, conf in registry.items():
        if slug == "_default":
            continue
        aliases = conf.get("aliases", [])
        for alias in aliases:
            a_lower = alias.lower()
            # Check for word boundary or direct inclusion
            pattern = rf"\b{re.escape(a_lower)}\b"
            if re.search(pattern, text_lower):
                if len(a_lower) > max_len:
                    max_len = len(a_lower)
                    best_match_slug = slug

    return best_match_slug


def has_legal_corpus(jurisdiction_slug: str) -> bool:
    """Checks if the given jurisdiction slug has an indexed statutory legal corpus."""
    registry = load_registry()
    conf = registry.get(jurisdiction_slug)
    if conf:
        return bool(conf.get("legal_corpus_available", False))
    return False


def build_jurisdiction_regex() -> Pattern:
    """
    Dynamically compiles a regex pattern matching any letterhead, issuing authority,
    or key institution across all registered jurisdictions. Zero hardcoded institution strings!
    """
    registry = load_registry()
    patterns = set()

    for slug, conf in registry.items():
        for p in conf.get("letterhead_patterns", []):
            patterns.add(re.escape(p))
        for p in conf.get("aliases", []):
            if len(p) > 3:  # avoid tiny acronym collisions
                patterns.add(re.escape(p))

    if not patterns:
        patterns.add(r"Municipal\s+Corporation")

    # Sort descending by length to ensure longest tokens match first
    sorted_patterns = sorted(patterns, key=lambda x: len(x), reverse=True)
    combined = "|".join(sorted_patterns)
    return re.compile(rf"(?i)\b(?:{combined})\b")


def resolve_addressee(jurisdiction_slug: str, ward: Optional[str] = None) -> str:
    """
    Resolves the fallback addressee for objections when document has no stated authority or authority was rejected.
    Uses ward_to_authority if ward matches, otherwise jurisdiction's default_authority.
    Uses strict word boundary / exact key matching, not loose substring containment.
    """
    registry = load_registry()
    conf = registry.get(jurisdiction_slug, registry["_default"])

    if ward:
        w_norm = re.sub(r"[\s\-]+", "_", ward.lower().strip())
        w_tokens = [t for t in re.split(r"[_\s\-]+", ward.lower().strip()) if t]
        ward_map = conf.get("ward_to_authority", {})

        for key, authority in ward_map.items():
            k_norm = re.sub(r"[\s\-]+", "_", key.lower().strip())
            # Exact match, token equality, or delimited word boundary match
            if k_norm == w_norm or k_norm in w_tokens or f"_{k_norm}_" in f"_{w_norm}_":
                return authority

    # Fallback to jurisdiction's default authority, or global default
    raw_auth = conf.get("default_authority") or registry["_default"]["default_authority"]
    j_name = conf.get("name", jurisdiction_slug)
    return raw_auth.replace("{jurisdiction_hint}", j_name)
