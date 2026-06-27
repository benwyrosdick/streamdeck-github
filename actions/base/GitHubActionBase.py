import os

from src.backend.PluginManager.ActionBase import ActionBase


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

    def render(self):
        """Update the button from current state. Overridden per action."""
        raise NotImplementedError
