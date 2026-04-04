"""Tool definitions in Anthropic API schema format."""

TOOLS = [
    {
        "name": "update_knowledge",
        "description": (
            "Update one of Tuesday's knowledge files to remember something new about Harman. "
            "Use this when you learn new facts, preferences, or context. "
            "Allowed files: identity.md, disposition.md, expertise.md, preferences.md, principles.md, context.md, session_summaries.md"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Which knowledge file to update (e.g. 'preferences.md')",
                },
                "content": {
                    "type": "string",
                    "description": "The full new content for the file, or content to append",
                },
                "mode": {
                    "type": "string",
                    "enum": ["replace", "append"],
                    "description": "Whether to replace the entire file or append to it",
                },
            },
            "required": ["filename", "content", "mode"],
        },
    },
    {
        "name": "save_session_note",
        "description": (
            "Save an important fact or note to long-term memory. "
            "Use this for key facts that should persist across all sessions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": "The fact or note to remember",
                },
                "category": {
                    "type": "string",
                    "enum": ["preference", "fact", "goal", "event", "other"],
                    "description": "Category of the note",
                },
            },
            "required": ["note", "category"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file from the filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to read",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write or create a file on the filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to write to",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_command",
        "description": (
            "Run a whitelisted shell command. "
            "Allowed: git, ls, cat, grep, find, python3, npm, node, date, whoami, pwd, echo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to run",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for current information using Brave Search. "
            "Use this to look up facts, documentation, news, or anything Tuesday doesn't already know."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of results (default 5, max 10)",
                },
            },
            "required": ["query"],
        },
    },
    # --- GitHub tools ---
    {
        "name": "github_create_repo",
        "description": (
            "Create a new GitHub repository for Harman. "
            "Defaults to private with a README."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Repository name (e.g. 'my-project')",
                },
                "description": {
                    "type": "string",
                    "description": "Short description of the repo",
                },
                "private": {
                    "type": "boolean",
                    "description": "Whether the repo is private (default true)",
                },
                "auto_init": {
                    "type": "boolean",
                    "description": "Initialize with a README (default true)",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "github_list_repos",
        "description": "List Harman's GitHub repositories, sorted by most recently updated.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sort": {
                    "type": "string",
                    "enum": ["updated", "created", "pushed"],
                    "description": "Sort order (default: updated)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of repos to list (default 10, max 30)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "github_analyze_repo",
        "description": (
            "Analyze a GitHub repository: structure, README, recent commits, open issues. "
            "Use this to understand what a repo contains and suggest improvements."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner (e.g. 'harmanjohll')",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name (e.g. 'Tuesday')",
                },
            },
            "required": ["owner", "repo"],
        },
    },
    {
        "name": "github_search_code",
        "description": "Search for code across Harman's GitHub repositories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Code search query",
                },
                "repo": {
                    "type": "string",
                    "description": "Optional: scope to a specific repo (owner/name)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "github_create_issue",
        "description": "Create a GitHub issue on one of Harman's repositories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name",
                },
                "title": {
                    "type": "string",
                    "description": "Issue title",
                },
                "body": {
                    "type": "string",
                    "description": "Issue body (markdown)",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels to apply",
                },
            },
            "required": ["owner", "repo", "title"],
        },
    },
    {
        "name": "github_manage_repo",
        "description": (
            "Manage a GitHub repository: list/create branches, read/create files. "
            "Actions: list_branches, create_branch, get_file, create_file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_branches", "create_branch", "get_file", "create_file"],
                    "description": "What to do",
                },
                "owner": {
                    "type": "string",
                    "description": "Repository owner",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name",
                },
                "branch_name": {
                    "type": "string",
                    "description": "For create_branch: new branch name",
                },
                "from_branch": {
                    "type": "string",
                    "description": "For create_branch: source branch (default: main)",
                },
                "path": {
                    "type": "string",
                    "description": "For get_file/create_file: file path",
                },
                "content": {
                    "type": "string",
                    "description": "For create_file: file content",
                },
                "message": {
                    "type": "string",
                    "description": "For create_file: commit message",
                },
            },
            "required": ["action", "owner", "repo"],
        },
    },
]
