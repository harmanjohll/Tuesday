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
        "description": "Search the web for information. (Not yet implemented - returns a placeholder.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
            },
            "required": ["query"],
        },
    },
]
