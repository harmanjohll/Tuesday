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
    # --- Outlook tools ---
    {
        "name": "outlook_list_events",
        "description": (
            "List Harman's calendar events from Outlook. "
            "Returns events for a date range with times, locations, and attendees. "
            "Default: next 7 days from the work calendar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format (default: today)",
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to look ahead (default: 7)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum events to return (default: 10, max 25)",
                },
                "account": {
                    "type": "string",
                    "enum": ["work", "personal"],
                    "description": "Which Outlook account to query (default: work)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "outlook_create_event",
        "description": (
            "Create a calendar event in Harman's Outlook calendar. "
            "IMPORTANT: Always confirm with Harman before creating events. "
            "Show the proposed event details and ask 'Should I go ahead?' before calling this tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Event title",
                },
                "start": {
                    "type": "string",
                    "description": "Start time in ISO format, Singapore time (e.g. '2026-04-07T06:00:00')",
                },
                "end": {
                    "type": "string",
                    "description": "End time in ISO format, Singapore time (e.g. '2026-04-07T08:00:00')",
                },
                "location": {
                    "type": "string",
                    "description": "Event location (optional)",
                },
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of attendee email addresses (optional)",
                },
                "account": {
                    "type": "string",
                    "enum": ["work", "personal"],
                    "description": "Which Outlook account (default: work)",
                },
            },
            "required": ["subject", "start", "end"],
        },
    },
    {
        "name": "outlook_update_event",
        "description": (
            "Update an existing calendar event. Requires the event ID from a previous list. "
            "IMPORTANT: Always confirm changes with Harman before updating."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "The event ID to update",
                },
                "subject": {
                    "type": "string",
                    "description": "New event title",
                },
                "start": {
                    "type": "string",
                    "description": "New start time (ISO format, Singapore time)",
                },
                "end": {
                    "type": "string",
                    "description": "New end time (ISO format, Singapore time)",
                },
                "location": {
                    "type": "string",
                    "description": "New location",
                },
                "account": {
                    "type": "string",
                    "enum": ["work", "personal"],
                    "description": "Which account (default: work)",
                },
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "outlook_get_messages",
        "description": (
            "Fetch emails from Harman's Outlook inbox. "
            "Can filter by unread status, sender, and folder. "
            "Email content is NOT saved to memory — only used in the current conversation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "unread_only": {
                    "type": "boolean",
                    "description": "Only show unread messages (default: false)",
                },
                "from_sender": {
                    "type": "string",
                    "description": "Filter by sender email address",
                },
                "folder": {
                    "type": "string",
                    "description": "Mail folder (default: inbox)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of emails to fetch (default: 10, max 25)",
                },
                "account": {
                    "type": "string",
                    "enum": ["work", "personal"],
                    "description": "Which Outlook account (default: work)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "outlook_send_email",
        "description": (
            "Send an email from Harman's Outlook account. "
            "IMPORTANT: Always show the full draft to Harman and get explicit approval before sending. "
            "Never send without confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address (or comma-separated list)",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line",
                },
                "body": {
                    "type": "string",
                    "description": "Email body (plain text)",
                },
                "account": {
                    "type": "string",
                    "enum": ["work", "personal"],
                    "description": "Which Outlook account to send from (default: work)",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    # --- Gmail tools ---
    {
        "name": "gmail_get_messages",
        "description": (
            "Fetch emails from Harman's personal Gmail inbox. "
            "Can filter by unread status and sender. "
            "Email content is NOT saved to memory — only used in the current conversation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "unread_only": {
                    "type": "boolean",
                    "description": "Only show unread messages (default: false)",
                },
                "from_sender": {
                    "type": "string",
                    "description": "Filter by sender email address",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of emails to fetch (default: 10, max 25)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "gmail_send_email",
        "description": (
            "Send an email from Harman's personal Gmail account. "
            "IMPORTANT: Always show the full draft to Harman and get explicit approval before sending. "
            "Never send without confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line",
                },
                "body": {
                    "type": "string",
                    "description": "Email body (plain text)",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
]
