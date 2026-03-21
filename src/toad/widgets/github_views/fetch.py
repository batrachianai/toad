"""gh CLI wrapper for fetching GitHub data as parsed JSON."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

GH_BIN: str | None = shutil.which("gh")

ISSUE_FIELDS = "number,title,labels,state,createdAt,updatedAt,author"
PR_FIELDS = (
    "number,title,state,reviewDecision,statusCheckRollup,createdAt,updatedAt,author"
)


class GitHubFetchError(Exception):
    """Raised when a gh CLI call fails."""


class GitHubAuthError(GitHubFetchError):
    """Raised when gh is not authenticated."""


@dataclass(frozen=True)
class RepoInfo:
    owner: str
    repo: str

    @property
    def nwo(self) -> str:
        return f"{self.owner}/{self.repo}"


async def _run_gh(*args: str, timeout_s: float = 15) -> str:
    """Run a gh CLI command and return stdout.

    Raises GitHubFetchError on failure, GitHubAuthError if not logged in.
    """
    if GH_BIN is None:
        raise GitHubFetchError(
            "gh CLI not found on PATH. Install from https://cli.github.com/"
        )

    proc = await asyncio.create_subprocess_exec(
        GH_BIN,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise GitHubFetchError(
            f"gh command timed out after {timeout_s}s: gh {' '.join(args)}"
        ) from exc

    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        if "auth login" in err or "not logged in" in err:
            raise GitHubAuthError("gh is not authenticated. Run: gh auth login")
        raise GitHubFetchError(f"gh exited {proc.returncode}: {err}")

    return stdout.decode(errors="replace")


async def check_auth() -> bool:
    """Return True if gh is authenticated."""
    try:
        await _run_gh("auth", "status")
    except GitHubFetchError:
        return False
    return True


async def detect_repo() -> RepoInfo:
    """Detect owner/repo from the current git remote.

    Parses the output of `gh repo view --json nameWithOwner`.
    """
    raw = await _run_gh("repo", "view", "--json", "nameWithOwner")
    data = json.loads(raw)
    nwo: str = data["nameWithOwner"]
    owner, repo = nwo.split("/", 1)
    return RepoInfo(owner=owner, repo=repo)


def _read_repo_from_dega_core(project_dir: Path) -> RepoInfo | None:
    """Read github.repo from dega-core.yaml in a project directory."""
    yaml_path = project_dir / "dega-core.yaml"
    if not yaml_path.is_file():
        return None
    try:
        import yaml  # noqa: PLC0415

        data = yaml.safe_load(yaml_path.read_text())
    except Exception:
        log.debug("failed to parse %s", yaml_path, exc_info=True)
        return None
    nwo = (data or {}).get("github", {}).get("repo")
    if not nwo or "/" not in nwo:
        return None
    owner, repo = nwo.split("/", 1)
    return RepoInfo(owner=owner, repo=repo)


async def _detect_repo_from_git(project_dir: Path) -> RepoInfo:
    """Detect owner/repo from git remote of a specific directory."""
    if GH_BIN is None:
        raise GitHubFetchError(
            "gh CLI not found on PATH. Install from https://cli.github.com/"
        )
    proc = await asyncio.create_subprocess_exec(
        GH_BIN,
        "repo",
        "view",
        "--json",
        "nameWithOwner",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(project_dir),
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=15
        )
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise GitHubFetchError(
            f"gh repo view timed out for {project_dir}"
        ) from exc
    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        raise GitHubFetchError(
            f"gh repo view failed in {project_dir}: {err}"
        )
    data = json.loads(stdout.decode(errors="replace"))
    nwo: str = data["nameWithOwner"]
    owner, repo = nwo.split("/", 1)
    return RepoInfo(owner=owner, repo=repo)


async def detect_repo_from_path(project_dir: str | Path) -> RepoInfo:
    """Detect owner/repo for a project directory.

    Resolution order:
    1. dega-core.yaml github.repo in the project directory
    2. git remote of the project directory (via gh repo view)
    """
    path = Path(project_dir).resolve()
    if not path.is_dir():
        raise GitHubFetchError(f"project directory not found: {path}")

    repo_info = _read_repo_from_dega_core(path)
    if repo_info is not None:
        log.info("repo from dega-core.yaml: %s", repo_info.nwo)
        return repo_info

    log.info("no dega-core.yaml github.repo, falling back to git remote")
    return await _detect_repo_from_git(path)


async def fetch_issues(
    repo: RepoInfo,
    *,
    state: str = "open",
    labels: list[str] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch issues from the repo."""
    args = [
        "issue",
        "list",
        "--repo",
        repo.nwo,
        "--state",
        state,
        "--json",
        ISSUE_FIELDS,
        "--limit",
        str(limit),
    ]
    if labels:
        for label in labels:
            args.extend(["--label", label])

    raw = await _run_gh(*args)
    result: list[dict[str, Any]] = json.loads(raw)
    return result


async def fetch_prs(
    repo: RepoInfo,
    *,
    state: str = "open",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch pull requests from the repo."""
    raw = await _run_gh(
        "pr",
        "list",
        "--repo",
        repo.nwo,
        "--state",
        state,
        "--json",
        PR_FIELDS,
        "--limit",
        str(limit),
    )
    result: list[dict[str, Any]] = json.loads(raw)
    return result


async def fetch_events(
    repo: RepoInfo,
    *,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Fetch recent repository events via the GitHub API."""
    raw = await _run_gh(
        "api",
        f"repos/{repo.nwo}/events",
        "--jq",
        f".[0:{limit}]",
    )
    result: list[dict[str, Any]] = json.loads(raw)
    return result


async def fetch_plan_issues(
    repo: RepoInfo,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Fetch issues with plan:* labels, including body for progress parsing."""
    raw = await _run_gh(
        "issue",
        "list",
        "--repo",
        repo.nwo,
        "--label",
        "plan:active",
        "--json",
        f"{ISSUE_FIELDS},body",
        "--limit",
        str(limit),
    )
    result: list[dict[str, Any]] = json.loads(raw)
    return result
