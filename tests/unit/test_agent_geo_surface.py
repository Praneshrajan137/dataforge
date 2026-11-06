"""Tests for agent-native discovery surfaces (`llms.txt` and `SKILL.md`)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from dataforge_mcp.server import create_server

from dataforge import cli

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_DECIMAL_FIGURE_RE = re.compile(r"(?<![\w.])(\d+\.\d{2,})(?![\w.])")


def test_llms_txt_conforms_and_all_links_resolve() -> None:
    llms_path = _REPO_ROOT / "llms.txt"
    assert llms_path.is_file(), "llms.txt must exist at repository root"
    text = llms_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    assert lines[0] == "# DataForge"
    assert lines[1].startswith("> ")
    assert any(line.startswith("## ") for line in lines)

    links = _LINK_RE.findall(text)
    assert len(links) >= 10
    for target in links:
        assert not target.startswith(("http://", "https://")), (
            f"Expected repo-local documentation link in llms.txt, got {target!r}"
        )
        resolved = (_REPO_ROOT / target).resolve()
        assert resolved.exists(), f"Broken link in llms.txt: {target!r}"

    # Zero unregistered decimal claims or retired names in llms.txt
    assert not _DECIMAL_FIGURE_RE.findall(text)
    lowered = text.lower()
    assert "beers" not in lowered
    assert "data_quality_env" not in lowered


def test_dataforge_verify_skill_frontmatter_and_command_truth() -> None:
    skill_path = _REPO_ROOT / ".agents" / "skills" / "dataforge-verify" / "SKILL.md"
    assert skill_path.is_file()
    raw = skill_path.read_text(encoding="utf-8")
    line_count = len(raw.splitlines())
    assert line_count <= 80, f"SKILL.md must stay concise (<=80 lines), got {line_count}"

    assert raw.startswith("---\n")
    _, frontmatter_str, body = raw.split("---\n", maxsplit=2)
    meta = yaml.safe_load(frontmatter_str)
    assert isinstance(meta, dict)
    assert meta.get("name") == "dataforge-verify"
    assert isinstance(meta.get("description"), str) and len(meta["description"]) >= 40

    registered_cli = cli.command_names()
    for subcmd in ("quickstart", "profile", "verify-apply", "attest", "revert"):
        assert subcmd in registered_cli
        assert f"dataforge {subcmd}" in body

    server = create_server()
    assert server.name == "DataForge"
    for tool_name in (
        "dataforge_profile",
        "dataforge_detect_errors",
        "dataforge_verify_fix",
        "dataforge_verify_and_apply",
        "dataforge_revert",
    ):
        assert tool_name in body
