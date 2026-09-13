from pathlib import Path

import pytest

from enterprise_ai_platform.rag.manual_loader import load_manual_chunks

MANUALS_DIR = Path(__file__).resolve().parents[1] / "data" / "manuals"


def test_loads_both_manuals_into_distinct_chunks() -> None:
    chunks = load_manual_chunks(MANUALS_DIR)

    assert len(chunks) == 13
    assert len({chunk.id for chunk in chunks}) == 13
    assert sum(chunk.equipment_model == "AX-100" for chunk in chunks) == 5
    assert sum(chunk.equipment_model == "PX-200" for chunk in chunks) == 8

    assert any(
        chunk.equipment_model == "AX-100" and "5.5 mm/s" in chunk.content for chunk in chunks
    )
    assert any(
        chunk.equipment_model == "PX-200" and "7.1 mm/s" in chunk.content for chunk in chunks
    )


def test_missing_manuals_raise_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="No Markdown manuals found"):
        load_manual_chunks(tmp_path)
