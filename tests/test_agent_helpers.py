import base64

from hometabs.agent import (
    REPL_TOOL,
    BrowsingAgent,
    extract_images,
    summarize_tool_input,
)
from hometabs.config import AgentConfig


def test_extract_images_both_shapes():
    data = base64.b64encode(b"PNGDATA").decode()
    content = [
        {"type": "text", "text": "hi"},
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}},
        {"type": "image", "data": data, "mimeType": "image/png"},
    ]
    imgs = extract_images(content)
    assert [(i.data, i.media_type) for i in imgs] == [
        (b"PNGDATA", "image/jpeg"),
        (b"PNGDATA", "image/png"),
    ]
    assert extract_images("text only") == []


def test_summarize_tool_input():
    assert (
        summarize_tool_input(REPL_TOOL, {"code": "// c\n\nawait page.goto('x')"})
        == "await page.goto('x')"
    )
    assert len(summarize_tool_input(REPL_TOOL, {"code": "x" * 500})) == 80
    assert (
        summarize_tool_input(REPL_TOOL, {"title": "Opening example.com", "code": "x"})
        == "Opening example.com"
    )
    assert summarize_tool_input("mcp__other__t", {}) == "other__t"
    assert summarize_tool_input("Skill", {"skill": "hometabs:1password"}) == "skill: 1password"


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
    assert agent.auth_mode == "oauth_token"


def test_options_inject_only_the_api_key_when_both_are_set():
    agent = BrowsingAgent(AgentConfig(api_key="key", oauth_token="tok"))
    opts = agent.build_options(resume=None)
    assert opts.env["ANTHROPIC_API_KEY"] == "key"
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in opts.env
    assert agent.auth_mode == "api_key"


def test_agent_config_repr_hides_credentials():
    text = repr(AgentConfig(api_key="secret-key", oauth_token="secret-token"))
    assert "secret-key" not in text and "secret-token" not in text


def _agent_with_plugin(plugin):
    cfg = AgentConfig(oauth_token="tok", plugin_dir=plugin.path, skills=plugin.skills)
    return BrowsingAgent(cfg)


def test_options_load_only_plugin_skills(plugin):
    opts = _agent_with_plugin(plugin).build_options(resume=None)
    assert opts.setting_sources == []  # no ~/.claude settings, CLAUDE.md, user skills/plugins
    assert opts.plugins == [{"type": "local", "path": str(plugin.path)}]
    assert opts.skills == ["hometabs:sign-in", "hometabs:1password"]


def test_options_without_plugin_allow_no_skills():
    opts = BrowsingAgent(AgentConfig(oauth_token="tok")).build_options(resume=None)
    assert opts.plugins == [] and opts.skills == []


def test_cli_command_for_skills(plugin):
    from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

    opts = _agent_with_plugin(plugin).build_options(resume=None)
    transport = SubprocessCLITransport(prompt="", options=opts)
    transport._cli_path = "claude"
    cmd = transport._build_command()

    def flag(name):
        return cmd[cmd.index(name) + 1]

    assert flag("--tools") == "Skill"
    assert flag("--allowedTools") == (
        f"{REPL_TOOL},Skill(hometabs:sign-in),Skill(hometabs:1password)"
    )
    assert flag("--plugin-dir") == str(plugin.path)
    assert "--setting-sources=" in cmd
