#!/usr/bin/env python3
"""Fail-closed public-safety validator for the FinSentinel case-study repository.

Run from anywhere:  python3 scripts/validate-public-case-study.py

Checks performed
----------------
1.  Required documents exist.
2.  The repository tree matches an allowlist (no copied product directories,
    no stray files).
3.  No environment, credential, key, or certificate files exist.
4.  No secret-like content: private-key blocks, cloud/API provider key
    patterns, JWT-like tokens, connection strings, credential assignments.
5.  No private or internal references: the private product repository URL,
    loopback host names, private hostnames, internal IP ranges, developer
    machine paths.
6.  No personal/customer-like data patterns in any text file: email addresses,
    phone numbers, IBAN-like values, card-like numbers. Examples must remain
    fabricated.
7.  Every Markdown link resolves to a local file that exists, or to an
    explicitly approved public URL.
8.  Markdown code fences are balanced.
9.  SVG assets are well-formed XML, contain no scripts, and reference nothing
    external.
10. Synthetic examples carry the required synthetic markers.
11. README carries the private-product notice and safety disclaimers.
12. No banned marketing phrases appear anywhere.

Failure mode: any finding prints the offending file and line and the script
exits non-zero. If a file cannot be decoded or parsed, that is also a finding:
the validator never guesses on unreadable input. Only ``.git`` is skipped: the
validator scans itself too. Pattern fragments below are assembled from pieces
so that the catalogue cannot match its own source text.
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
SKIP_DIRS = {".git"}

REQUIRED_FILES = (
    "README.md",
    "ARCHITECTURE.md",
    "EVALUATION.md",
    "THREAT-MODEL.md",
    "LIMITATIONS.md",
    "DISCLOSURE.md",
    "DECISIONS.md",
    "OWNERSHIP-AND-LICENSE.md",
    "DOCUMENTATION-LICENSE.md",
    "SECURITY.md",
    ".gitignore",
    "assets/architecture-public.svg",
    "assets/workflow-public.svg",
    "assets/demo-poster.svg",
    "examples/synthetic-transaction.json",
    "examples/synthetic-case-summary.json",
    "examples/benchmark-summary.json",
    "scripts/validate-public-case-study.py",
    ".github/workflows/public-docs-check.yml",
)

ALLOWED_TOP_LEVEL = {
    "README.md",
    "ARCHITECTURE.md",
    "EVALUATION.md",
    "THREAT-MODEL.md",
    "LIMITATIONS.md",
    "DISCLOSURE.md",
    "DECISIONS.md",
    "OWNERSHIP-AND-LICENSE.md",
    "DOCUMENTATION-LICENSE.md",
    "SECURITY.md",
    "LICENSE",
    ".gitignore",
    "assets",
    "examples",
    "scripts",
    ".github",
    ".git",
}

APPROVED_EXTERNAL_URLS = {
    "https://github.com/jeevesh2515",
    "https://creativecommons.org/licenses/by-nc-nd/4.0",
    "https://creativecommons.org/licenses/by/4.0",
    "https://finsentinel-chi.vercel.app",
}

FORBIDDEN_FILE_NAMES = {
    ".env",
    ".netrc",
    ".npmrc",
    ".pgpass",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
    "kubeconfig",
    "secrets",
    "secrets.json",
}
FORBIDDEN_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".tfstate")

# (label, compiled regex). Applied per line to every scanned text file.
DENY_PATTERNS = (
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("cloud access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("cloud secret assignment", re.compile(r"(?i)aws_?secret_?(?:access_)?key")),
    ("provider API key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    (
        "credential assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|apikey|secret|token|password|passwd|credential|dsn)\b"
            r"\s*[:=]\s*[\"']?[A-Za-z0-9_\-/+]{12,}"
        ),
    ),
    (
        "JWT-like token",
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    ),
    (
        "connection string",
        re.compile(
            r"(?i)\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|rediss|"
            r"amqp|amqps|mssql|sqlite|clickhouse)://"
        ),
    ),
    ("URL with embedded credentials", re.compile(r"[a-z][a-z0-9+.-]*://[^\s/]+:[^\s/@]+@")),
    ("loopback address", re.compile(r"\b127\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
    ("private IP (10/8)", re.compile(r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
    ("private IP (192.168/16)", re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b")),
    (
        "private IP (172.16/12)",
        re.compile(r"\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b"),
    ),
    ("link-local address", re.compile(r"\b169\.254\.\d{1,3}\.\d{1,3}\b")),
    ("loopback host name", re.compile(r"\b" + "local" + "host" + r"\b", re.IGNORECASE)),
    ("internal hostname", re.compile(r"\.(?:local|internal|corp|lan|intranet)\b", re.IGNORECASE)),
    (
        # Generic: matches any owner path pointing at a repository named like the
        # private product, without naming the private owner in this public file.
        "private product repository URL",
        re.compile(r"(?i)github\.com/[a-z0-9-]+/finsentinel(?:\.git)?\b"),
    ),
    ("email address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("phone number", re.compile(r"(?:\+44|\+1|0044|\btel:)\s?\d[\d\s().-]{6,}")),
    (
        "IBAN-like value",
        re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}\b"),
    ),
    ("developer machine path", re.compile(r"(?i)(?:/Users/[a-z0-9._-]+/|[A-Z]:\\\\Users\\\\)")),
)

# Card-like numbers are checked by Luhn, not by a bare digit-count regex, so that
# SVG coordinates (for example "500 258 C 545 222 ...") are not false positives.
CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){12,19}(?!\d)")


def luhn_valid(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0

# Banned phrases are assembled from fragments so this file never contains the
# phrases verbatim (it is scanned by its own check).
BANNED_PHRASES = (
    "-".join(("production", "grade")),
    " ".join(("production", "grade")),
    "-".join(("bank", "grade")),
    "-".join(("military", "grade")),
    "-".join(("zero", "hallucination")),
    " ".join(("zero", "hallucination")),
    "fully " + "autonomous",
    "guaranteed " + "detection",
    "100% " + "accurate",
    "regulatory " + "compliant",
    "fraud detection " + "accuracy",
    "statutory " + "precedent",
    "coverage " + "dial",
)

README_REQUIRED_PHRASES = (
    "private commercial product",
    "does not contain the product source code",
    "triage priority, not a fraud probability",
    "does not file regulatory reports",
    "humans approve, dismiss, or escalate",
    "do not predict real-world fraud-detection performance",
)

EXAMPLE_MARKERS = ("synthetic", "illustrative")

MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
MD_AUTOLINK = re.compile(r"<((?:https?)://[^>\s]+)>")
FENCE_LINE = re.compile(r"^\s*```")

findings: list[str] = []


def fail(message: str) -> None:
    findings.append(message)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def iter_files() -> list[Path]:
    files = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        files.append(path)
    return files


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        fail(f"[unreadable] {rel(path)}: cannot decode as UTF-8 ({exc}); cannot judge safety")
        return None


def check_required_files() -> None:
    for name in REQUIRED_FILES:
        if not (ROOT / name).is_file():
            fail(f"[missing] required file absent: {name}")


def check_tree_allowlist(files: list[Path]) -> None:
    for path in files:
        parts = path.relative_to(ROOT).parts
        if parts[0] not in ALLOWED_TOP_LEVEL:
            fail(f"[tree] {rel(path)}: not in the public-safe allowlist")
    github_dir = ROOT / ".github"
    if github_dir.is_dir():
        for path in sorted(github_dir.rglob("*")):
            if path.is_file() and rel(path) != ".github/workflows/public-docs-check.yml":
                fail(f"[tree] {rel(path)}: only the public-docs-check workflow is allowed under .github/")


def check_forbidden_files(files: list[Path]) -> None:
    for path in files:
        name = path.name.lower()
        if name.startswith(".env") or name in FORBIDDEN_FILE_NAMES:
            fail(f"[file] {rel(path)}: environment/credential file must not be present")
        if name.endswith(FORBIDDEN_SUFFIXES):
            fail(f"[file] {rel(path)}: key/certificate/state file must not be present")


def check_content_patterns(files: list[Path]) -> None:
    for path in files:
        text = read_text(path)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, pattern in DENY_PATTERNS:
                if pattern.search(line):
                    fail(f"[content] {rel(path)}:{lineno}: {label}")
            for candidate in CARD_CANDIDATE.findall(line):
                digits = re.sub(r"[ -]", "", candidate)
                if 13 <= len(digits) <= 19 and luhn_valid(digits):
                    fail(f"[content] {rel(path)}:{lineno}: card-like number (Luhn-valid)")
            lowered = line.lower()
            for phrase in BANNED_PHRASES:
                if phrase in lowered:
                    fail(f"[claim] {rel(path)}:{lineno}: banned marketing phrase '{phrase}'")


def check_markdown_links(files: list[Path]) -> None:
    for path in files:
        if path.suffix != ".md":
            continue
        text = read_text(path)
        if text is None:
            continue
        for target in MD_LINK.findall(text) + MD_AUTOLINK.findall(text):
            if target.startswith("#"):
                continue
            if target.startswith(("http://", "https://")):
                normalized = target.rstrip("/")
                if normalized not in APPROVED_EXTERNAL_URLS:
                    fail(
                        f"[link] {rel(path)}: external URL not on the approved list: {target}"
                    )
                continue
            if target.startswith("mailto:"):
                fail(f"[link] {rel(path)}: mailto links are not allowed in this repository")
            local = target.split("#", 1)[0]
            if not local:
                continue
            resolved = (path.parent / local).resolve()
            if not resolved.is_file():
                fail(f"[link] {rel(path)}: link target does not exist: {target}")


def check_markdown_fences(files: list[Path]) -> None:
    for path in files:
        if path.suffix != ".md":
            continue
        text = read_text(path)
        if text is None:
            continue
        fences = sum(1 for line in text.splitlines() if FENCE_LINE.match(line))
        if fences % 2 != 0:
            fail(f"[markdown] {rel(path)}: unbalanced code fences ({fences} fence lines)")


def check_svgs(files: list[Path]) -> None:
    for path in files:
        if path.suffix != ".svg":
            continue
        text = read_text(path)
        if text is None:
            continue
        try:
            ET.fromstring(text)
        except ET.ParseError as exc:
            fail(f"[svg] {rel(path)}: not well-formed XML ({exc})")
            continue
        if re.search(r"<\s*script", text, re.IGNORECASE):
            fail(f"[svg] {rel(path)}: contains a script element")
        stripped = text.replace("http://www.w3.org/2000/svg", "")
        if "http" in stripped:
            fail(f"[svg] {rel(path)}: references an external URL")
        if re.search(r"(?:xlink:href|href)\s*=\s*[\"'](?!#)", text):
            fail(f"[svg] {rel(path)}: contains a non-fragment href")


def check_examples(files: list[Path]) -> None:
    for path in files:
        if path.suffix != ".json" or "examples" not in path.relative_to(ROOT).parts:
            continue
        text = read_text(path)
        if text is None:
            continue
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            fail(f"[example] {rel(path)}: invalid JSON ({exc})")
            continue
        lowered = text.lower()
        for marker in EXAMPLE_MARKERS:
            if marker not in lowered:
                fail(f"[example] {rel(path)}: missing required marker '{marker}'")


def check_readme() -> None:
    readme = ROOT / "README.md"
    if not readme.is_file():
        return
    text = read_text(readme)
    if text is None:
        return
    lowered = text.lower()
    for phrase in README_REQUIRED_PHRASES:
        if phrase not in lowered:
            fail(f"[readme] missing required notice/disclaimer phrase: '{phrase}'")


def self_test() -> int:
    """--self-test: assert-based check of the validator's own decision logic."""
    valid = "".join(("4111", "1111", "1111", "1111"))
    assert luhn_valid(valid) is True
    assert luhn_valid(valid[:-1] + "2") is False
    assert luhn_valid("".join(("79927", "39871", "3"))) is True  # published Luhn vector
    sample = '<path d="M 500 258 C 545 222 570 170 604 122"/>'
    flagged = [
        candidate
        for candidate in CARD_CANDIDATE.findall(sample)
        if 13 <= len(re.sub(r"[ -]", "", candidate)) <= 19
        and luhn_valid(re.sub(r"[ -]", "", candidate))
    ]
    assert flagged == [], f"SVG coordinates must not be flagged: {flagged}"
    print("self-test: PASS (Luhn logic and SVG-coordinate non-flagging)")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    files = iter_files()
    check_required_files()
    check_tree_allowlist(files)
    check_forbidden_files(files)
    check_content_patterns(files)
    check_markdown_links(files)
    check_markdown_fences(files)
    check_svgs(files)
    check_examples(files)
    check_readme()

    scanned = len(files)
    if findings:
        print(f"FAIL: {len(findings)} finding(s) across {scanned} scanned files")
        for finding in findings:
            print(f"  - {finding}")
        print("\nThe validator fails closed. Resolve every finding before publishing.")
        return 1

    print(f"PASS: {scanned} files scanned, no findings")
    print("Checks: required files, tree allowlist, forbidden files, secret patterns,")
    print("        link targets, code fences, SVG safety, example markers, README notices,")
    print("        banned marketing phrases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
