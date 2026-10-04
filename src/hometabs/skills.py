"""Assemble the local Claude Code plugin that carries the agent's skills.

The plugin is built at startup under the state dir (``.state/plugin/``) from
two sources:

- the skills this project ships (``plugin/skills/`` in this package, MIT),
  e.g. ``sign-in``, which tells the agent to use the password manager;
- Aside's builtin skills listed in :data:`ASIDE_SKILLS`, copied unmodified
  from the user's local Aside install (``ASIDE_SKILLS_DIR``). They are not
  redistributed with this project; if one is missing the bot runs without it.

The CLI loads the result with ``--plugin-dir``, and only the skills returned
in :attr:`SkillPlugin.skills` are allowlisted.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

PLUGIN_NAME = "hometabs"
# Manifest + the skills authored in this repo; copied as the plugin's base.
PLUGIN_TEMPLATE_DIR = Path(__file__).resolve().parent / "plugin"
# Aside builtin skills the agent may use, by directory name.
ASIDE_SKILLS: tuple[str, ...] = ("1password",)

_MANIFEST = Path(".claude-plugin") / "plugin.json"
_IGNORE = shutil.ignore_patterns("__pycache__", ".DS_Store")


@dataclass(frozen=True)
class SkillPlugin:
    """A built plugin directory and the qualified names of its skills."""

    path: Path
    skills: tuple[str, ...]


def _skill_dirs(skills_dir: Path) -> list[Path]:
    if not skills_dir.is_dir():
        return []
    return sorted(p for p in skills_dir.iterdir() if (p / "SKILL.md").is_file())


def build_plugin(dest: Path, aside_skills_dir: Path | None) -> SkillPlugin:
    """(Re)build the plugin at *dest* and return what it contains.

    *dest* is replaced on every call, so an Aside update is picked up at the
    next start. Refuses to delete a non-empty directory that doesn't look like
    a plugin built here.
    """
    dest = dest.resolve()
    if dest.exists():
        if any(dest.iterdir()) and not (dest / _MANIFEST).is_file():
            raise RuntimeError(
                f"Refusing to replace {dest}: it isn't a plugin built by {PLUGIN_NAME}"
            )
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PLUGIN_TEMPLATE_DIR, dest, ignore=_IGNORE)

    manifest = json.loads((dest / _MANIFEST).read_text())
    if manifest.get("name") != PLUGIN_NAME:
        raise RuntimeError(f"Unexpected plugin name in {PLUGIN_TEMPLATE_DIR / _MANIFEST}")

    skills_dest = dest / "skills"
    names = [p.name for p in _skill_dirs(skills_dest)]
    for name in ASIDE_SKILLS:
        src = aside_skills_dir / name if aside_skills_dir else None
        if src is None or not (src / "SKILL.md").is_file():
            logger.warning(
                "Aside skill '{}' not found in {} (set ASIDE_SKILLS_DIR); running without it",
                name,
                aside_skills_dir,
            )
            continue
        if name in names:
            logger.warning("Skipping Aside skill '{}': a bundled skill has the same name", name)
            continue
        shutil.copytree(src, skills_dest / name, ignore=_IGNORE)
        names.append(name)
    return SkillPlugin(dest, tuple(f"{PLUGIN_NAME}:{n}" for n in names))
