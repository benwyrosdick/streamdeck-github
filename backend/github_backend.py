"""Thin wrapper around the host `gh` (GitHub CLI).

This module deliberately has NO GTK or StreamController imports so it stays
pure and unit-testable. StreamController runs inside a flatpak sandbox, so the
host binary is reached via `flatpak-spawn --host gh ...`. When running outside
a sandbox (e.g. local development) the binary is called directly.

We use the *local* `gh` CLI (which carries the user's existing auth) rather
than a raw GitHub API token, so no extra credentials are needed.

Counts are obtained with a single GraphQL `search { issueCount }` call: it
returns just the total without fetching any result rows, which is by far the
cheapest way to count matching pull requests.
"""

import json
import os
import shutil
import subprocess
import threading
from typing import Optional

try:
    from loguru import logger as log
except Exception:  # pragma: no cover - loguru always present inside the app
    import logging
    log = logging.getLogger("github")

# Timeouts (seconds). Counts hit the network, so give them a generous budget;
# auth checks are local and quick.
COUNT_TIMEOUT = 8
AUTH_TIMEOUT = 5


class GitHubBackend:
    def __init__(self):
        # The flatpak sandbox always has /.flatpak-info; the host does not.
        self._sandboxed = os.path.exists("/.flatpak-info")

    # ------------------------------------------------------------------ #
    # Low-level command construction / execution
    # ------------------------------------------------------------------ #
    def _build_cmd(self, args: list) -> list:
        if self._sandboxed:
            # --directory=/ pins a working dir that exists on the host. Without
            # it, flatpak-spawn forwards the caller's cwd (the app's install
            # dir), which the host can't chdir into, and every call fails with
            # "Failed to change to directory".
            return ["flatpak-spawn", "--host", "--directory=/", "gh", *args]
        return [shutil.which("gh") or "gh", *args]

    def _run(self, args: list, timeout: int = COUNT_TIMEOUT):
        """Run a gh command. Returns (ok, stdout, stderr); never raises."""
        cmd = self._build_cmd(args)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            ok = proc.returncode == 0
            if not ok:
                log.warning("[github] {} -> rc={} err={!r}", args, proc.returncode, (proc.stderr or "").strip()[:200])
            return ok, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            log.error("[github] {} -> TIMEOUT after {}s", cmd, timeout)
            return False, "", "timeout"
        except (FileNotFoundError, OSError) as e:
            log.error("[github] {} -> EXEC FAILED: {}", cmd, e)
            return False, "", str(e)

    # ------------------------------------------------------------------ #
    # Read operations
    # ------------------------------------------------------------------ #
    def gh_available(self) -> bool:
        """True if `gh` is installed and authenticated."""
        ok, _, _ = self._run(["auth", "status"], timeout=AUTH_TIMEOUT)
        return ok

    def count(self, query: str, timeout: int = COUNT_TIMEOUT) -> Optional[int]:
        """Number of issues/PRs matching a GitHub search `query`.

        Uses GraphQL `search(type: ISSUE, first: 0) { issueCount }` so only the
        total comes back, not the matching rows. Returns None on any failure.
        """
        if not query or not query.strip():
            return None
        gql = (
            "query($q: String!) { search(query: $q, type: ISSUE, first: 0) "
            "{ issueCount } }"
        )
        # Both -f flags force string typing; the GraphQL variable is String!.
        # -f (vs -F) also avoids gh interpreting a leading '@' as a file path.
        ok, out, _ = self._run(
            ["api", "graphql", "-f", f"query={gql}", "-f", f"q={query}",
             "--jq", ".data.search.issueCount"],
            timeout=timeout,
        )
        if not ok or not out.strip():
            return None
        try:
            return int(out.strip())
        except (ValueError, TypeError):
            # Fall back to parsing a full JSON envelope just in case --jq is
            # unavailable on an older gh.
            try:
                return int(json.loads(out)["data"]["search"]["issueCount"])
            except (ValueError, TypeError, KeyError):
                return None

    def latest_run(self, repo: str, workflow: str = "", branch: str = "",
                   timeout: int = COUNT_TIMEOUT):
        """Most recent GitHub Actions run for a repo (optionally filtered).

        Returns the run dict (status/conclusion/workflowName/headBranch/url/
        displayTitle), an empty dict `{}` when the repo has no matching runs,
        or None on any failure — letting the caller tell "no runs" apart from
        "couldn't fetch".
        """
        if not repo:
            return None
        args = [
            "run", "list", "-R", repo, "--limit", "1",
            "--json", "status,conclusion,workflowName,headBranch,displayTitle,url",
        ]
        if workflow:
            args += ["--workflow", workflow]
        if branch:
            args += ["--branch", branch]
        ok, out, _ = self._run(args, timeout=timeout)
        if not ok or not out.strip():
            return None
        try:
            data = json.loads(out)
        except (ValueError, TypeError):
            return None
        if not data:
            return {}
        return data[0]

    # ------------------------------------------------------------------ #
    # Side effects
    # ------------------------------------------------------------------ #
    def open_in_browser(self, url: str) -> None:
        """Open `url` in the host's default browser; fire-and-forget."""
        if not url:
            return

        def worker():
            if self._sandboxed:
                cmd = ["flatpak-spawn", "--host", "--directory=/", "xdg-open", url]
            else:
                cmd = [shutil.which("xdg-open") or "xdg-open", url]
            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            except Exception as e:  # never let a browser launch crash a key press
                log.error("[github] open_in_browser failed: {}", e)

        threading.Thread(target=worker, daemon=True).start()
