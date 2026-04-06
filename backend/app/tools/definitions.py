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
    {
        "name": "github_update_file",
        "description": (
            "Update an existing file in a GitHub repository. "
            "Fetches the current file SHA automatically. "
            "IMPORTANT: Always confirm with Harman before modifying code."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "path": {"type": "string", "description": "File path to update"},
                "content": {"type": "string", "description": "New file content (full file)"},
                "message": {"type": "string", "description": "Commit message"},
                "branch": {"type": "string", "description": "Target branch (default: main)"},
            },
            "required": ["owner", "repo", "path", "content", "message"],
        },
    },
    {
        "name": "github_create_pull_request",
        "description": "Create a pull request in a GitHub repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "title": {"type": "string", "description": "PR title"},
                "body": {"type": "string", "description": "PR description"},
                "head": {"type": "string", "description": "Branch with changes"},
                "base": {"type": "string", "description": "Branch to merge into (default: main)"},
            },
            "required": ["owner", "repo", "title", "head"],
        },
    },
    {
        "name": "github_list_pull_requests",
        "description": "List pull requests for a GitHub repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "state": {
                    "type": "string",
                    "enum": ["open", "closed", "all"],
                    "description": "Filter by state (default: open)",
                },
            },
            "required": ["owner", "repo"],
        },
    },
    # --- Brain sync ---
    {
        "name": "sync_brain",
        "description": (
            "Sync Tuesday's knowledge files to the brain repo (harmanjohll/brain) on GitHub. "
            "Use after updating knowledge files so the portable brain stays current. "
            "This keeps Harman's identity accessible across all Claude instances."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "create_time_capsule",
        "description": (
            "Create a dated snapshot of Harman's brain repo — a digital time capsule. "
            "Syncs all knowledge files and creates a Git tag marking this moment in time. "
            "Use when Harman asks to save a snapshot, or at meaningful milestones."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Optional label for this capsule (e.g. 'started-new-role', 'end-of-2026')",
                },
                "message": {
                    "type": "string",
                    "description": "Optional message to attach to the capsule",
                },
            },
            "required": [],
        },
    },
    # --- Content creation ---
    {
        "name": "create_presentation",
        "description": (
            "Generate a PowerPoint presentation (PPTX). "
            "Provide a title and array of slides, each with a title and content. "
            "Returns a download link for the generated file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Presentation title"},
                "subtitle": {"type": "string", "description": "Subtitle for the title slide"},
                "slides": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                    "description": "Array of slides, each with title and content",
                },
                "template_id": {
                    "type": "string",
                    "description": "Optional template ID to use as base (from list_templates). Preserves corporate branding.",
                },
            },
            "required": ["title", "slides"],
        },
    },
    {
        "name": "list_templates",
        "description": (
            "List available document templates (PPTX, DOCX). "
            "Returns template IDs that can be passed to create_presentation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "template_type": {
                    "type": "string",
                    "enum": ["pptx", "docx"],
                    "description": "Filter by type (optional)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "create_document",
        "description": (
            "Generate a Word document (DOCX) — letters, proposals, reports, memos, policies. "
            "Provide a title and sections with headings and body text. "
            "Returns a download link for the generated file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Document title"},
                "author": {"type": "string", "description": "Author name (optional)"},
                "date": {"type": "string", "description": "Date string (optional)"},
                "style": {
                    "type": "string",
                    "enum": ["formal", "casual", "memo"],
                    "description": "Document style (default: formal)",
                },
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "heading": {"type": "string"},
                            "body": {"type": "string"},
                        },
                    },
                    "description": "Array of sections, each with heading and body",
                },
            },
            "required": ["title", "sections"],
        },
    },
    {
        "name": "create_pdf_report",
        "description": (
            "Generate a formatted PDF report. "
            "Provide a title and sections. Returns a download link."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Report title"},
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "heading": {"type": "string"},
                            "body": {"type": "string"},
                        },
                    },
                    "description": "Array of sections, each with heading and body",
                },
            },
            "required": ["title", "sections"],
        },
    },
    # --- Reminders ---
    {
        "name": "set_reminder",
        "description": (
            "Set a reminder for Harman. Use when he says 'remind me to...' or similar. "
            "Reminders appear in morning briefings and can be listed on demand."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "What to remind about"},
                "due_date": {
                    "type": "string",
                    "description": "When to remind (YYYY-MM-DD format). Use 'today' for same-day.",
                },
                "repeat": {
                    "type": "string",
                    "enum": ["none", "daily", "weekly", "monthly"],
                    "description": "Repeat frequency (default: none)",
                },
            },
            "required": ["text", "due_date"],
        },
    },
    {
        "name": "list_reminders",
        "description": "List all active reminders for Harman.",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_done": {
                    "type": "boolean",
                    "description": "Include completed reminders (default: false)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "dismiss_reminder",
        "description": "Mark a reminder as done. Use the reminder ID from list_reminders.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reminder_id": {"type": "string", "description": "The reminder ID to dismiss"},
            },
            "required": ["reminder_id"],
        },
    },
    # --- Code execution ---
    {
        "name": "run_python",
        "description": (
            "Execute Python code in a sandbox. Use for data analysis, calculations, plotting, "
            "simulations, and mathematical modelling. Available libraries: numpy, scipy, matplotlib, "
            "sympy, pandas. Generated plots are automatically saved and returned as download links. "
            "Do NOT import os, subprocess, socket, or other system-access modules."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute",
                },
                "description": {
                    "type": "string",
                    "description": "Brief description of what this code does (for logging)",
                },
            },
            "required": ["code"],
        },
    },
    # --- Statistics ---
    {
        "name": "query_statistics",
        "description": (
            "Query public statistics APIs. Sources: "
            "singapore (data.gov.sg — demographics, education, economics), "
            "world_bank (global development indicators), "
            "who (global health data). "
            "First search for available datasets/indicators, then query with a specific indicator ID."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["singapore", "world_bank", "who"],
                    "description": "Data source to query",
                },
                "query": {
                    "type": "string",
                    "description": "Search term to find datasets/indicators",
                },
                "indicator": {
                    "type": "string",
                    "description": "Specific indicator/dataset ID (from a previous search)",
                },
                "country": {
                    "type": "string",
                    "description": "Country code, e.g. SGP, USA, GBR (default: SGP)",
                },
                "year_from": {
                    "type": "string",
                    "description": "Start year for data range (default: 2010)",
                },
                "year_to": {
                    "type": "string",
                    "description": "End year for data range (default: 2024)",
                },
            },
            "required": ["source"],
        },
    },
    # --- Work calendar (ICS) ---
    {
        "name": "read_work_calendar",
        "description": (
            "Read Harman's work calendar (Outlook/MOE) via published ICS feed. "
            "Read-only. To create events, use Google Calendar instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Days ahead to check (default: 7)"},
                "max_results": {"type": "integer", "description": "Max events (default: 20)"},
            },
            "required": [],
        },
    },
    # --- Google Calendar ---
    {
        "name": "gcal_list_events",
        "description": (
            "List Harman's upcoming Google Calendar events. "
            "Returns events with times, titles, and locations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Days ahead to check (default: 7)"},
                "max_results": {"type": "integer", "description": "Max events (default: 15)"},
            },
            "required": [],
        },
    },
    {
        "name": "gcal_create_event",
        "description": (
            "Create a Google Calendar event. "
            "IMPORTANT: Always confirm with Harman before creating."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Event title"},
                "start": {"type": "string", "description": "Start time ISO format (e.g. 2026-04-07T09:00:00)"},
                "end": {"type": "string", "description": "End time ISO format"},
                "location": {"type": "string", "description": "Location (optional)"},
                "description": {"type": "string", "description": "Event description (optional)"},
            },
            "required": ["summary", "start", "end"],
        },
    },
    {
        "name": "gcal_update_event",
        "description": "Update an existing Google Calendar event. Can change summary, time, location, or description.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Event ID to update (from gcal_list_events)"},
                "summary": {"type": "string", "description": "New title (optional)"},
                "start": {"type": "string", "description": "New start time ISO format (optional)"},
                "end": {"type": "string", "description": "New end time ISO format (optional)"},
                "location": {"type": "string", "description": "New location (optional)"},
                "description": {"type": "string", "description": "New description (optional)"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "gcal_delete_event",
        "description": "Delete a Google Calendar event. Requires event ID from list.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Event ID to delete"},
            },
            "required": ["event_id"],
        },
    },
    # --- Google Drive ---
    {
        "name": "gdrive_list_files",
        "description": "List files in Harman's Google Drive. Can filter by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search by filename (optional)"},
                "folder_id": {"type": "string", "description": "Folder ID to list (optional)"},
                "max_results": {"type": "integer", "description": "Max files (default: 15)"},
            },
            "required": [],
        },
    },
    {
        "name": "gdrive_read_file",
        "description": (
            "Read a file from Google Drive. For Google Docs/Sheets/Slides, "
            "exports as plain text. Use the file ID from gdrive_list_files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "Drive file ID"},
            },
            "required": ["file_id"],
        },
    },
    {
        "name": "analyze_reference_materials",
        "description": (
            "Read all files from a Google Drive folder and analyze Harman's communication style, "
            "writing patterns, presentation approach, and teaching methods. "
            "Writes the analysis to knowledge/style.md so Tuesday can match Harman's voice. "
            "Use when Harman asks Tuesday to learn his style or analyze his reference materials."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "folder_name": {
                    "type": "string",
                    "description": "Google Drive folder name containing reference materials (default: 'Tuesday')",
                },
                "focus": {
                    "type": "string",
                    "enum": ["writing_style", "presentation_style", "teaching_approach", "all"],
                    "description": "What aspect to focus on (default: all)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "fetch_reference_exemplar",
        "description": (
            "Fetch a reference document from Harman's Google Drive to use as a style exemplar "
            "when creating a presentation, speech, or written piece. "
            "Searches the Tuesday reference folder for a relevant file by name or keyword. "
            "Use this BEFORE generating content to have Harman's actual voice in your working context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term to find relevant reference (e.g. 'graduation speech', 'awards day', 'gala dinner')",
                },
                "max_files": {
                    "type": "integer",
                    "description": "Number of files to fetch (default 1, max 3)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "gdrive_search",
        "description": "Search Google Drive by file content or name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "gdrive_upload_file",
        "description": (
            "Upload a file to Google Drive. Use after creating a document (presentation, report, etc.) "
            "to save it to Harman's Drive. Can specify a target folder."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Local file path (in outputs/ directory)"},
                "folder_name": {"type": "string", "description": "Drive folder name to upload to (optional)"},
                "file_name": {"type": "string", "description": "Name for the file on Drive (optional, defaults to local filename)"},
            },
            "required": ["file_path"],
        },
    },
    # --- Decision journal ---
    {
        "name": "log_decision",
        "description": (
            "Log a decision Harman has made. Use proactively when Harman makes a decision during conversation. "
            "Include context and optional follow-up date so nothing falls through the cracks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "decision": {"type": "string", "description": "What was decided"},
                "context": {"type": "string", "description": "Why this decision was made, relevant background"},
                "category": {
                    "type": "string",
                    "description": "Category (e.g. school, personal, tech, finance)",
                },
                "follow_up_date": {
                    "type": "string",
                    "description": "When to follow up (YYYY-MM-DD format). Optional.",
                },
            },
            "required": ["decision", "context"],
        },
    },
    {
        "name": "check_followups",
        "description": (
            "Check for upcoming decision follow-ups. Use proactively at the start of conversations "
            "to remind Harman of things he needs to revisit."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "How many days ahead to check (default: 7)",
                },
            },
            "required": [],
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
        "name": "outlook_delete_event",
        "description": "Delete an Outlook calendar event. Requires event ID from outlook_list_events.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Event ID to delete"},
                "account": {"type": "string", "enum": ["work", "personal"], "description": "Which account (default: work)"},
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
    {
        "name": "outlook_mark_read",
        "description": "Mark an Outlook email as read.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Message ID to mark as read"},
                "account": {"type": "string", "enum": ["work", "personal"], "description": "Which account (default: work)"},
            },
            "required": ["message_id"],
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
    {
        "name": "gmail_mark_read",
        "description": (
            "Mark Gmail emails as read. Use after reviewing emails with Harman "
            "to clean up his inbox. Pass the message IDs from gmail_get_messages output."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Gmail message IDs to mark as read",
                },
            },
            "required": ["message_ids"],
        },
    },
    {
        "name": "gmail_archive",
        "description": (
            "Archive Gmail emails — removes from inbox but keeps in All Mail. "
            "Good for newsletters and notifications Harman has already seen."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Gmail message IDs to archive",
                },
            },
            "required": ["message_ids"],
        },
    },
    # --- Mind Castle agent tools ---
    {
        "name": "spawn_agent",
        "description": (
            "Create a new agent in the Mind Castle. Agents are specialist AIs that can work on tasks "
            "independently. Give each agent a clear name and role. Use this when Harman needs parallel "
            "work done or a dedicated specialist for a domain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Agent name (e.g. 'Strategist', 'Editor', 'Researcher')"},
                "role": {"type": "string", "description": "What this agent does (1-2 sentences)"},
                "color": {"type": "string", "description": "Hex color for the agent's orb (optional, auto-assigned if blank)"},
                "system_prompt": {"type": "string", "description": "Additional instructions for this agent (optional)"},
            },
            "required": ["name", "role"],
        },
    },
    {
        "name": "assign_agent_task",
        "description": (
            "Assign a task to a Mind Castle agent. The agent will work on it in the background. "
            "Use get_agent_status to check progress and read_agent_output to get results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Agent ID to assign the task to"},
                "task": {"type": "string", "description": "Detailed task description for the agent"},
            },
            "required": ["agent_id", "task"],
        },
    },
    {
        "name": "get_agent_status",
        "description": "Check the status and progress of a Mind Castle agent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Agent ID to check"},
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "read_agent_output",
        "description": "Read the full latest output from a Mind Castle agent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Agent ID to read from"},
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "list_agents",
        "description": "List all agents in the Mind Castle with their current status.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "gmail_trash",
        "description": (
            "Move Gmail emails to trash. Use with caution — always confirm with Harman before trashing. "
            "Trashed emails are permanently deleted after 30 days."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Gmail message IDs to trash",
                },
            },
            "required": ["message_ids"],
        },
    },
    # --- Metacognition ---
    {
        "name": "review_insight_report",
        "description": (
            "Mark a weekly insight report as reviewed by Harman. "
            "Use after Harman has read and responded to an insight report. "
            "Status can be: confirmed, corrected, partially_accepted."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "report_date": {
                    "type": "string",
                    "description": "Date of the report (YYYY-MM-DD format)",
                },
                "status": {
                    "type": "string",
                    "enum": ["confirmed", "corrected", "partially_accepted"],
                    "description": "Harman's review status",
                },
                "notes": {
                    "type": "string",
                    "description": "Harman's corrections or comments (optional)",
                },
            },
            "required": ["report_date", "status"],
        },
    },
]
