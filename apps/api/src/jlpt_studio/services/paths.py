from __future__ import annotations

from pathlib import Path

from jlpt_studio.core.config import Settings
from jlpt_studio.core.errors import StudioError


def project_dir(settings: Settings, project_id: str) -> Path:
    path = settings.resolved_data_dir / "projects" / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def project_asset_dir(settings: Settings, project_id: str, category: str) -> Path:
    path = project_dir(settings, project_id) / category
    path.mkdir(parents=True, exist_ok=True)
    return path


def to_relative_project_path(settings: Settings, absolute_path: Path) -> str:
    try:
        return absolute_path.resolve().relative_to(settings.resolved_data_dir.resolve()).as_posix()
    except ValueError as error:
        raise StudioError(
            "UNSAFE_PATH", "Đường dẫn media nằm ngoài thư mục dữ liệu", status_code=400
        ) from error


def resolve_relative_project_path(settings: Settings, relative_path: str) -> Path:
    root = settings.resolved_data_dir.resolve()
    candidate = (root / relative_path).resolve()
    if root not in candidate.parents and candidate != root:
        raise StudioError("UNSAFE_PATH", "Đường dẫn media không hợp lệ", status_code=400)
    return candidate
