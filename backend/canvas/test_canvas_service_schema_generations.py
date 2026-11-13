"""Every boot-path DDL of the app is witnessed: the generation chain from 0 reaches the live schema."""
from backend.canvas.canvas_service import CanvasService
from database.repositories.schema_generations import chain, rows


def test_boot_and_reopen_leave_contiguous_generations(tmp_path):
    for _ in range(2):
        service = CanvasService(tmp_path / "data")
        try:
            assert service.db.in_transaction is False
            assert chain(service.db, 0) is not None
            assert chain(service.db_for("draft"), 0) is not None
            assert rows(service.db)[0][3] == "CanvasService registry init: REGISTRY_SCHEMA"
            assert all(row[3].startswith("initialize_project_schema: ") for row in rows(service.db_for("draft")))
        finally:
            service.close()
