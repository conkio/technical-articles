#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE_ROOT = PROJECT_ROOT / "working" / "site" / "public"

MAX_PREVIEW_BYTES = 64 * 1024
MAX_MATCH_PATHS = 500


# These values are expected in wp-config.php but should not be sent
# verbatim to a hosted model.
WORDPRESS_SENSITIVE_DEFINES = (
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "AUTH_KEY",
    "SECURE_AUTH_KEY",
    "LOGGED_IN_KEY",
    "NONCE_KEY",
    "AUTH_SALT",
    "SECURE_AUTH_SALT",
    "LOGGED_IN_SALT",
    "NONCE_SALT",
)

_DEFINE_KEYS = "|".join(
    re.escape(key) for key in WORDPRESS_SENSITIVE_DEFINES
)

WP_DEFINE_RE = re.compile(
    rf"""(?im)^
    (?P<prefix>
        \s*define\s*\(\s*
        ['"](?P<key>{_DEFINE_KEYS})['"]
        \s*,\s*
    )
    .*?
    (?P<suffix>
        \)\s*;
        \s*(?://.*)?
    )
    $
    """,
    re.VERBOSE,
)

ENV_SECRET_RE = re.compile(
    r"""(?im)^
    (?P<prefix>
        \s*
        [A-Z0-9_]*
        (?:PASSWORD|PASSWD|SECRET|TOKEN|API_KEY|APIKEY|PRIVATE_KEY)
        [A-Z0-9_]*
        \s*=\s*
    )
    .*$
    """,
    re.VERBOSE,
)

PHP_SECRET_ASSIGN_RE = re.compile(
    r"""(?im)^
    (?P<prefix>
        \s*\$
        [A-Za-z0-9_]*
        (?:password|passwd|secret|token|api_?key)
        [A-Za-z0-9_]*
        \s*=\s*
    )
    .*?
    (?P<suffix>
        ;\s*(?://.*)?
    )
    $
    """,
    re.VERBOSE,
)

PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----.*?"
    r"-----END [^-]*PRIVATE KEY-----",
    re.DOTALL,
)

TOKEN_RE = re.compile(
    r"\b(?:"
    r"sk-[A-Za-z0-9_-]{20,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|AKIA[A-Z0-9]{16}"
    r")\b"
)

BASIC_AUTH_URL_RE = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)"
    r"(?P<user>[^/\s:@]+):"
    r"(?P<password>[^@\s/]+)@"
)


class ForensicToolError(Exception):
    """Raised when a forensic tool request is invalid or unsafe."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def iso_timestamp(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None

    return datetime.fromtimestamp(
        timestamp,
        tz=timezone.utc,
    ).isoformat()


def normalize_agent_path(path: str, root: Path) -> Path:
    """
    Convert an agent-supplied path into a safe path beneath root.

    Agent-facing paths are relative to the WordPress root:
        index.php
        wp-admin/.wp-admin.php
        wp-config.php

    For compatibility with existing reports, a single leading
    "public/" component is also accepted when the configured root
    itself is named "public".
    """

    if not isinstance(path, str) or not path.strip():
        raise ForensicToolError("Path must be a non-empty string.")

    if "\x00" in path:
        raise ForensicToolError("NUL bytes are not allowed in paths.")

    requested = Path(path.strip())

    if requested.is_absolute():
        raise ForensicToolError(
            "Absolute paths are not allowed."
        )

    parts = list(requested.parts)

    if root.name == "public" and parts and parts[0] == "public":
        parts = parts[1:]

    if not parts:
        raise ForensicToolError(
            "Path must identify a file beneath the WordPress root."
        )

    if any(part in ("..", "") for part in parts):
        raise ForensicToolError(
            "Parent-directory traversal is not allowed."
        )

    root_resolved = root.resolve(strict=True)

    current = root_resolved
    for part in parts:
        current = current / part

        # Reject symlinks anywhere in the requested path.
        if current.is_symlink():
            raise ForensicToolError(
                "Symlink paths are not allowed."
            )

    try:
        resolved = current.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ForensicToolError(
            f"File does not exist: {'/'.join(parts)}"
        ) from exc

    try:
        common = os.path.commonpath(
            [str(root_resolved), str(resolved)]
        )
    except ValueError as exc:
        raise ForensicToolError(
            "Path is outside the configured WordPress root."
        ) from exc

    if common != str(root_resolved):
        raise ForensicToolError(
            "Path is outside the configured WordPress root."
        )

    if not resolved.is_file():
        raise ForensicToolError(
            "Requested path is not a regular file."
        )

    return resolved


def display_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(
        root.resolve()
    ).as_posix()


def redact_text(text: str) -> tuple[str, list[str]]:
    """
    Apply deterministic credential redaction.

    This is deliberately conservative. It is intended to prevent
    obvious secrets from being sent to a hosted model, not to serve
    as a complete secret-detection system.
    """

    redactions: list[str] = []

    def replace_wp_define(match: re.Match[str]) -> str:
        key = match.group("key")
        redactions.append(f"wordpress-define:{key}")

        return (
            f"{match.group('prefix')}"
            "'[REDACTED]'"
            f"{match.group('suffix')}"
        )

    text = WP_DEFINE_RE.sub(replace_wp_define, text)

    def replace_env_secret(match: re.Match[str]) -> str:
        redactions.append("environment-secret")
        return f"{match.group('prefix')}[REDACTED]"

    text = ENV_SECRET_RE.sub(replace_env_secret, text)

    def replace_php_secret(match: re.Match[str]) -> str:
        redactions.append("php-secret-assignment")
        return (
            f"{match.group('prefix')}"
            "'[REDACTED]'"
            f"{match.group('suffix')}"
        )

    text = PHP_SECRET_ASSIGN_RE.sub(
        replace_php_secret,
        text,
    )

    def replace_private_key(match: re.Match[str]) -> str:
        redactions.append("private-key")
        return "[REDACTED PRIVATE KEY]"

    text = PRIVATE_KEY_RE.sub(
        replace_private_key,
        text,
    )

    def replace_token(match: re.Match[str]) -> str:
        redactions.append("credential-token")
        return "[REDACTED TOKEN]"

    text = TOKEN_RE.sub(replace_token, text)

    def replace_basic_auth(match: re.Match[str]) -> str:
        redactions.append("url-embedded-credentials")
        return (
            f"{match.group('scheme')}"
            "[REDACTED]:[REDACTED]@"
        )

    text = BASIC_AUTH_URL_RE.sub(
        replace_basic_auth,
        text,
    )

    return text, sorted(set(redactions))


def probably_text(data: bytes) -> bool:
    if not data:
        return True

    if b"\x00" in data:
        return False

    sample = data[:8192]

    decoded = sample.decode(
        "utf-8",
        errors="replace",
    )

    replacement_ratio = (
        decoded.count("\ufffd") / max(len(decoded), 1)
    )

    return replacement_ratio < 0.02


def read_bounded_preview(
    path: Path,
    max_bytes: int = MAX_PREVIEW_BYTES,
) -> dict[str, Any]:

    size = path.stat().st_size

    if max_bytes < 1024:
        raise ForensicToolError(
            "Preview limit must be at least 1024 bytes."
        )

    with path.open("rb") as handle:
        if size <= max_bytes:
            data = handle.read(max_bytes)
            truncated = False
            strategy = "full"
        else:
            head_size = max_bytes // 2
            tail_size = max_bytes - head_size

            head = handle.read(head_size)

            handle.seek(max(size - tail_size, 0))
            tail = handle.read(tail_size)

            data = (
                head
                + b"\n\n"
                + b"[... CONTENT TRUNCATED ...]"
                + b"\n\n"
                + tail
            )

            truncated = True
            strategy = "head-and-tail"

    if not probably_text(data):
        return {
            "content_type": "binary",
            "content_preview": None,
            "binary_prefix_hex": data[:256].hex(),
            "preview_bytes_limit": max_bytes,
            "preview_strategy": strategy,
            "truncated": truncated,
            "redactions": [],
        }

    text = data.decode(
        "utf-8",
        errors="replace",
    )

    redacted_text, redactions = redact_text(text)

    return {
        "content_type": "text",
        "content_preview": redacted_text,
        "binary_prefix_hex": None,
        "preview_bytes_limit": max_bytes,
        "preview_strategy": strategy,
        "truncated": truncated,
        "redactions": redactions,
    }


def inspect_file(
    path: str,
    root: Path = DEFAULT_SITE_ROOT,
    max_preview_bytes: int = MAX_PREVIEW_BYTES,
) -> dict[str, Any]:
    """
    Return static metadata and a bounded, sanitized preview.

    The file is never executed.
    """

    resolved = normalize_agent_path(path, root)

    file_stat = resolved.stat()

    mime_type, mime_encoding = mimetypes.guess_type(
        resolved.name
    )

    preview = read_bounded_preview(
        resolved,
        max_bytes=max_preview_bytes,
    )

    birthtime = getattr(
        file_stat,
        "st_birthtime",
        None,
    )

    return {
        "tool": "inspect_file",
        "requested_path": path,
        "path": display_path(resolved, root),
        "sha256": sha256_file(resolved),
        "size": file_stat.st_size,
        "mode": stat.filemode(file_stat.st_mode),
        "mode_octal": oct(
            stat.S_IMODE(file_stat.st_mode)
        ),
        "uid": file_stat.st_uid,
        "gid": file_stat.st_gid,
        "timestamps": {
            "mtime_unix": file_stat.st_mtime,
            "mtime_utc": iso_timestamp(
                file_stat.st_mtime
            ),
            "ctime_unix": file_stat.st_ctime,
            "ctime_utc": iso_timestamp(
                file_stat.st_ctime
            ),
            "atime_unix": file_stat.st_atime,
            "atime_utc": iso_timestamp(
                file_stat.st_atime
            ),
            "birthtime_unix": birthtime,
            "birthtime_utc": iso_timestamp(
                birthtime
            ),
        },
        "mime_type_guess": mime_type,
        "mime_encoding_guess": mime_encoding,
        "executed": False,
        "preview": preview,
        "redaction_notice": (
            "Credential redaction is heuristic and is not "
            "guaranteed to detect every possible secret."
        ),
    }


def find_same_hash(
    path: str,
    root: Path = DEFAULT_SITE_ROOT,
    max_paths: int = MAX_MATCH_PATHS,
) -> dict[str, Any]:
    """
    Find regular files beneath root with the same SHA-256 as path.

    Files with different sizes are skipped without hashing, which makes
    this much cheaper than hashing the entire site on every request.
    """

    target = normalize_agent_path(path, root)

    target_size = target.stat().st_size
    target_hash = sha256_file(target)

    matches: list[str] = []

    scanned_files = 0
    same_size_candidates = 0
    exact_match_count = 0

    root_resolved = root.resolve(strict=True)

    for dirpath, dirnames, filenames in os.walk(
        root_resolved,
        followlinks=False,
    ):
        directory = Path(dirpath)

        # Never traverse symlinked directories.
        dirnames[:] = [
            name
            for name in dirnames
            if not (directory / name).is_symlink()
        ]

        for filename in filenames:
            candidate = directory / filename

            if candidate.is_symlink():
                continue

            try:
                if not candidate.is_file():
                    continue

                candidate_stat = candidate.stat()
            except OSError:
                continue

            scanned_files += 1

            if candidate_stat.st_size != target_size:
                continue

            same_size_candidates += 1

            try:
                candidate_hash = sha256_file(candidate)
            except OSError:
                continue

            if candidate_hash != target_hash:
                continue

            exact_match_count += 1

            if len(matches) < max_paths:
                matches.append(
                    candidate.relative_to(
                        root_resolved
                    ).as_posix()
                )

    matches.sort()

    return {
        "tool": "find_same_hash",
        "requested_path": path,
        "path": display_path(target, root),
        "sha256": target_hash,
        "size": target_size,
        "match_count": exact_match_count,
        "paths_returned": len(matches),
        "paths_truncated": exact_match_count > len(matches),
        "paths": matches,
        "scan_scope": str(root_resolved),
        "scanned_regular_files": scanned_files,
        "same_size_candidates": same_size_candidates,
        "symlinks_followed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only forensic tools for a WordPress "
            "filesystem working copy."
        )
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_SITE_ROOT,
        help=(
            "WordPress root directory "
            f"(default: {DEFAULT_SITE_ROOT})"
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect one file statically.",
    )

    inspect_parser.add_argument(
        "path",
        help="Path relative to the WordPress root.",
    )

    inspect_parser.add_argument(
        "--max-preview-bytes",
        type=int,
        default=MAX_PREVIEW_BYTES,
    )

    hash_parser = subparsers.add_parser(
        "same-hash",
        help="Find files with the same SHA-256.",
    )

    hash_parser.add_argument(
        "path",
        help="Path relative to the WordPress root.",
    )

    hash_parser.add_argument(
        "--max-paths",
        type=int,
        default=MAX_MATCH_PATHS,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        if args.command == "inspect":
            result = inspect_file(
                args.path,
                root=args.root,
                max_preview_bytes=args.max_preview_bytes,
            )

        elif args.command == "same-hash":
            result = find_same_hash(
                args.path,
                root=args.root,
                max_paths=args.max_paths,
            )

        else:
            raise ForensicToolError(
                f"Unknown command: {args.command}"
            )

        print(
            json.dumps(
                result,
                indent=2,
                sort_keys=False,
            )
        )

        return 0

    except (
        ForensicToolError,
        OSError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {
                    "error": type(exc).__name__,
                    "message": str(exc),
                },
                indent=2,
            ),
            file=sys.stderr,
        )

        return 2


if __name__ == "__main__":
    raise SystemExit(main())
