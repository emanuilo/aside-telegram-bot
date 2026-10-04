"""Model discovery (/v1/models). No network: httpx.MockTransport fakes the API."""

import asyncio
import json
import time
import typing

import httpx
import pytest
from claude_agent_sdk import ClaudeAgentOptions

from hometabs import models as M
from hometabs.auth import select_credential
from hometabs.models import ModelCatalog, ModelInfo, parse_models, resolve_effort


def _effort(*levels, supported=True):
    node = {"supported": supported}
    for lv in ("low", "medium", "high", "xhigh", "max"):
        node[lv] = {"supported": lv in levels}
    return node


def _entry(mid, created, effort=None, name=None):
    caps = {"effort": effort} if effort is not None else {}
    return {"id": mid, "display_name": name or mid, "created_at": created, "capabilities": caps}


def _client(pages, calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        after = request.url.params.get("after_id")
        return httpx.Response(200, json=pages[after])

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_sdk_levels_come_from_the_sdk_type():
    hint = typing.get_type_hints(ClaudeAgentOptions)["effort"]
    literal = next(a for a in typing.get_args(hint) if typing.get_origin(a) is typing.Literal)
    assert typing.get_args(literal) == M.SDK_EFFORT_LEVELS
    assert M.SDK_EFFORT_LEVELS[:3] == ("low", "medium", "high")


OAUTH = select_credential(None, "tok")
API_KEY = select_credential("key", None)


def test_headers_use_bearer_oauth():
    h = M.build_headers(OAUTH)
    assert h == {
        "Authorization": "Bearer tok",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "oauth-2025-04-20",
    }
    assert "x-api-key" not in h


def test_headers_use_x_api_key():
    h = M.build_headers(API_KEY)
    assert h == {"x-api-key": "key", "anthropic-version": "2023-06-01"}
    assert "Authorization" not in h and "anthropic-beta" not in h


def test_headers_prefer_api_key_when_both_set():
    h = M.build_headers(select_credential("key", "tok"))
    assert h["x-api-key"] == "key" and "Authorization" not in h


def test_headers_refuse_local_login():
    with pytest.raises(ValueError):
        M.build_headers(select_credential(None, None))


def test_parse_sorts_newest_first_and_filters_effort():
    future = _effort("high")
    future["ultra"] = {"supported": True}  # a level the SDK doesn't know
    models = parse_models(
        [
            _entry("old", "2024-01-01T00:00:00Z"),
            _entry("broken-date", "nope"),
            _entry(
                "new",
                "2026-09-28T00:00:00Z",
                _effort("low", "medium", "high", "xhigh", "max"),
                "New",
            ),
            _entry("partial", "2026-02-01T00:00:00Z", _effort("low", "high", "max")),
            _entry("noeffort", "2025-10-15T00:00:00Z", _effort("low", supported=False)),
            _entry("future", "2026-05-01T00:00:00Z", future),
            {"display_name": "no id"},
        ]
    )
    assert [m.id for m in models] == ["new", "future", "partial", "noeffort", "old", "broken-date"]
    by = {m.id: m for m in models}
    assert by["new"].display_name == "New"
    assert by["new"].effort_levels == ["low", "medium", "high", "xhigh", "max"]
    assert by["partial"].effort_levels == ["low", "high", "max"]
    assert by["noeffort"].effort_levels == []  # effort.supported = false
    assert by["old"].effort_levels == []  # no capabilities at all
    assert by["future"].effort_levels == ["high"]


def test_fetch_paginates_and_sends_oauth_headers():
    calls = []
    pages = {
        None: {"data": [_entry("a", "2026-01-01T00:00:00Z")], "has_more": True, "last_id": "a"},
        "a": {"data": [_entry("b", "2026-02-01T00:00:00Z")], "has_more": False, "last_id": "b"},
    }

    async def go():
        async with _client(pages, calls) as client:
            return await M.fetch_models(OAUTH, client=client)

    models = asyncio.run(go())
    assert [m.id for m in models] == ["b", "a"]
    assert len(calls) == 2
    for req in calls:
        assert req.url.host == "api.anthropic.com"
        assert req.headers["authorization"] == "Bearer tok"
        assert req.headers["anthropic-beta"] == M.OAUTH_BETA
        assert "x-api-key" not in req.headers
    assert calls[1].url.params["after_id"] == "a"


def test_fetch_sends_api_key_headers():
    calls = []
    pages = {None: {"data": [_entry("a", "2026-01-01T00:00:00Z")], "has_more": False}}

    async def go():
        async with _client(pages, calls) as client:
            return await M.fetch_models(API_KEY, client=client)

    assert [m.id for m in asyncio.run(go())] == ["a"]
    (req,) = calls
    assert req.url.host == "api.anthropic.com"
    assert req.headers["x-api-key"] == "key"
    assert req.headers["anthropic-version"] == M.API_VERSION
    assert "authorization" not in req.headers
    assert "anthropic-beta" not in req.headers


def test_fetch_raises_on_http_error():
    async def go():
        transport = httpx.MockTransport(lambda r: httpx.Response(401, json={}))
        async with httpx.AsyncClient(transport=transport) as client:
            await M.fetch_models(OAUTH, client=client)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(go())


def _write_cache(path, age, models=None):
    path.write_text(
        json.dumps(
            {
                "fetched_at": time.time() - age,
                "models": models
                if models is not None
                else [
                    {
                        "id": "cached",
                        "display_name": "Cached",
                        "created_at": "",
                        "effort_levels": ["high"],
                    }
                ],
            }
        )
    )


def test_cache_freshness(tmp_path):
    path = tmp_path / "c.json"
    _write_cache(path, 60)
    assert M.read_cache(path) == [ModelInfo("cached", "Cached", "", ["high"])]
    _write_cache(path, M.CACHE_TTL_SECONDS + 60)
    assert M.read_cache(path) is None
    assert M.read_cache(path, max_age=None)[0].id == "cached"
    _write_cache(path, -3600)  # clock moved backwards
    assert M.read_cache(path) is None
    for bad in ("not json", '{"models": []}', '{"fetched_at": 0, "models": [{"id": "x"}]}'):
        path.write_text(bad)
        assert M.read_cache(path, max_age=None) is None


def test_catalog_serves_fresh_cache_without_network(tmp_path, monkeypatch):
    path = tmp_path / "c.json"
    _write_cache(path, 60)

    async def boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(M, "fetch_models", boom)
    cat = ModelCatalog(None, "tok", path)
    assert [m.id for m in asyncio.run(cat.refresh())] == ["cached"]


def test_catalog_fetches_when_stale_and_writes_cache(tmp_path, monkeypatch):
    path = tmp_path / "c.json"
    _write_cache(path, M.CACHE_TTL_SECONDS + 60)

    async def fake(credential, client=None):
        assert (credential.mode, credential.secret) == ("oauth_token", "tok")
        return [ModelInfo("fresh", "Fresh", "", ["low"])]

    monkeypatch.setattr(M, "fetch_models", fake)
    cat = ModelCatalog(None, "tok", path)
    assert cat.models[0].id == "cached"  # stale list known before refresh
    assert [m.id for m in asyncio.run(cat.refresh())] == ["fresh"]
    assert M.read_cache(path)[0].id == "fresh"


def test_catalog_falls_back_silently(tmp_path, monkeypatch):
    path = tmp_path / "c.json"
    _write_cache(path, M.CACHE_TTL_SECONDS + 60)

    async def fail(credential, client=None):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(M, "fetch_models", fail)
    assert [m.id for m in asyncio.run(ModelCatalog(None, "tok", path).refresh())] == ["cached"]
    # No cache at all and no network: empty list, no exception.
    assert asyncio.run(ModelCatalog(None, "tok", tmp_path / "none.json").refresh()) == []


def test_catalog_uses_api_key_over_oauth(tmp_path, monkeypatch):
    seen = []

    async def fake(credential, client=None):
        seen.append((credential.mode, credential.secret))
        return [ModelInfo("m", "M", "", [])]

    monkeypatch.setattr(M, "fetch_models", fake)
    asyncio.run(ModelCatalog("key", "tok", tmp_path / "c.json").refresh())
    assert seen == [("api_key", "key")]


def test_catalog_local_login_never_uses_network(tmp_path, monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(M, "fetch_models", boom)
    for key, tok in ((None, None), ("", "  ")):
        cat = ModelCatalog(key, tok, tmp_path / "none.json")
        assert asyncio.run(cat.refresh(force=True)) == []


def test_catalog_failure_log_has_no_secrets(tmp_path, monkeypatch):
    from loguru import logger

    async def fail(credential, client=None):
        raise httpx.HTTPStatusError(
            f"401 with {credential.secret}",
            request=httpx.Request("GET", M.MODELS_URL, headers=M.build_headers(credential)),
            response=httpx.Response(401),
        )

    monkeypatch.setattr(M, "fetch_models", fail)
    lines: list[str] = []
    handler = logger.add(lambda m: lines.append(str(m)), level="DEBUG")
    try:
        asyncio.run(ModelCatalog("sk-secret-key", None, tmp_path / "c.json").refresh())
    finally:
        logger.remove(handler)
    text = "\n".join(lines)
    assert "HTTPStatusError" in text and "sk-secret-key" not in text


def test_resolve_by_id_name_or_unique_prefix(tmp_path):
    cat = ModelCatalog(None, None, tmp_path / "x.json")
    cat.models = [
        ModelInfo("claude-haiku-4-5-20251001", "Claude Haiku 4.5"),
        ModelInfo("claude-opus-5", "Claude Opus 5"),
        ModelInfo("claude-opus-5-5", "Claude Opus 5.5"),
    ]
    assert cat.resolve("claude-opus-5").id == "claude-opus-5"
    assert cat.resolve("claude haiku 4.5").id.startswith("claude-haiku")
    assert cat.resolve("claude-haiku-4-5").id == "claude-haiku-4-5-20251001"
    assert cat.resolve("claude-nope") is None


@pytest.mark.parametrize(
    "levels, preferred, expected",
    [
        (None, "max", "max"),  # unknown model: keep as is
        ([], "medium", None),  # no effort support: omit
        (["low", "medium", "high"], "medium", "medium"),
        (["low", "medium", "high", "max"], "xhigh", "high"),  # nearest lower
        (["high", "max"], "low", "high"),  # nothing lower: lowest supported
        (["low"], None, None),
    ],
)
def test_resolve_effort(levels, preferred, expected):
    assert resolve_effort(levels, preferred) == expected
