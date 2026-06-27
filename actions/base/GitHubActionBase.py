import os
import time

from src.backend.PluginManager.ActionBase import ActionBase


def format_countdown(seconds: float) -> str:
    """Compact mm/ss countdown, e.g. 205s -> "3m25s", 9s -> "9s"."""
    secs = max(0, int(seconds))
    minutes, secs = divmod(secs, 60)
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


class GitHubActionBase(ActionBase):
    """Shared rendering and error helpers for GitHub actions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------ #
    # Rendering helpers
    # ------------------------------------------------------------------ #
    def set_icon(self, name: str, size: float = 0.75):
        path = os.path.join(self.plugin_base.PATH, "assets", name)
        self.set_media(media_path=path, size=size)

    def clear_icon(self):
        # Drop any previously-set icon so a label-only key isn't covered by it.
        try:
            self.set_media(media_path=None)
        except (AttributeError, TypeError):
            pass

    def safe_set_background(self, color):
        # set_background_color raises AttributeError on some 1.5.0-beta builds.
        try:
            self.set_background_color(color=color)
        except AttributeError:
            pass

    def safe_set_label(self, position: str, text: str, **kwargs):
        """Set a label defensively.

        Only set_bottom_label is exercised by every build we target; the top /
        center setters exist in current StreamController but we guard them so a
        missing method degrades gracefully instead of crashing render().
        """
        setter = getattr(self, f"set_{position}_label", None)
        if setter is None:
            return
        try:
            setter(text, **kwargs)
        except (AttributeError, TypeError):
            try:
                setter(text)
            except Exception:
                pass

    def render_rate_limited(self, until: float):
        """Shared "rate limit" key state: red background, no icon, and a
        countdown (bottom) to when polling will resume."""
        self.clear_icon()
        self.safe_set_background([180, 30, 30, 255])
        self.safe_set_label("top", "rate limit", font_size=12)
        self.safe_set_label("center", "", font_size=1)
        self.safe_set_label("bottom", format_countdown(until - time.time()), font_size=14)

    def render(self):
        """Update the button from current state. Overridden per action."""
        raise NotImplementedError
