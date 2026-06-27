# GitHub Insights plugin for StreamController

Surface [GitHub](https://github.com) repo insights on your Stream Deck, powered
by the local [`gh`](https://cli.github.com) CLI.

## Actions

| Action | What it does |
| --- | --- |
| **PR Count** | Shows a live count of pull requests in a repo matching a filter (author, approval status, labels, state). Press the key to open the equivalent GitHub PR search in your browser. |
| **CI Status** | Shows the status of the latest GitHub Actions run for a repo — green ✓ (success), red ✗ (failure), amber dots (running/queued), grey dash (no runs / cancelled). Press to open the run (or the repo's Actions page) in your browser. |

### PR Count filters

Configure each button in its settings:

| Setting | Notes |
| --- | --- |
| **Button label** | Short name shown on the key (e.g. "My Open"). |
| **Repository** | `owner/name`, e.g. `benwyrosdick/streamdeck-github`. |
| **Author** | Anyone / Me / Not me / Specific user / Not a user. |
| **User** | The username used when Author is *Specific user* or *Not a user*. |
| **Approval** | Any / Pending review / Approved / Changes requested / Review required. |
| **Labels** | Comma-separated; all must be present (AND). |
| **State** | Open (default) / Closed / Merged / All. |
| **Advanced query** | Raw GitHub search qualifiers appended verbatim (e.g. `draft:false`). |

**Examples**

- **My Open** — Author: *Me*, Approval: *Pending review*, State: *Open*.
- **For Review** — Author: *Not me*, Labels: `api`, Approval: *Pending review*, State: *Open*.

### CI Status filters

| Setting | Notes |
| --- | --- |
| **Button label** | Short name shown on the key; defaults to the workflow name. |
| **Repository** | `owner/name`. |
| **Workflow** | Optional — a workflow name (`CI`) or file (`ci.yml`). Blank = any workflow. |
| **Branch** | Optional — blank follows the repo's default branch. |

## Requirements

- StreamController **1.5.0-beta.14** or newer.
- The `gh` CLI installed on the host and authenticated (`gh auth status`). The
  plugin reaches it from the flatpak sandbox via `flatpak-spawn --host`, so it
  uses your existing `gh` login — **no API key or extra setup required**.

If `gh` isn't authenticated, run `gh auth login` once on the host. Until then,
PR Count keys show an `auth` hint instead of a number.

## How it works

The plugin shells out to the host `gh` CLI. Counts come from a single GraphQL
`search { issueCount }` call — it returns just the total without fetching the
matching PRs, the cheapest way to count. Each unique filter's count is cached
for ~45s and refreshed on a background thread, so the deck never freezes and
GitHub isn't polled more than necessary no matter how many buttons you have.

## Notes

- "Not me" / negated-author filters are always scoped to the configured repo,
  so they stay fast and accurate (an unscoped negation would span all of
  GitHub).
- The `pr.png` icon and `store/Thumbnail.png` are simple placeholders — replace
  them with your own art if you like.
