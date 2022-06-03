"""Stores a cached version of displayed items with the last update time. Can be accessed by the rest of the application as a global instance"""

import time


class CachedLeaderboard:
    """Object holding the last update of the leaderboard and the leaderboard items received in the leaderboard.html template"""

    last_update: float = time.time()
    leaderboard: dict = None
