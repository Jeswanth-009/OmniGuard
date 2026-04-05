"""
OmniGuard CSV Data Module
Load local CSV datasets for API responses.
"""
import csv
import os
from pathlib import Path
from typing import Any


SUPPORTED_DATASETS = {
    "users": "users.csv",
    "urls": "urls.csv",
    "events": "events.csv",
}


class CsvDatasetNotFound(Exception):
    """Raised when a CSV dataset is missing or unsupported."""


class CsvDataStore:
    """Simple CSV-backed data store for local datasets."""

    def __init__(self, data_dir: str | None = None):
        configured_dir = data_dir or os.getenv("CSV_DATA_DIR", "app/data")
        self.data_dir = Path(configured_dir)

    def available_datasets(self) -> list[dict[str, Any]]:
        """Return supported datasets with availability metadata."""
        datasets: list[dict[str, Any]] = []
        for name, filename in SUPPORTED_DATASETS.items():
            file_path = self.data_dir / filename
            datasets.append(
                {
                    "dataset": name,
                    "file": filename,
                    "available": file_path.exists(),
                }
            )
        return datasets

    def _resolve_dataset_file(self, dataset: str) -> Path:
        dataset_name = dataset.lower().strip()
        filename = SUPPORTED_DATASETS.get(dataset_name)
        if not filename:
            raise CsvDatasetNotFound(
                f"Unsupported dataset '{dataset}'. Supported: {', '.join(SUPPORTED_DATASETS.keys())}"
            )

        file_path = self.data_dir / filename
        if not file_path.exists():
            raise CsvDatasetNotFound(
                f"CSV file not found: {file_path}. Place file in app/data or set CSV_DATA_DIR."
            )

        return file_path

    def get_dataset(self, dataset: str, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a CSV dataset and return paginated rows with metadata."""
        file_path = self._resolve_dataset_file(dataset)

        with file_path.open("r", encoding="utf-8", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))

        bounded_limit = max(1, min(limit, 1000))
        bounded_offset = max(0, offset)
        paged_rows = rows[bounded_offset: bounded_offset + bounded_limit]

        return {
            "source": "csv",
            "dataset": dataset.lower().strip(),
            "file": file_path.name,
            "total_items": len(rows),
            "limit": bounded_limit,
            "offset": bounded_offset,
            "data": paged_rows,
        }


csv_store = CsvDataStore()
