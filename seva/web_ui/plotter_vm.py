"""Web data-plotter viewmodel for CSV parsing and chart DTO generation."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Dict, List


def _is_float(text: str) -> bool:
    """Return whether a value can be parsed as float."""
    try:
        float(text)
    except (TypeError, ValueError):
        return False
    return True


@dataclass
class WebPlotterVM:
    """Hold parsed CSV state and derive chart options for NiceGUI."""

    filename: str = ""
    columns: List[str] = field(default_factory=list)
    rows: List[Dict[str, str]] = field(default_factory=list)
    numeric_columns: List[str] = field(default_factory=list)
    x_column: str = ""
    y_column: str = ""
    y2_column: str = ""
    show_y2: bool = False
    log_x: bool = False

    def load_csv_bytes(self, content: bytes, *, filename: str = "") -> None:
        """Parse UTF-8 CSV bytes and derive initial plotting columns."""
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("CSV file has no header row.")
        parsed_rows = [dict(row) for row in reader]
        self.filename = filename
        self.columns = [str(field) for field in reader.fieldnames]
        self.rows = parsed_rows
        self.numeric_columns = self._detect_numeric_columns(parsed_rows, self.columns)
        if not self.numeric_columns:
            raise ValueError("CSV has no numeric columns for plotting.")
        self.x_column = self.numeric_columns[0]
        self.y_column = self.numeric_columns[1] if len(self.numeric_columns) > 1 else self.numeric_columns[0]
        self.y2_column = self.numeric_columns[2] if len(self.numeric_columns) > 2 else self.y_column

    def _detect_numeric_columns(self, rows: List[Dict[str, str]], columns: List[str]) -> List[str]:
        """Return columns where all non-empty values are numeric."""
        numeric: List[str] = []
        for column in columns:
            values = [str(row.get(column, "") or "").strip() for row in rows]
            non_empty = [value for value in values if value]
            if not non_empty:
                continue
            if all(_is_float(value) for value in non_empty):
                numeric.append(column)
        return numeric

    def chart_options(self) -> Dict:
        """Build ECharts options from current selection."""
        if not self.rows or not self.x_column or not self.y_column:
            return {
                "title": {"text": "No CSV loaded"},
                "xAxis": {"type": "category", "data": []},
                "yAxis": [{"type": "value"}],
                "series": [],
            }

        x_values = [self._safe_float(row.get(self.x_column)) for row in self.rows]
        y_values = [self._safe_float(row.get(self.y_column)) for row in self.rows]
        series = [
            {
                "name": self.y_column,
                "type": "line",
                "showSymbol": False,
                "data": y_values,
                "yAxisIndex": 0,
            }
        ]
        y_axes = [{"type": "value", "name": self.y_column}]
        if self.show_y2 and self.y2_column:
            y2_values = [self._safe_float(row.get(self.y2_column)) for row in self.rows]
            series.append(
                {
                    "name": self.y2_column,
                    "type": "line",
                    "showSymbol": False,
                    "data": y2_values,
                    "yAxisIndex": 1,
                }
            )
            y_axes.append({"type": "value", "name": self.y2_column})

        return {
            "title": {"text": self.filename or "SEVA Data Plotter"},
            "tooltip": {"trigger": "axis"},
            "legend": {"data": [series_item["name"] for series_item in series]},
            "xAxis": {
                "type": "value",
                "name": self.x_column,
                "scale": True,
                "axisLabel": {"formatter": "{value}"},
                "min": "dataMin",
                "max": "dataMax",
            },
            "yAxis": y_axes,
            "series": [self._attach_xy(series_item, x_values) for series_item in series],
            "dataZoom": [{"type": "inside"}, {"type": "slider"}],
        }

    def _attach_xy(self, series_item: Dict, x_values: List[float]) -> Dict:
        """Attach `(x,y)` tuples to a line-series definition."""
        y_values = series_item.get("data", [])
        series_item["data"] = [[x, y] for x, y in zip(x_values, y_values, strict=False)]
        return series_item

    @staticmethod
    def _safe_float(raw_value: str | None) -> float:
        """Parse float values and fallback to ``0.0`` for blanks."""
        if raw_value is None:
            return 0.0
        text = str(raw_value).strip()
        if not text:
            return 0.0
        return float(text)

    def export_csv_bytes(self) -> bytes:
        """Serialize current rows back to CSV bytes for browser download."""
        if not self.columns:
            raise ValueError("No CSV data loaded.")
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=self.columns)
        writer.writeheader()
        for row in self.rows:
            writer.writerow({key: row.get(key, "") for key in self.columns})
        return stream.getvalue().encode("utf-8")
