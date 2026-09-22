#!/usr/bin/env python3

import argparse
import csv
import json
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import PurePosixPath

SERVER_CODE_EXTENSIONS = {
    ".php", ".phtml", ".php3", ".php4", ".php5",
    ".php7", ".php8", ".phar", ".cgi", ".pl",
    ".py", ".sh"
}


def member_type(member):
    if member.isfile():
        return "file"
    if member.isdir():
        return "directory"
    if member.issym():
        return "symlink"
    if member.islnk():
        return "hardlink"
    if member.ischr():
        return "char-device"
    if member.isblk():
        return "block-device"
    if member.isfifo():
        return "fifo"
    return "other"


def unsafe_path(path):
    normalized = path.replace("\\", "/")
    p = PurePosixPath(normalized)

    return (
        p.is_absolute()
        or normalized.startswith("/")
        or ".." in p.parts
    )


def in_uploads(path):
    normalized = "/" + path.replace("\\", "/").lstrip("./")
    return "/wp-content/uploads/" in normalized


def suspicious_upload_name(path):
    p = PurePosixPath(path.replace("\\", "/"))
    name = p.name.lower()

    if name == ".htaccess":
        return True

    if p.suffix.lower() in SERVER_CODE_EXTENSIONS:
        return True

    # Examples: photo.jpg.php, cache.php.jpg, etc.
    if any(f"{ext}." in name for ext in SERVER_CODE_EXTENSIONS):
        return True

    return False


def main():
    parser = argparse.ArgumentParser(
        description="Safely inventory a tar archive without extracting it."
    )
    parser.add_argument("archive")
    parser.add_argument("output_dir")
    args = parser.parse_args()

    summary = {
        "archive": args.archive,
        "members": 0,
        "files": 0,
        "directories": 0,
        "symlinks": 0,
        "hardlinks": 0,
        "special_files": 0,
        "logical_file_bytes": 0,
        "uploads_files": 0,
        "uploads_bytes": 0,
        "unsafe_members": 0,
        "flagged_members": 0,
    }

    extensions = Counter()
    top_level = Counter()

    members_path = f"{args.output_dir}/archive-members.tsv"
    flags_path = f"{args.output_dir}/archive-flags.tsv"
    summary_path = f"{args.output_dir}/archive-summary.json"

    with (
        tarfile.open(args.archive, mode="r:*") as archive,
        open(members_path, "w", newline="", encoding="utf-8") as members_file,
        open(flags_path, "w", newline="", encoding="utf-8") as flags_file,
    ):
        member_writer = csv.writer(members_file, delimiter="\t")
        flag_writer = csv.writer(flags_file, delimiter="\t")

        member_writer.writerow(
            ["type", "size", "mtime", "path", "link_target"]
        )

        flag_writer.writerow(
            ["reason", "type", "size", "path", "link_target"]
        )

        for member in archive:
            summary["members"] += 1

            kind = member_type(member)

            if kind == "file":
                summary["files"] += 1
                summary["logical_file_bytes"] += member.size

            elif kind == "directory":
                summary["directories"] += 1

            elif kind == "symlink":
                summary["symlinks"] += 1

            elif kind == "hardlink":
                summary["hardlinks"] += 1

            elif kind in {"char-device", "block-device", "fifo"}:
                summary["special_files"] += 1

            try:
                mtime = datetime.fromtimestamp(
                    member.mtime, timezone.utc
                ).isoformat()
            except (ValueError, OSError, OverflowError):
                mtime = str(member.mtime)

            member_writer.writerow(
                [
                    kind,
                    member.size,
                    mtime,
                    member.name,
                    member.linkname or "",
                ]
            )

            normalized = member.name.replace("\\", "/")
            parts = PurePosixPath(normalized).parts

            if parts:
                top_level[parts[0]] += 1

            if member.isfile():
                suffix = PurePosixPath(normalized).suffix.lower()
                extensions[suffix or "(none)"] += 1

            reasons = []

            if unsafe_path(member.name):
                reasons.append("unsafe-member-path")
                summary["unsafe_members"] += 1

            if member.issym() or member.islnk():
                if member.linkname and unsafe_path(member.linkname):
                    reasons.append("unsafe-link-target")

            if kind in {"char-device", "block-device", "fifo"}:
                reasons.append("special-file")

            if member.isfile() and in_uploads(member.name):
                summary["uploads_files"] += 1
                summary["uploads_bytes"] += member.size

                if suspicious_upload_name(member.name):
                    reasons.append("potential-code-in-uploads")

            if reasons:
                summary["flagged_members"] += 1

                flag_writer.writerow(
                    [
                        ",".join(reasons),
                        kind,
                        member.size,
                        member.name,
                        member.linkname or "",
                    ]
                )

    summary["top_level_entries"] = dict(
        top_level.most_common(30)
    )

    summary["common_extensions"] = dict(
        extensions.most_common(50)
    )

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Summary: {summary_path}")
    print(f"Full inventory: {members_path}")
    print(f"Flags: {flags_path}")


if __name__ == "__main__":
    main()
