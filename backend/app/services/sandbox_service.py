"""Python code execution sandbox.

Runs Python code in a subprocess with resource limits.
Used for data analysis, plotting, simulations, and calculations.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import tempfile
import uuid
from pathlib import Path

from app.config import settings

logger = logging.getLogger("tuesday.sandbox")

# Max execution time (seconds)
MAX_TIMEOUT = 60

# Max output size (bytes)
MAX_OUTPUT = 50_000

# Banned imports for security
BANNED_PATTERNS = [
    "import subprocess", "import os", "from os", "import shutil",
    "import socket", "import requests", "import urllib",
    "__import__", "exec(", "eval(",
    "open('/etc", "open('/root", "open('/home",
    "os.system", "os.popen", "os.exec",
]


def _outputs_dir() -> Path:
    d = settings.outputs_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


async def run_python(inp: dict) -> str:
    """Execute Python code in a sandboxed subprocess."""
    code = inp.get("code", "")
    if not code.strip():
        return "No code provided."

    # Basic security check
    code_lower = code.lower()
    for pattern in BANNED_PATTERNS:
        if pattern.lower() in code_lower:
            return f"Security: '{pattern}' is not allowed in sandbox code."

    # Create temp directory for this execution
    exec_id = uuid.uuid4().hex[:12]
    work_dir = tempfile.mkdtemp(prefix=f"tuesday_sandbox_{exec_id}_")
    output_dir = _outputs_dir()

    # Write the code to a file
    code_file = Path(work_dir) / "script.py"

    # Wrap code to capture generated files
    wrapped_code = f"""
import sys
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import warnings
warnings.filterwarnings('ignore')

# Set output directory for any generated files
_OUTPUT_DIR = "{output_dir}"
_EXEC_ID = "{exec_id}"

{code}

# Check for any matplotlib figures and save them
import matplotlib.pyplot as plt
if plt.get_fignums():
    for i, num in enumerate(plt.get_fignums()):
        fig = plt.figure(num)
        fname = f"{{_OUTPUT_DIR}}/{{_EXEC_ID}}_plot{{i}}.png"
        fig.savefig(fname, dpi=150, bbox_inches='tight')
        print(f"PLOT_SAVED:{{fname}}")
    plt.close('all')
"""
    code_file.write_text(wrapped_code)

    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", str(code_file),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir,
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/usr/local/bin"),
                "HOME": work_dir,
                "MPLCONFIGDIR": work_dir,
            },
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=MAX_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            return f"Execution timed out after {MAX_TIMEOUT} seconds."

        stdout_text = stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT]
        stderr_text = stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT]

        # Parse output for saved plots
        result_parts = []
        plots = []
        for line in stdout_text.split("\n"):
            if line.startswith("PLOT_SAVED:"):
                plot_path = line.replace("PLOT_SAVED:", "").strip()
                plot_filename = Path(plot_path).name
                file_id = plot_filename.split(".")[0]
                plots.append(f"DOWNLOAD:/documents/download/{file_id}|{plot_filename}|Chart")
            else:
                if line.strip():
                    result_parts.append(line)

        output = "\n".join(result_parts) if result_parts else "(no output)"

        if stderr_text and proc.returncode != 0:
            # Filter out common warnings
            error_lines = [l for l in stderr_text.split("\n")
                          if l.strip() and "warning" not in l.lower()]
            if error_lines:
                output += f"\n\nErrors:\n" + "\n".join(error_lines[-10:])

        if plots:
            output += "\n\n" + "\n".join(plots)

        return output

    except Exception as e:
        return f"Sandbox error: {e}"
    finally:
        # Cleanup temp directory (keep output files)
        try:
            code_file.unlink(missing_ok=True)
            Path(work_dir).rmdir()
        except OSError:
            pass
