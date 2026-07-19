# -*- coding: utf-8 -*-
"""Curator 日志采集器"""
import json
from pathlib import Path
from datetime import datetime

from .base import BaseCollector, CollectorResult


class CuratorCollector(BaseCollector):
    name = "curator"
    path_pattern = "logs/curator"
    known_schema_version = "v2"

    def collect(self) -> CollectorResult:
        ts = datetime.utcnow().isoformat() + "Z"
        result = CollectorResult(
            source=self.name, data={}, schema_version=self.known_schema_version, timestamp=ts
        )

        curator_dir = self.hermes_home / "logs" / "curator"
        if not curator_dir.exists():
            result.status = "unavailable"
            result.error = "curator logs directory not found"
            return result

        try:
            runs = []
            for run_dir in sorted(curator_dir.iterdir(), reverse=True):
                if not run_dir.is_dir():
                    continue
                run_data = {"timestamp": run_dir.name, "run_json": None, "report_md": None}

                run_json = run_dir / "run.json"
                if run_json.exists():
                    try:
                        run_data["run_json"] = json.loads(run_json.read_text(encoding="utf-8"))
                    except Exception:
                        run_data["run_json"] = {"error": "failed to parse"}

                report_md = run_dir / "REPORT.md"
                if report_md.exists():
                    run_data["report_md"] = report_md.read_text(encoding="utf-8")

                runs.append(run_data)

            result.data = {"runs": runs, "total_runs": len(runs)}
        except Exception as e:
            result.status = "error"
            result.error = str(e)
        return result
