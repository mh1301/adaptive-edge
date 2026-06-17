"""
OHLCV Cache — Reduce API calls by caching candle data.
"""

import time
from typing import Dict, List, Optional

_cache: Dict[str, Dict] = {}
DEFAULT_TTL = 60  # seconds


def get(key: str) -> Optional[List[Dict]]:
    """Get cached data if not expired."""
    if key in _cache:
        entry = _cache[key]
        if time.time() - entry["ts"] < entry.get("ttl", DEFAULT_TTL):
            return entry["data"]
        del _cache[key]
    return None


def put(key: str, data: List[Dict], ttl: int = DEFAULT_TTL):
    """Cache data with timestamp."""
    _cache[key] = {"data": data, "ts": time.time(), "ttl": ttl}


def clear():
    """Clear all cache."""
    _cache.clear()


def stats() -> Dict:
    """Cache statistics."""
    now = time.time()
    valid = sum(1 for v in _cache.values() if now - v["ts"] < v["ttl"])
    return {"total_entries": len(_cache), "valid_entries": valid, "expired": len(_cache) - valid}
