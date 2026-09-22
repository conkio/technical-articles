#!/usr/bin/env python3

import argparse
import hashlib
import json
from pathlib import Path


CORE_DIRS = ("wp-admin", "wp-includes")


def sha256_file(path, chunk_size=1024 * 1024):
    """Calculate SHA-256 for a file without loading it all into memory."""
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)

    return h.hexdigest()


def file_info(path, root):
    """Return basic deterministic metadata about a file."""
    stat = path.stat()

    return {
        "path": str(path.relative_to(root)),
        "size": stat.st_size,
        "sha256": sha256_file(path),
        "mtime": stat.st_mtime,
    }


def load_site_file_rules(path):
    """
    Load rules describing expected site-specific files.

    These files are not considered trusted. The rules only distinguish
    files that may legitimately exist on an installed WordPress site
    despite not being included in the official WordPress distribution.
    """
    if path is None:
        return {}

    rules_path = Path(path)

    if not rules_path.is_file():
        raise FileNotFoundError(
            f"Site-specific rules file not found: {rules_path}"
        )

    with rules_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def collect_reference_files(reference_root):
    """
    Collect files controlled by the official WordPress distribution.

    Includes:
      - files in the WordPress root
      - everything below wp-admin
      - everything below wp-includes

    wp-content is intentionally excluded because it normally contains
    installation-specific plugins, themes, and uploads.
    """
    files = {}

    for path in reference_root.iterdir():
        if path.is_file():
            rel = str(path.relative_to(reference_root))
            files[rel] = path

    for dirname in CORE_DIRS:
        base = reference_root / dirname

        if not base.exists():
            continue

        for path in base.rglob("*"):
            if path.is_file():
                rel = str(path.relative_to(reference_root))
                files[rel] = path

    return files


def collect_site_core_files(site_root):
    """
    Collect files from locations relevant to WordPress core integrity.

    Includes:
      - every root-level file
      - everything below wp-admin
      - everything below wp-includes
    """
    files = {}

    for path in site_root.iterdir():
        if path.is_file():
            rel = str(path.relative_to(site_root))
            files[rel] = path

    for dirname in CORE_DIRS:
        base = site_root / dirname

        if not base.exists():
            continue

        for path in base.rglob("*"):
            if path.is_file():
                rel = str(path.relative_to(site_root))
                files[rel] = path

    return files


def determine_location(rel):
    """Describe where a file resides in the WordPress tree."""
    parts = Path(rel).parts

    if len(parts) == 1:
        return "root"

    if parts[0] in CORE_DIRS:
        return parts[0]

    return "other"


def file_signals(rel, location):
    """
    Record factual characteristics that may be useful to later AI triage.

    These are signals, not malware classifications.
    """
    path = Path(rel)
    name = path.name

    signals = []

    if path.suffix.lower() == ".php":
        signals.append("php-file")

    if name.startswith("."):
        signals.append("hidden-file")

    if location in CORE_DIRS:
        signals.append("core-controlled-location")

    if location == "root":
        signals.append("wordpress-root")

    return signals


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Compare a WordPress installation against a known-good "
            "WordPress distribution."
        )
    )

    parser.add_argument(
        "site_root",
        help="Root directory of the affected WordPress installation",
    )

    parser.add_argument(
        "reference_root",
        help="Root directory of the known-good WordPress distribution",
    )

    parser.add_argument(
        "output",
        help="JSON report filename",
    )

    parser.add_argument(
        "--rules",
        help=(
            "JSON file describing expected site-specific files such as "
            "wp-config.php and .htaccess"
        ),
    )

    args = parser.parse_args()

    site_root = Path(args.site_root).resolve()
    reference_root = Path(args.reference_root).resolve()
    output_path = Path(args.output)

    if not site_root.is_dir():
        raise NotADirectoryError(
            f"Site root does not exist: {site_root}"
        )

    if not reference_root.is_dir():
        raise NotADirectoryError(
            f"Reference root does not exist: {reference_root}"
        )

    site_file_rules = load_site_file_rules(args.rules)

    reference_files = collect_reference_files(reference_root)
    site_files = collect_site_core_files(site_root)

    results = {
        "reference_root": str(reference_root),
        "site_root": str(site_root),
        "rules_file": (
            str(Path(args.rules).resolve())
            if args.rules
            else None
        ),
        "summary": {
            "reference_files": len(reference_files),
            "identical": 0,
            "modified": 0,
            "missing": 0,
            "unexpected": 0,
            "unexpected_php": 0,
            "expected_site_specific": 0,
            "site_specific_review_required": 0,
        },
        "modified": [],
        "missing": [],
        "unexpected": [],
        "expected_site_specific": [],
    }

    #
    # 1. Compare all files belonging to the official WordPress
    #    distribution.
    #
    for rel, ref_path in sorted(reference_files.items()):
        site_path = site_root / rel

        if not site_path.is_file():
            results["summary"]["missing"] += 1

            results["missing"].append({
                "path": rel,
                "reference_sha256": sha256_file(ref_path),
                "reference_size": ref_path.stat().st_size,
            })

            continue

        ref_hash = sha256_file(ref_path)
        site_hash = sha256_file(site_path)

        if ref_hash == site_hash:
            results["summary"]["identical"] += 1

        else:
            results["summary"]["modified"] += 1

            results["modified"].append({
                "path": rel,
                "classification": "modified-official-core",
                "reference_sha256": ref_hash,
                "site_sha256": site_hash,
                "reference_size": ref_path.stat().st_size,
                "site_size": site_path.stat().st_size,
                "site_mtime": site_path.stat().st_mtime,
                "signals": file_signals(
                    rel,
                    determine_location(rel)
                ),
            })

    #
    # 2. Examine files that exist in the affected installation but
    #    are absent from the official WordPress distribution.
    #
    for rel, site_path in sorted(site_files.items()):

        # Already handled as an official WordPress file.
        if rel in reference_files:
            continue

        location = determine_location(rel)

        if location == "other":
            continue

        info = file_info(site_path, site_root)
        info["location"] = location

        #
        # Expected site-specific files are separated from unexpected
        # files, but remain available for security review.
        #
        if rel in site_file_rules:
            rule = site_file_rules[rel]

            info["classification"] = rule.get(
                "classification",
                "expected-site-specific"
            )

            info["review"] = rule.get(
                "review",
                "recommended"
            )

            info["priority"] = rule.get(
                "priority",
                "normal"
            )

            info["reason"] = rule.get(
                "reason",
                ""
            )

            info["signals"] = file_signals(rel, location)

            results["expected_site_specific"].append(info)

            results["summary"]["expected_site_specific"] += 1

            if info["review"] == "required":
                results["summary"][
                    "site_specific_review_required"
                ] += 1

            continue

        #
        # Everything else in a core-controlled location that is absent
        # from the official distribution is objectively unexpected.
        #
        info["classification"] = "unexpected-file"
        info["signals"] = file_signals(rel, location)

        results["unexpected"].append(info)
        results["summary"]["unexpected"] += 1

        if site_path.suffix.lower() == ".php":
            results["summary"]["unexpected_php"] += 1

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with output_path.open(
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            results,
            f,
            indent=2
        )

    print(
        json.dumps(
            results["summary"],
            indent=2
        )
    )

    print()
    print(f"Report written to: {output_path}")


if __name__ == "__main__":
    main()
