#!/usr/bin/env python3
"""Minimal self-check for assess.py -- no test framework, stdlib only.

Run directly: python3 test_assess.py
"""

from __future__ import annotations

import os
import shutil
import tempfile

from assess import CHECKS, DATA_VALIDATION, JOB_MIGRATION, ML_MIGRATION, METADATA_MIGRATION, assess


def _fixture_repo() -> str:
    root = tempfile.mkdtemp(prefix="migration-assess-test-")
    files = {
        "notebooks/etl.py": (
            "path = 'dbfs:/mnt/raw/orders'\n"
            "spark.sql('SELECT * FROM hive_metastore.bronze.orders')\n"
            "role = 'arn:aws:iam::123456789012:instance-profile/etl-role'\n"
        ),
        "notebooks/ml.py": (
            "model = mlflow.pyfunc.load_model('models:/churn_model/Production')\n"
            "for run in client.search_runs(['1']):\n"
            "    for k in run.data.metrics:\n"
            "        pass\n"
        ),
        "scripts/export_jobs.sh": "databricks jobs list -o json > jobs.json\n",
        "clusters/policy.json": '{"node_type_id": "i3.xlarge"}\n',
        "checks/reconcile.py": "assert source_count == target_count\n",
        "clean/util.py": "def add(a, b):\n    return a + b\n",
        # Should be skipped entirely.
        ".venv/lib/skip_me.py": "dbfs:/mnt/should/not/appear\n",
    }
    for rel, content in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
    return root


def main() -> int:
    root = _fixture_repo()
    try:
        report = assess(root)

        found_categories = {f.category for f in report.findings}
        assert "dbfs-path" in found_categories, found_categories
        assert "legacy-hive-reference" in found_categories, found_categories
        assert "cloud-identity-aws" in found_categories, found_categories
        assert "stage-based-model-uri" in found_categories, found_categories
        assert "mlflow-search-runs-pagination" in found_categories, found_categories
        assert "manual-job-cli-loop" in found_categories, found_categories
        assert "hardcoded-node-type" in found_categories, found_categories
        assert "hand-rolled-row-count-check" in found_categories, found_categories

        # .venv is skipped -- its dbfs: path must not appear anywhere.
        assert not any(".venv" in f.path for f in report.findings)

        # clean/util.py has no matches at all.
        assert not any(f.path.endswith("util.py") for f in report.findings)

        by_kind = report.by_kind()
        assert METADATA_MIGRATION in by_kind
        assert JOB_MIGRATION in by_kind
        assert DATA_VALIDATION in by_kind
        assert ML_MIGRATION in by_kind

        # Every check has all five fields populated (non-empty).
        for pattern, category, kind, tool, why in CHECKS:
            assert pattern.pattern and category and kind and tool and why

        # files_scanned counts real source files, not the skipped one.
        assert report.files_scanned == 6, report.files_scanned

        print(f"OK -- {len(report.findings)} findings across {report.files_scanned} files")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
