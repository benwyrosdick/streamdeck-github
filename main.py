# Import StreamController modules
from src.backend.PluginManager.PluginBase import PluginBase
from src.backend.PluginManager.ActionHolder import ActionHolder
from src.backend.PluginManager.ActionInputSupport import ActionInputSupport
from src.backend.DeckManagement.InputIdentifier import Input

import time
import threading

# Relative imports anchor every module to this plugin's package. Absolute
# top-level names like `actions`/`backend` would collide with the identically
# named packages other installed plugins register in sys.modules.
from .backend.github_backend import GitHubBackend

from .actions.PRCount.PRCount import PRCount


class GitHubPlugin(PluginBase):
    def __init__(self):
        super().__init__()

        self.lm = self.locale_manager
        self.backend = GitHubBackend()

        # Per-query count cache. Counts hit the network, so they must never run
        # on the UI thread: get_count() returns the cached value immediately and
        # refreshes in the background. Keyed by the full search query string so
        # buttons with different filters don't clobber each other, and identical
        # buttons share one fetch.
        self._counts = {}          # query -> {"value": int|None, "ts": float}
        self._inflight = set()     # queries with a fetch currently running
        self._counts_lock = threading.Lock()

        # Register actions
        self.pr_count_holder = ActionHolder(
            plugin_base=self,
            action_base=PRCount,
            action_id_suffix="PRCount",
            action_name=self.lm.get("actions.pr-count.name"),
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNTESTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            },
        )
        self.add_action_holder(self.pr_count_holder)

        # Register plugin
        self.register(
            plugin_name=self.lm.get("plugin.name"),
            github_repo="https://github.com/benwyrosdick/streamdeck-github",
            plugin_version="1.0.0",
            app_version="1.5.0-beta.14",
        )

    # ------------------------------------------------------------------ #
    # Asynchronous, cached PR counts
    # ------------------------------------------------------------------ #
    def get_count(self, query: str, max_age: float = 45.0):
        """Return the most recent count for `query` (or None if not fetched yet).

        Never blocks: if the cached value is missing or older than
        max_age_seconds, a background refresh is kicked off and the stale value
        (or None) is returned immediately. Failures are cached too, so a broken
        `gh` doesn't get hammered every tick.
        """
        if not query:
            return None
        now = time.monotonic()
        with self._counts_lock:
            entry = self._counts.get(query)
            fresh = entry is not None and (now - entry["ts"]) < max_age
            if not fresh and query not in self._inflight:
                self._inflight.add(query)
                threading.Thread(
                    target=self._refresh, args=(query,), daemon=True
                ).start()
            return entry["value"] if entry else None

    def invalidate(self, query: str):
        """Drop the cached value so the next get_count() re-fetches."""
        with self._counts_lock:
            self._counts.pop(query, None)

    def _refresh(self, query: str):
        value = self.backend.count(query)
        with self._counts_lock:
            # Cache the result (including None on failure) with a timestamp so
            # the max_age backoff applies to errors as well as successes.
            self._counts[query] = {"value": value, "ts": time.monotonic()}
            self._inflight.discard(query)
