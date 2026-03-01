"""Price caching layer.

Thin convenience wrapper around the cache helpers in db.database.
Import this module when you want a cleaner API for price caching.
"""

from db.database import get_cached_prices, save_price_cache

__all__ = ["get_cached_prices", "save_price_cache"]
