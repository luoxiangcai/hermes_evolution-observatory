# -*- coding: utf-8 -*-
"""技能库采集器 — .usage.json + SKILL.md 文件"""
import json
from pathlib import Path
from datetime import datetime

from .base import BaseCollector, CollectorResult


class SkillsCollector(BaseCollector):
    name = "skills"
    path_pattern = "skills"
    known_schema_version = "v2"

    def collect(self) -> CollectorResult:
        ts = datetime.utcnow().isoformat() + "Z"
        result = CollectorResult(
            source=self.name, data={}, schema_version=self.known_schema_version, timestamp=ts
        )

        skills_dir = self.hermes_home / "skills"
        if not skills_dir.exists():
            result.status = "unavailable"
            result.error = "skills directory not found"
            return result

        try:
            usage_data = self._read_usage_json()
            skills_list = self._scan_skills()
            archived = self._scan_archived()

            result.data = {
                "skills": skills_list,
                "usage_stats": usage_data,
                "archived": archived,
                "total_count": len(skills_list),
                "archived_count": len(archived),
            }
        except Exception as e:
            result.status = "error"
            result.error = str(e)
        return result

    def _read_usage_json(self) -> dict:
        path = self.hermes_home / "skills" / ".usage.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _scan_skills(self) -> list:
        skills_dir = self.hermes_home / "skills"
        skills = []
        for skill_md in skills_dir.rglob("SKILL.md"):
            try:
                content = skill_md.read_text(encoding="utf-8")
                name = skill_md.parent.name
                category = skill_md.parent.parent.name if skill_md.parent.parent != skills_dir else ""

                # 解析 YAML frontmatter — 用 PyYAML 完整支持 `>` 折叠和 `|` 保留换行
                frontmatter = {}
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        try:
                            import yaml as _yaml
                            parsed = _yaml.safe_load(parts[1]) or {}
                            if isinstance(parsed, dict):
                                frontmatter = parsed
                        except Exception:
                            # 兜底：不解析 folded/block，只抓单行 key:value
                            for line in parts[1].strip().split("\n"):
                                if ":" in line and not line.startswith(" "):
                                    k, v = line.split(":", 1)
                                    frontmatter[k.strip()] = v.strip().strip("'\"")
                # description 可能是字符串、也可能是 list/dict，统一转字符串
                desc = frontmatter.get("description", "")
                if not isinstance(desc, str):
                    desc = str(desc)
                desc = desc.strip()

                # 获取 usage 统计
                usage = self._get_usage_entry(name)

                skills.append({
                    "name": name,
                    "category": category,
                    "description": desc,
                    "version": (str(frontmatter.get("version", "1.0.0")) if not isinstance(frontmatter.get("version"), str) else frontmatter.get("version", "1.0.0")),
                    "path": str(skill_md.relative_to(self.hermes_home)),
                    "abs_path": str(skill_md.resolve()),
                    "size": len(content),
                    "usage": usage,
                    "state": usage.get("state", "active"),
                    "created_by": usage.get("created_by", "unknown"),
                    "pinned": usage.get("pinned", False),
                })
            except Exception as e:
                logger = __import__("logging").getLogger(__name__)
                logger.warning(f"Failed to read skill {skill_md}: {e}")
        return skills

    def _get_usage_entry(self, skill_name: str) -> dict:
        usage = self._read_usage_json()
        return usage.get(skill_name, {})

    def _scan_archived(self) -> list:
        archive_dir = self.hermes_home / "skills" / ".archive"
        if not archive_dir.exists():
            return []
        archived = []
        for item in archive_dir.iterdir():
            if item.is_dir():
                skill_md = item / "SKILL.md"
                archived.append({
                    "name": item.name,
                    "path": str(item.relative_to(self.hermes_home)),
                    "abs_path": str(item.resolve()),
                    "has_skill_md": skill_md.exists(),
                })
        return archived
