"""GitHub API client and tool implementations."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger("tuesday.github")

API_BASE = "https://api.github.com"
TIMEOUT = 15.0


def _headers() -> dict:
    return {
        "Authorization": f"token {settings.github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _check_token() -> str | None:
    """Return error message if no token configured."""
    if not settings.github_token:
        return "GitHub token not configured. Set GITHUB_TOKEN in your .env file."
    return None


async def create_repo(inp: dict) -> str:
    if err := _check_token():
        return err

    name = inp["name"]
    description = inp.get("description", "")
    private = inp.get("private", True)
    auto_init = inp.get("auto_init", True)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{API_BASE}/user/repos",
            headers=_headers(),
            json={
                "name": name,
                "description": description,
                "private": private,
                "auto_init": auto_init,
            },
        )

    if resp.status_code == 201:
        data = resp.json()
        return f"Created repository: {data['full_name']}\nURL: {data['html_url']}\nClone: {data['clone_url']}"
    elif resp.status_code == 422:
        return f"Repository '{name}' already exists or name is invalid."
    else:
        return f"GitHub API error {resp.status_code}: {resp.text[:300]}"


async def list_repos(inp: dict) -> str:
    if err := _check_token():
        return err

    sort = inp.get("sort", "updated")
    limit = min(inp.get("limit", 10), 30)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            f"{API_BASE}/user/repos",
            headers=_headers(),
            params={"sort": sort, "per_page": limit, "type": "owner"},
        )

    if resp.status_code != 200:
        return f"GitHub API error {resp.status_code}: {resp.text[:300]}"

    repos = resp.json()
    if not repos:
        return "No repositories found."

    lines = []
    for r in repos:
        vis = "private" if r["private"] else "public"
        lang = r.get("language") or "—"
        stars = r.get("stargazers_count", 0)
        updated = r.get("updated_at", "")[:10]
        lines.append(f"- **{r['full_name']}** ({vis}, {lang}, {stars}★) — updated {updated}")
        if r.get("description"):
            lines.append(f"  {r['description']}")

    return "\n".join(lines)


async def analyze_repo(inp: dict) -> str:
    if err := _check_token():
        return err

    owner = inp["owner"]
    repo = inp["repo"]
    headers = _headers()

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Fetch repo metadata, file tree, README, recent commits in parallel
        meta_req = client.get(f"{API_BASE}/repos/{owner}/{repo}", headers=headers)
        tree_req = client.get(
            f"{API_BASE}/repos/{owner}/{repo}/git/trees/HEAD",
            headers=headers,
            params={"recursive": "1"},
        )
        readme_req = client.get(
            f"{API_BASE}/repos/{owner}/{repo}/readme",
            headers={**headers, "Accept": "application/vnd.github.v3.raw"},
        )
        commits_req = client.get(
            f"{API_BASE}/repos/{owner}/{repo}/commits",
            headers=headers,
            params={"per_page": 10},
        )
        issues_req = client.get(
            f"{API_BASE}/repos/{owner}/{repo}/issues",
            headers=headers,
            params={"state": "open", "per_page": 10},
        )

        meta_resp, tree_resp, readme_resp, commits_resp, issues_resp = await asyncio.gather(
            meta_req, tree_req, readme_req, commits_req, issues_req
        )

    sections = []

    # Metadata
    if meta_resp.status_code == 200:
        m = meta_resp.json()
        sections.append(f"## {m['full_name']}")
        if m.get("description"):
            sections.append(m["description"])
        sections.append(f"- Language: {m.get('language', '—')}")
        sections.append(f"- Stars: {m.get('stargazers_count', 0)}, Forks: {m.get('forks_count', 0)}")
        sections.append(f"- Created: {m.get('created_at', '')[:10]}, Updated: {m.get('updated_at', '')[:10]}")
        sections.append(f"- Default branch: {m.get('default_branch', 'main')}")
    elif meta_resp.status_code == 404:
        return f"Repository {owner}/{repo} not found."
    else:
        return f"GitHub API error {meta_resp.status_code}: {meta_resp.text[:300]}"

    # File tree
    if tree_resp.status_code == 200:
        tree = tree_resp.json().get("tree", [])
        # Show directory structure (top-level + key files)
        dirs = set()
        files = []
        for item in tree:
            path = item["path"]
            if item["type"] == "tree":
                # Only top-level dirs
                if "/" not in path:
                    dirs.add(path + "/")
            elif item["type"] == "blob":
                parts = path.split("/")
                if len(parts) == 1:
                    files.append(path)

        sections.append("\n## Structure")
        for d in sorted(dirs):
            sections.append(f"  {d}")
        for f in sorted(files):
            sections.append(f"  {f}")
        sections.append(f"  ({len(tree)} total files/dirs)")

    # README (first 2000 chars)
    if readme_resp.status_code == 200:
        readme = readme_resp.text[:2000]
        sections.append(f"\n## README\n{readme}")

    # Recent commits
    if commits_resp.status_code == 200:
        commits = commits_resp.json()[:5]
        sections.append("\n## Recent Commits")
        for c in commits:
            sha = c["sha"][:7]
            msg = c["commit"]["message"].split("\n")[0][:80]
            date = c["commit"]["author"]["date"][:10]
            sections.append(f"- `{sha}` {msg} ({date})")

    # Open issues
    if issues_resp.status_code == 200:
        issues = [i for i in issues_resp.json() if not i.get("pull_request")]
        if issues:
            sections.append(f"\n## Open Issues ({len(issues)})")
            for i in issues[:5]:
                labels = ", ".join(l["name"] for l in i.get("labels", []))
                sections.append(f"- #{i['number']}: {i['title']}" + (f" [{labels}]" if labels else ""))

    return "\n".join(sections)


async def search_code(inp: dict) -> str:
    if err := _check_token():
        return err

    query = inp["query"]
    repo_scope = inp.get("repo", "")

    q = f"{query} user:{_get_username()}" if not repo_scope else f"{query} repo:{repo_scope}"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            f"{API_BASE}/search/code",
            headers=_headers(),
            params={"q": q, "per_page": 10},
        )

    if resp.status_code != 200:
        return f"GitHub search error {resp.status_code}: {resp.text[:300]}"

    data = resp.json()
    items = data.get("items", [])
    if not items:
        return f"No code matches for: {query}"

    lines = [f"Found {data['total_count']} matches:"]
    for item in items[:10]:
        lines.append(f"- `{item['repository']['full_name']}` / `{item['path']}`")

    return "\n".join(lines)


async def create_issue(inp: dict) -> str:
    if err := _check_token():
        return err

    owner = inp["owner"]
    repo = inp["repo"]
    title = inp["title"]
    body = inp.get("body", "")
    labels = inp.get("labels", [])

    payload: dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{API_BASE}/repos/{owner}/{repo}/issues",
            headers=_headers(),
            json=payload,
        )

    if resp.status_code == 201:
        data = resp.json()
        return f"Created issue #{data['number']}: {data['title']}\nURL: {data['html_url']}"
    else:
        return f"GitHub API error {resp.status_code}: {resp.text[:300]}"


async def manage_repo(inp: dict) -> str:
    if err := _check_token():
        return err

    action = inp["action"]
    owner = inp.get("owner", "")
    repo = inp.get("repo", "")
    headers = _headers()

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        if action == "list_branches":
            resp = await client.get(
                f"{API_BASE}/repos/{owner}/{repo}/branches",
                headers=headers,
                params={"per_page": 20},
            )
            if resp.status_code != 200:
                return f"Error: {resp.status_code}"
            branches = resp.json()
            return "\n".join(f"- {b['name']}" for b in branches) or "No branches found."

        elif action == "create_branch":
            branch_name = inp.get("branch_name", "")
            from_branch = inp.get("from_branch", "main")
            # Get SHA of source branch
            ref_resp = await client.get(
                f"{API_BASE}/repos/{owner}/{repo}/git/refs/heads/{from_branch}",
                headers=headers,
            )
            if ref_resp.status_code != 200:
                return f"Could not find branch '{from_branch}'"
            sha = ref_resp.json()["object"]["sha"]
            # Create new branch
            resp = await client.post(
                f"{API_BASE}/repos/{owner}/{repo}/git/refs",
                headers=headers,
                json={"ref": f"refs/heads/{branch_name}", "sha": sha},
            )
            if resp.status_code == 201:
                return f"Created branch '{branch_name}' from '{from_branch}'"
            return f"Error creating branch: {resp.status_code} {resp.text[:200]}"

        elif action == "get_file":
            file_path = inp.get("path", "")
            resp = await client.get(
                f"{API_BASE}/repos/{owner}/{repo}/contents/{file_path}",
                headers={**headers, "Accept": "application/vnd.github.v3.raw"},
            )
            if resp.status_code == 200:
                content = resp.text
                if len(content) > 10000:
                    content = content[:10000] + "\n... (truncated)"
                return content
            return f"File not found or error: {resp.status_code}"

        elif action == "create_file":
            file_path = inp.get("path", "")
            content = inp.get("content", "")
            message = inp.get("message", f"Create {file_path}")
            import base64
            resp = await client.put(
                f"{API_BASE}/repos/{owner}/{repo}/contents/{file_path}",
                headers=headers,
                json={
                    "message": message,
                    "content": base64.b64encode(content.encode()).decode(),
                },
            )
            if resp.status_code in (200, 201):
                return f"Created/updated file: {file_path}"
            return f"Error: {resp.status_code} {resp.text[:200]}"

        else:
            return f"Unknown action: {action}. Available: list_branches, create_branch, get_file, create_file"


def _get_username() -> str:
    """Extract username from token (best effort)."""
    # This is used for search scoping; if it fails, searches are unscoped
    return ""


# Need asyncio for gather in analyze_repo
import asyncio
