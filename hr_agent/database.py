from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from threading import RLock

import pandas as pd

from .settings import PROJECT_ROOT


class HRDatabase:
    """Read-only service database built from the configured CSV sources."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self._lock = RLock()

    @classmethod
    def from_project_files(cls, project_root: Path = PROJECT_ROOT) -> "HRDatabase":
        config_path = project_root / "hr_data_files.json"
        with config_path.open(encoding="utf-8") as config_file:
            file_config = json.load(config_file)

        connection = sqlite3.connect(":memory:", check_same_thread=False)
        for table, config_key in (
            ("employees", "EMPLOYEES_FILE"),
            ("departments", "DEPARTMENTS_FILE"),
            ("absences", "ABSENCES_FILE"),
        ):
            configured_path = Path(file_config[config_key])
            csv_path = (
                configured_path
                if configured_path.is_absolute()
                else project_root / configured_path
            )
            pd.read_csv(csv_path).to_sql(
                table,
                connection,
                index=False,
                if_exists="replace",
            )

        return cls(connection)

    def execute(
        self,
        sql: str,
        parameters: tuple[object, ...] = (),
    ) -> tuple[list[str], list[tuple]]:
        with self._lock:
            cursor = self.connection.cursor()
            cursor.execute(sql, parameters)
            rows = cursor.fetchall()
            columns = [
                description[0]
                for description in (cursor.description or [])
            ]
        return columns, rows

    def review_records(self) -> list[dict[str, object]]:
        sql = """
        SELECT
            e.employee_id,
            e.first_name,
            e.last_name,
            e.job_title,
            d.department_name,
            e.performance_review
        FROM employees e
        LEFT JOIN departments d
            ON e.department_id = d.department_id
        WHERE e.performance_review IS NOT NULL
          AND TRIM(e.performance_review) <> ''
        ORDER BY e.employee_id
        """
        columns, rows = self.execute(sql)
        return [dict(zip(columns, row)) for row in rows]
