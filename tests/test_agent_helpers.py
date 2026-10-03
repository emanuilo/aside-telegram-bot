import base64

from aside_telegram.agent import BrowsingAgent, REPL_TOOL, extract_images, summarize_tool_input
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


def test_options_lock_down_tools():
    agent = BrowsingAgent(AgentConfig(oauth_token="tok", aside_command="/bin/aside"))
    opts = agent.build_options(resume=None)
    assert opts.model == "claude-sonnet-5-5" and opts.effort == "medium"
    assert opts.tools == [] and opts.allowed_tools == [REPL_TOOL]
    assert opts.permission_mode == "dontAsk"
    assert opts.setting_sources == [] and opts.strict_mcp_config
    assert opts.mcp_servers["aside"]["command"] == "/bin/aside"
    assert opts.env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok"
    assert "ANTHROPIC_API_KEY" not in opts.env
