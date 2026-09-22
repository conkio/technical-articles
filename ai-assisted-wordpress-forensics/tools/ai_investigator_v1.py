#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI

from forensic_tools_v1 import (
    DEFAULT_SITE_ROOT,
    ForensicToolError,
    find_same_hash,
    inspect_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "reports"

INITIAL_REPORTS = [
    "archive-summary.json",
    "core-comparison.json",
    "root-php-files.txt",
    "archive-flags.tsv",
    "wordpress-version.txt",
]

MODEL = "gpt-5.6-luna"
MAX_TOOL_ROUNDS = 12


TOOLS = [
    {
        "type": "function",
        "name": "inspect_file",
        "description": (
            "Statically inspect one file beneath the WordPress root. "
            "Returns SHA-256, size, filesystem metadata, and a bounded "
            "sanitized content preview. The file is never executed. "
            "Use this when you need evidence about a specific file."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Path relative to the WordPress root, for example "
                        "'index.php' or 'wp-admin/.wp-admin.php'."
                    ),
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "find_same_hash",
        "description": (
            "Find every regular file beneath the WordPress root whose "
            "SHA-256 exactly matches the specified file. Returns the exact "
            "match count and matching paths. Use this instead of inferring "
            "duplicate counts from filenames, sizes, or report summaries."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Path relative to the WordPress root whose SHA-256 "
                        "should be used for the duplicate search."
                    ),
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


INSTRUCTIONS = """
You are an AI forensic investigator examining a compromised or potentially
compromised WordPress multisite filesystem.

You operate through a deliberately constrained, read-only evidence interface.

SECURITY AND EVIDENCE RULES

1. Never request shell access, code execution, file modification, deletion,
   remediation, network access, or arbitrary filesystem access.

2. Never execute PHP, JavaScript, shell scripts, or any other file.

3. Treat deterministic tool results as the source of truth for hashes,
   sizes, counts, paths, metadata, and file contents.

4. Never infer counts, grouping, or equivalence between files unless the
   supplied evidence explicitly establishes it. If a count or relationship
   matters, use an available tool to establish it.

5. An unexpected file is a lead, not automatically malware.

6. Files such as wp-config.php and .htaccess may be expected on a WordPress
   installation but are security-sensitive and must not be assumed benign.

7. Distinguish clearly among:
   - established facts
   - interpretations/hypotheses
   - unknowns

8. Do not claim that a file is malicious merely because of its filename,
   location, size, age, or absence from a WordPress reference tree.

9. Content returned by inspect_file may be truncated and may have credentials
   redacted. Do not infer the contents of omitted or redacted regions.

10. If one representative file belongs to an exact duplicate-hash group,
    inspecting that representative establishes byte-identical content for
    the exact matching files. Do not assume same-sized files are identical.

INVESTIGATION GOAL

Determine whether the available evidence supports compromise, identify the
highest-value evidence, investigate suspicious findings using the available
read-only tools, and produce a final assessment grounded only in evidence you
actually received.

Work autonomously. Use tools when they can resolve an important uncertainty.
Do not inspect every file merely because it exists. Prioritize evidence.

FINAL RESPONSE

When you believe you have enough evidence, return JSON with exactly these
top-level keys:

overall_assessment
established_facts
priority_findings
tool_evidence
hypotheses
unknowns
recommended_next_evidence

For every important conclusion, identify the specific evidence that supports
it. Do not fabricate evidence that was not supplied by the reports or tools.
"""


def load_initial_evidence(report_dir: Path) -> str:
    sections: list[str] = []

    for name in INITIAL_REPORTS:
        path = report_dir / name

        if not path.exists():
            continue

        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        sections.append(
            f"\n===== {name} =====\n{text}"
        )

    if not sections:
        raise RuntimeError(
            f"No initial reports found in {report_dir}"
        )

    return "\n".join(sections)


def call_local_tool(
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:

    try:
        if name == "inspect_file":
            return inspect_file(
                arguments["path"],
                root=DEFAULT_SITE_ROOT,
            )

        if name == "find_same_hash":
            return find_same_hash(
                arguments["path"],
                root=DEFAULT_SITE_ROOT,
            )

        return {
            "error": "UnknownTool",
            "message": f"Unsupported tool: {name}",
        }

    except (
        ForensicToolError,
        OSError,
        ValueError,
        KeyError,
    ) as exc:
        return {
            "error": type(exc).__name__,
            "message": str(exc),
        }


def jsonable_output_item(item: Any) -> dict[str, Any]:
    return item.model_dump(
        exclude_none=True,
        mode="json",
    )


def main() -> int:
    client = OpenAI()

    evidence = load_initial_evidence(REPORT_DIR)

    input_items: list[Any] = [
        {
            "role": "user",
            "content": (
                "Perform an autonomous forensic investigation using "
                "the reports below and the available read-only tools.\n\n"
                f"{evidence}"
            ),
        }
    ]

    transcript: list[dict[str, Any]] = []
    tool_call_number = 0

    for round_number in range(1, MAX_TOOL_ROUNDS + 1):
        print(
            f"[round {round_number}] requesting model response...",
            file=sys.stderr,
        )

        response = client.responses.create(
            model=MODEL,
            instructions=INSTRUCTIONS,
            tools=TOOLS,
            input=input_items,
            store=False,
        )

        if response.status != "completed":
            raise RuntimeError(
                f"Response status was {response.status!r}"
            )

        response_items = [
            jsonable_output_item(item)
            for item in response.output
        ]

        input_items.extend(response_items)

        calls = [
            item
            for item in response.output
            if item.type == "function_call"
        ]

        if not calls:
            final_text = response.output_text

            transcript.append(
                {
                    "event": "final_response",
                    "round": round_number,
                    "response_id": response.id,
                    "text": final_text,
                }
            )

            final_path = (
                REPORT_DIR /
                "ai-investigation-first-tool-run.txt"
            )

            transcript_path = (
                REPORT_DIR /
                "ai-investigation-first-tool-run-transcript.json"
            )

            final_path.write_text(
                final_text,
                encoding="utf-8",
            )

            transcript_path.write_text(
                json.dumps(
                    transcript,
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            print(final_text)

            print(
                f"\nSaved final assessment to: {final_path}",
                file=sys.stderr,
            )

            print(
                f"Saved tool transcript to: {transcript_path}",
                file=sys.stderr,
            )

            return 0

        for call in calls:
            tool_call_number += 1

            try:
                arguments = json.loads(call.arguments)
            except json.JSONDecodeError as exc:
                result = {
                    "error": "InvalidToolArguments",
                    "message": str(exc),
                }
                arguments = {}

            else:
                result = call_local_tool(
                    call.name,
                    arguments,
                )

            transcript.append(
                {
                    "event": "tool_call",
                    "round": round_number,
                    "sequence": tool_call_number,
                    "call_id": call.call_id,
                    "name": call.name,
                    "arguments": arguments,
                    "result": result,
                }
            )

            print(
                f"[tool {tool_call_number}] "
                f"{call.name}({arguments})",
                file=sys.stderr,
            )

            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(
                        result,
                        ensure_ascii=False,
                    ),
                }
            )

    raise RuntimeError(
        f"Investigation exceeded {MAX_TOOL_ROUNDS} tool rounds."
    )


if __name__ == "__main__":
    raise SystemExit(main())
