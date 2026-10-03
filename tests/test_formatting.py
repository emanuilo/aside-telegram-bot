import pytest

from aside_telegram.formatting import markdown_to_telegram_html, split_message


def test_short_message_single_chunk():
    assert split_message("hello") == ["hello"]
    assert split_message("   ") == []


@pytest.mark.parametrize("limit", [50, 100, 4096])
def test_chunks_respect_limit_and_keep_content(limit):
    text = "\n\n".join(f"Paragraph {i} " + "word " * 30 for i in range(40))
    chunks = split_message(text, limit)
    assert all(len(c) <= limit for c in chunks)
    assert " ".join(" ".join(chunks).split()) == " ".join(text.split())


def test_prefers_paragraph_boundaries():
    a, b = "a" * 60, "b" * 60
    assert split_message(f"{a}\n\n{b}", 100) == [a, b]


def test_hard_cut_without_whitespace():
    chunks = split_message("x" * 250, 100)
    assert all(len(c) <= 100 for c in chunks)
    assert "".join(chunks) == "x" * 250


def test_code_fence_closed_and_reopened():
    code = "\n".join(f"line {i}" for i in range(60))
    text = f"Intro\n\n```python\n{code}\n```\n\nOutro"
    chunks = split_message(text, 120)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 120
        assert c.count("```") % 2 == 0, c
    assert chunks[1].startswith("```python")


def test_html_escapes_and_formats():
    out = markdown_to_telegram_html(
        "**Bold** & _it_ <tag> `a<b` [Ex](https://example.com/?a=1&b=2)"
    )
    assert "<b>Bold</b>" in out
    assert "&amp;" in out and "&lt;tag&gt;" in out
    assert "<i>it</i>" in out
    assert "<code>a&lt;b</code>" in out
    assert '<a href="https://example.com/?a=1&amp;b=2">Ex</a>' in out


def test_html_code_block_and_lists():
    out = markdown_to_telegram_html("# Title\n- one\n* two\n```js\nif (a < b && c) {}\n```")
    assert "<b>Title</b>" in out
    assert "• one" in out and "• two" in out
    assert '<pre><code class="language-js">if (a &lt; b &amp;&amp; c) {}</code></pre>' in out


def test_html_leaves_snake_case_alone():
    assert markdown_to_telegram_html("my_var_name and 2*3*4") == "my_var_name and 2*3*4"
