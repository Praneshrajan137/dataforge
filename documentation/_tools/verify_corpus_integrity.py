"""Deterministic integrity & epistemic gate for c:\\dev\\dataforge\\documentation\\.

Verifies:
1. Total population parity: 66/66 documents in 00_corpus_manifest.json and 01_sources/_manifest.csv.
2. Cryptographic checksum integrity: LF-normalized archive SHA-256 matches 00_corpus_manifest.json,
   and recorded raw SHA-256 matches _manifest.csv 100%.
3. Exhaustive dossier coverage: all 14 channel dossiers exist in 02_dossiers/, and every DOC-001..DOC-066
   has a section whose heading starts with `## DOC-XXX` in its assigned dossier, containing a link to its
   verbatim source, an epistemic/verification subsection, and all 6 strategic bucket tags.
4. Synthesis completeness: all 5 synthesis ledgers exist in 03_synthesis/ and are substantive, and every
   DOC-referencing row in the errata ledger carries an evidence reference (source line, URL, or UNVERIFIED).
5. Zero broken relative Markdown links across 00_*.md, 02_dossiers/*.md, and 03_synthesis/*.md.
6. Zero credential / secret leaks matching DataForge backend_gate SECRET_PATTERNS.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import re
import sys
from urllib.parse import unquote

DOC_ROOT = pathlib.Path(__file__).resolve().parent.parent

EXPECTED_DOSSIERS = [
    "02_dossiers/01_a16z_dossier.md",
    "02_dossiers/02_claude_code_classes_dossier.md",
    "02_dossiers/03_cursor_compile26_dossier.md",
    "02_dossiers/04_google_guide_dossier.md",
    "02_dossiers/05_jane_street_dossier.md",
    "02_dossiers/06_lennys_podcast_dossier.md",
    "02_dossiers/07_posts_context_dossier.md",
    "02_dossiers/08_rainmatter_eo_enterprise_dossier.md",
    "02_dossiers/09_sequoia_guide_dossier.md",
    "02_dossiers/10_sequoia_ai_dossier.md",
    "02_dossiers/11_south_park_commons_dossier.md",
    "02_dossiers/12_pragmatic_engineer_codex_dossier.md",
    "02_dossiers/13_yc_ai_guide_dossier.md",
    "02_dossiers/14_yc_guide_dossier.md",
]

EXPECTED_SYNTHESIS = [
    "03_synthesis/ERRATA_AND_VERIFICATION_LEDGER.md",
    "03_synthesis/ADAPT_CHANGE_REBUILD_MATRIX.md",
    "03_synthesis/UNASKED_WISDOM_AND_BLINDSPOTS.md",
    "03_synthesis/SOLO_FOUNDER_50_DOLLAR_PLAYBOOK.md",
    "03_synthesis/HYPOTHESIS_REGISTRY.md",
]

REQUIRED_BUCKETS = [
    "[ADAPT]",
    "[CHANGE]",
    "[BUILD-NEW]",
    "[REBUILD-0-TO-1]",
    "[REJECT / TRAP]",
    "[UNASKED-WISDOM]",
]

# Built dynamically so this file itself never trips literal secret scanners
SECRET_REGEXES = [
    re.compile("sk-" + r"ant-[A-Za-z0-9\-_]{16,}"),
    re.compile("sk-" + r"proj-[A-Za-z0-9\-_]{16,}"),
    re.compile("gh" + r"p_[A-Za-z0-9]{30,}"),
    re.compile("github_" + r"pat_[A-Za-z0-9_]{30,}"),
    re.compile("AK" + r"IA[0-9A-Z]{16}"),
    re.compile("AI" + r"za[0-9A-Za-z\-_]{35}"),
    re.compile("gl" + r"pat-[A-Za-z0-9\-_]{20,}"),
    re.compile("xo" + r"x[baprs]-[A-Za-z0-9\-]{16,}"),
    re.compile("-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]

MD_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
DOC_ID_RE = re.compile(r"\bDOC-\d{3}\b")
EVIDENCE_RE = re.compile(r"https?://|\bL\d+\b|UNVERIFIED")
SOURCE_LINK_RE = re.compile(r"\]\(\.\./01_sources/[^)]+\)")
EPISTEMIC_HEADING_RE = re.compile(r"^#{3,4} .*(epistemic|errata|verification)", re.IGNORECASE | re.MULTILINE)


def doc_section(text: str, doc_id: str) -> str | None:
    """Return the body of the '## DOC-XXX' section, ending at the next level-2 heading."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if re.match(rf"^## {re.escape(doc_id)}\b", ln)), None)
    if start is None:
        return None
    end = next((j for j in range(start + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def section_problems(section: str) -> list[str]:
    """Structural requirements every per-DOC section must meet."""
    problems = []
    if not SOURCE_LINK_RE.search(section):
        problems.append("no link to its verbatim file in ../01_sources/")
    if not EPISTEMIC_HEADING_RE.search(section):
        problems.append("no epistemic/errata/verification subsection")
    problems.extend(f"missing bucket tag {b}" for b in REQUIRED_BUCKETS if b not in section)
    return problems


def check_links(md_path: pathlib.Path, text: str, errors: list[str]) -> int:
    checked = 0
    # Strip fenced code blocks before scanning links
    stripped = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    for match in MD_LINK_RE.finditer(stripped):
        raw_target = match.group(1).strip()
        if not raw_target or raw_target.startswith(("#", "http://", "https://", "mailto:", "sidecar://", "conversation://")):
            continue
        if raw_target.startswith("file:///"):
            # Verify local c:/dev/dataforge paths if referenced
            clean = unquote(raw_target[len("file:///"):]).split("#")[0]
            target_path = pathlib.Path(clean)
            if "dataforge" in clean.lower() and not target_path.exists():
                errors.append(f"Broken file:/// link in {md_path.relative_to(DOC_ROOT)}: {raw_target}")
            checked += 1
            continue
        rel_clean = unquote(raw_target.split("#")[0]).strip()
        if not rel_clean:
            continue
        resolved = (md_path.parent / rel_clean).resolve()
        if not resolved.exists():
            errors.append(f"Broken relative link in {md_path.relative_to(DOC_ROOT)}: {raw_target}")
        checked += 1
    return checked


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DataForge documentation corpus integrity.")
    parser.add_argument("--unlock", action="store_true", help="Flip epoch_2_unlocked=true on 100%% pass.")
    args = parser.parse_args()

    errors: list[str] = []
    manifest_json_path = DOC_ROOT / "00_corpus_manifest.json"
    manifest_csv_path = DOC_ROOT / "01_sources" / "_manifest.csv"

    if not manifest_json_path.exists():
        print("FATAL: Missing 00_corpus_manifest.json", file=sys.stderr)
        return 1
    if not manifest_csv_path.exists():
        print("FATAL: Missing 01_sources/_manifest.csv", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_json_path.read_text(encoding="utf-8"))
    csv_rows = list(csv.DictReader(manifest_csv_path.open(encoding="utf-8")))
    docs = manifest.get("documents", [])

    if len(docs) != 66 or len(csv_rows) != 66:
        errors.append(f"Population mismatch: json={len(docs)}, csv={len(csv_rows)} (expected 66).")

    # 1. Verify 01_sources checksums and line counts
    total_lines = 0
    for idx, (doc, row) in enumerate(zip(docs, csv_rows), 1):
        expected_id = f"DOC-{idx:03d}"
        if doc.get("doc_id") != expected_id:
            errors.append(f"Unexpected doc_id at index {idx}: {doc.get('doc_id')}")
        if doc.get("source_sha256_raw") != row["sha256"].strip().lower():
            errors.append(f"Raw SHA mismatch vs _manifest.csv for {expected_id}")

        arch_path = DOC_ROOT / doc["archive_relpath"]
        if not arch_path.exists():
            errors.append(f"Missing archived source file: {doc['archive_relpath']}")
            continue
        raw_bytes = arch_path.read_bytes()
        if b"\r\n" in raw_bytes:
            errors.append(f"CRLF bytes found in LF-normalized archive: {doc['archive_relpath']}")
        actual_lf_sha = hashlib.sha256(raw_bytes).hexdigest()
        if actual_lf_sha != doc.get("archive_sha256_lf"):
            errors.append(f"Archive LF SHA mismatch on {expected_id}: {actual_lf_sha} != {doc.get('archive_sha256_lf')}")
        total_lines += len(raw_bytes.decode("utf-8").splitlines())

    if total_lines != 13476:
        errors.append(f"Total archived source lines = {total_lines}, expected 13476.")

    # 2. Verify top-level charter & master index
    for root_doc in ("00_CHARTER_AND_METHODOLOGY.md", "00_MASTER_INDEX.md"):
        p = DOC_ROOT / root_doc
        if not p.exists() or len(p.read_text(encoding="utf-8").splitlines()) < 60:
            errors.append(f"Missing or incomplete root doc: {root_doc}")

    # 3. Verify all 14 dossiers and per-DOC sections.
    # v2 (2026-10-30): a DOC counts as covered only if a level-2 heading STARTS with
    # "## DOC-XXX" (v1 accepted any heading that merely mentioned the ID, which let
    # cross-reference headings mask 7 unwritten docs). Coverage is judged by section
    # structure, not by file line counts (v1's >=90-line rule rewarded padding).
    dossier_texts: dict[str, str] = {}
    for d_rel in EXPECTED_DOSSIERS:
        dp = DOC_ROOT / d_rel
        if not dp.exists():
            errors.append(f"Missing channel dossier: {d_rel}")
            continue
        dossier_texts[d_rel] = dp.read_text(encoding="utf-8")

    for doc in docs:
        doc_id = doc["doc_id"]
        d_rel = doc["dossier_relpath"]
        section = doc_section(dossier_texts.get(d_rel, ""), doc_id)
        if section is None:
            errors.append(f"Missing '## {doc_id}' section for {doc['filename']} in {d_rel}")
            continue
        for problem in section_problems(section):
            errors.append(f"{doc_id} section in {d_rel}: {problem}")

    # 4. Verify all 5 synthesis files
    for s_rel in EXPECTED_SYNTHESIS:
        sp = DOC_ROOT / s_rel
        if not sp.exists():
            errors.append(f"Missing synthesis ledger: {s_rel}")
            continue
        stxt = sp.read_text(encoding="utf-8")
        if len(stxt.splitlines()) < 100:
            errors.append(f"Synthesis ledger too short (<100 lines): {s_rel}")

    # Every DOC-referencing table row in the errata ledger must carry evidence:
    # a source line (L123), a URL, or an explicit UNVERIFIED marker.
    errata_path = DOC_ROOT / "03_synthesis/ERRATA_AND_VERIFICATION_LEDGER.md"
    if errata_path.exists():
        for n, line in enumerate(errata_path.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("|") and DOC_ID_RE.search(line) and not EVIDENCE_RE.search(line):
                errors.append(f"ERRATA_AND_VERIFICATION_LEDGER.md L{n}: table row has no evidence reference")

    # ADAPT matrix must use all 6 buckets
    adapt_path = DOC_ROOT / "03_synthesis/ADAPT_CHANGE_REBUILD_MATRIX.md"
    if adapt_path.exists():
        atxt = adapt_path.read_text(encoding="utf-8")
        for bucket in REQUIRED_BUCKETS:
            if bucket not in atxt:
                errors.append(f"ADAPT_CHANGE_REBUILD_MATRIX.md missing bucket {bucket}")

    # 5. Check Markdown links & secret patterns across entire documentation tree
    links_checked = 0
    files_scanned = 0
    for fpath in sorted(DOC_ROOT.rglob("*")):
        if not fpath.is_file():
            continue
        files_scanned += 1
        content = fpath.read_text(encoding="utf-8", errors="replace")
        for rx in SECRET_REGEXES:
            if rx.search(content):
                errors.append(f"SECRET_PATTERN match in {fpath.relative_to(DOC_ROOT)}: {rx.pattern}")
        if fpath.suffix.lower() == ".md" and "01_sources" not in fpath.parts:
            links_checked += check_links(fpath, content, errors)

    if errors:
        print(f"VERIFICATION FAILED with {len(errors)} error(s):", file=sys.stderr)
        for err in errors[:50]:
            print(f"  - {err}", file=sys.stderr)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more.", file=sys.stderr)
        return 1

    if args.unlock:
        for doc in docs:
            doc["analysis_status"] = "verified_complete"
            doc["errata_logged"] = True
        manifest["epoch_1_complete"] = True
        manifest["epoch_2_unlocked"] = True
        manifest_json_path.write_bytes(
            (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        )

    print(
        f"PASS: 66/66 sources SHA-verified ({total_lines} lines), "
        f"66/66 DOC sections structurally complete in 14/14 dossiers, 5/5 synthesis ledgers complete, "
        f"{links_checked} links verified, {files_scanned} files scanned for secrets (0 hits). "
        f"epoch_2_unlocked={manifest.get('epoch_2_unlocked')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
