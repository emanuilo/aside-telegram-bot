import json

import pytest

from hometabs.agent import instructions_fingerprint
from hometabs.skills import PLUGIN_TEMPLATE_DIR, build_plugin

from .conftest import FAKE_1PASSWORD


def test_shipped_plugin_has_only_our_skills():
    manifest = json.loads((PLUGIN_TEMPLATE_DIR / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "hometabs"
    shipped = sorted(p.name for p in (PLUGIN_TEMPLATE_DIR / "skills").iterdir())
    assert shipped == ["sign-in"]  # Aside's skills are never vendored
    skill = (PLUGIN_TEMPLATE_DIR / "skills" / "sign-in" / "SKILL.md").read_text()
    assert skill.startswith("---\nname: sign-in\n")


def test_build_copies_aside_skill_unmodified(plugin, aside_skills_dir):
    assert plugin.skills == ("hometabs:sign-in", "hometabs:1password")
    assert (plugin.path / ".claude-plugin" / "plugin.json").is_file()
    assert (plugin.path / "skills" / "sign-in" / "SKILL.md").is_file()
    assert (plugin.path / "skills" / "1password" / "SKILL.md").read_text() == FAKE_1PASSWORD
    assert not (plugin.path / "skills" / "slack").exists()


def test_missing_aside_skills_runs_without_them(tmp_path):
    plugin = build_plugin(tmp_path / "plugin", tmp_path / "nope")
    assert plugin.skills == ("hometabs:sign-in",)
    assert build_plugin(tmp_path / "plugin2", None).skills == ("hometabs:sign-in",)


def test_rebuild_replaces_old_contents(tmp_path, aside_skills_dir):
    dest = tmp_path / "plugin"
    build_plugin(dest, aside_skills_dir)
    (dest / "skills" / "stale").mkdir()
    plugin = build_plugin(dest, tmp_path / "nope")
    assert not (dest / "skills" / "stale").exists()
    assert not (dest / "skills" / "1password").exists()
    assert plugin.skills == ("hometabs:sign-in",)


def test_refuses_to_replace_foreign_directory(tmp_path):
    dest = tmp_path / "precious"
    dest.mkdir()
    (dest / "file.txt").write_text("keep me")
    with pytest.raises(RuntimeError):
        build_plugin(dest, None)
    assert (dest / "file.txt").read_text() == "keep me"


def test_fingerprint_tracks_loaded_skills(tmp_path, aside_skills_dir):
    base = instructions_fingerprint(build_plugin(tmp_path / "a", aside_skills_dir))
    # Stable across rebuilds and locations.
    assert instructions_fingerprint(build_plugin(tmp_path / "b", aside_skills_dir)) == base
    # An Aside update changes it.
    (aside_skills_dir / "1password" / "SKILL.md").write_text(FAKE_1PASSWORD + "\nNew step.\n")
    assert instructions_fingerprint(build_plugin(tmp_path / "c", aside_skills_dir)) != base
    # So does running without the Aside skill.
    assert instructions_fingerprint(build_plugin(tmp_path / "d", None)) != base
