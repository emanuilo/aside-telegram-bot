import pytest

from hometabs.skills import build_plugin

FAKE_1PASSWORD = (
    "---\nname: 1password\ndescription: Read this skill when the user uses 1Password.\n"
    "---\n# 1Password\n"
)


@pytest.fixture
def aside_skills_dir(tmp_path):
    """A fake Aside install's builtin skills dir with a 1password skill."""
    root = tmp_path / "aside-skills"
    (root / "1password").mkdir(parents=True)
    (root / "1password" / "SKILL.md").write_text(FAKE_1PASSWORD)
    (root / "slack").mkdir()  # not in ASIDE_SKILLS: must not be copied
    (root / "slack" / "SKILL.md").write_text("---\nname: slack\n---\n")
    return root


@pytest.fixture
def plugin(tmp_path, aside_skills_dir):
    return build_plugin(tmp_path / "state" / "plugin", aside_skills_dir)
