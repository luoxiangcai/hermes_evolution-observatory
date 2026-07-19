# -*- coding: utf-8 -*-
"""GEPA 进化管道采集器 — 读取 self-evolution output"""
import json
from pathlib import Path
from datetime import datetime

from .base import BaseCollector, CollectorResult


class GepaCollector(BaseCollector):
    name = "gepa"
    path_pattern = ""  # 路径不固定，取决于 self-evolution 安装位置
    known_schema_version = "v1"

    def __init__(self, hermes_home: Path, evolution_output_dir: Path = None):
        super().__init__(hermes_home)
        self.evolution_output_dir = evolution_output_dir or Path("output")

    def collect(self) -> CollectorResult:
        ts = datetime.utcnow().isoformat() + "Z"
        result = CollectorResult(
            source=self.name, data={}, schema_version=self.known_schema_version, timestamp=ts
        )

        if not self.evolution_output_dir.exists():
            result.status = "unavailable"
            result.error = "evolution output directory not found"
            return result

        try:
            runs = []
            for skill_dir in self.evolution_output_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                for ts_dir in skill_dir.iterdir():
                    if not ts_dir.is_dir():
                        continue
                    run_data = {"skill_name": skill_dir.name, "timestamp": ts_dir.name}

                    metrics_file = ts_dir / "metrics.json"
                    if metrics_file.exists():
                        try:
                            run_data["metrics"] = json.loads(metrics_file.read_text(encoding="utf-8"))
                        except Exception:
                            run_data["metrics"] = {"error": "failed to parse"}

                    evolved = ts_dir / "evolved_skill.md"
                    baseline = ts_dir / "baseline_skill.md"
                    run_data["has_evolved"] = evolved.exists()
                    run_data["has_baseline"] = baseline.exists()

                    runs.append(run_data)

            runs.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
            result.data = {"runs": runs, "total_runs": len(runs)}
        except Exception as e:
            result.status = "error"
            result.error = str(e)
        return result
