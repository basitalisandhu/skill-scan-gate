"""SSG603 against the reserved-name rules in the Claude Code plugin documentation (checked 2026-10-28).

https://code.claude.com/docs/en/plugins/marketplace-reference#reserved-names
https://code.claude.com/docs/en/plugins/manifest-reference#name
"""

import pytest

from skill_scan_gate.patterns import reserved_marketplace_reason, reserved_plugin_reason

from conftest import rule_ids


@pytest.mark.parametrize(
    "name",
    [
        "claude-plugins-official",
        "knowledge-work-plugins",
        "life-sciences",
        "claude-plugins-community",
        "healthcare",
        "claude-plugin-directory",
        "claude.code.plugins",  # another spelling
        "first-party-plugins.",  # trailing dot
        "inline",
        "GitHub",
        "skills-dir",
        "toString",
        "claudeai-team",
        "official-claude-plugins",
        "claude-plugins-v2",
        "café-tools",  # non-ASCII
    ],
)
def test_reserved_marketplace_names(name):
    assert reserved_marketplace_reason(name)


@pytest.mark.parametrize(
    "name", ["team-tools", "acme-plugins", "sciences", "my-github-tools", "valueof", "life_sciences"]
)
def test_ordinary_marketplace_names(name):
    # Only an underscore does not count as a hyphen, so life_sciences is allowed.
    assert reserved_marketplace_reason(name) is None


@pytest.mark.parametrize(
    "name",
    [
        "claude",
        "Anthropics",
        "claude-code",
        "claude-mods",
        "claude-helper",
        "cc-plugin-lint",
        "official-claude-tools",
        "claude_helper",
        "anthropic-official",
    ],
)
def test_reserved_plugin_names(name):
    assert reserved_plugin_reason(name)


@pytest.mark.parametrize("name", ["notes-helper", "mcp-for-claude", "cc-plugin", "my-claw", "officially-yours"])
def test_ordinary_plugin_names(name):
    # mcp-for-claude is only a warning in claude plugin validate, so the gate does not flag it.
    assert reserved_plugin_reason(name) is None


def test_finding_names_the_reason(tree):
    mk = {"name": "claude.code.plugins", "owner": {"name": "x"}, "plugins": [{"name": "cc-plugin-x", "source": "./p"}]}
    root = tree({".claude-plugin/marketplace.json": mk})
    assert rule_ids(root).count("SSG603") == 2
