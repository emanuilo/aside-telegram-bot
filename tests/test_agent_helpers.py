import base64
import json

from aside_telegram.agent import (
    PLUGIN_DIR,
    REPL_TOOL,
    BrowsingAgent,
    extract_images,
    summarize_tool_input,
)
from aside_telegram.config import AgentConfig


def test_extract_images_both_shapes():
    data = base64.b64encode(b"PNGDATA").decode()
    content = [
        {"type": "text", "text": "hi"},
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}},
        {"type": "image", "data": data, "mimeType": "image/png"},
    ]
    imgs = extract_images(content)
    assert [(i.data, i.media_type) for i in imgs] == [(b"PNGDATA", "image/jpeg"), (b"PNGDATA", "image/png")]
    assert extract_images("text only") == []


def test_summarize_tool_input():
    assert summarize_tool_input(REPL_TOOL, {"code": "// c\n\nawait page.goto('x')"}) == "await page.goto('x')"
    assert len(summarize_tool_input(REPL_TOOL, {"code": "x" * 500})) == 80
    assert summarize_tool_input(REPL_TOOL, {"title": "Opening example.com", "code": "x"}) == "Opening example.com"
    assert summarize_tool_input("mcp__other__t", {}) == "other__t"
    assert summarize_tool_input("Skill", {"skill": "aside-telegram:1password"}) == "skill: 1password"


def test_options_lock_down_tools():
    agent = BrowsingAgent(AgentConfig(oauth_token="tok", aside_command="/bin/aside"))
    opts = agent.build_options(resume=None)
    assert opts.model == "claude-sonnet-5-5" and opts.effort == "medium"
    # Only built-in tool is Skill; only auto-approved tool is the aside repl.
    assert opts.tools == ["Skill"] and opts.allowed_tools == [REPL_TOOL]
    assert opts.permission_mode == "dontAsk"
    assert opts.setting_sources == [] and opts.strict_mcp_config
    assert opts.mcp_servers["aside"]["command"] == "/bin/aside"
    assert opts.env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok"
    assert "ANTHROPIC_API_KEY" not in opts.env


def test_options_load_only_bundled_skills():
    opts = BrowsingAgent(AgentConfig(oauth_token="tok")).build_options(resume=None)
    assert opts.setting_sources == []  # no ~/.claude settings, CLAUDE.md, user skills/plugins
    assert opts.plugins == [{"type": "local", "path": str(PLUGIN_DIR)}]
    assert opts.skills == ["aside-telegram:1password"]


def test_cli_command_for_skills():
    from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

    opts = BrowsingAgent(AgentConfig(oauth_token="tok")).build_options(resume=None)
    transport = SubprocessCLITransport(prompt="", options=opts)
    transport._cli_path = "claude"
    cmd = transport._build_command()

    def flag(name):
        return cmd[cmd.index(name) + 1]

    assert flag("--tools") == "Skill"
    assert flag("--allowedTools") == f"{REPL_TOOL},Skill(aside-telegram:1password)"
    assert flag("--plugin-dir") == str(PLUGIN_DIR)
    assert "--setting-sources=" in cmd


def test_bundled_plugin_layout():
    manifest = json.loads((PLUGIN_DIR / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "aside-telegram"
    skill = (PLUGIN_DIR / "skills" / "1password" / "SKILL.md").read_text()
    assert skill.startswith("---\nname: 1password\n")
