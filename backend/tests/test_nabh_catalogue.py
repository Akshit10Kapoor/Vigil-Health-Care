import json
from pathlib import Path

CATALOGUE_PATH = (
    Path(__file__).resolve().parents[1]
    / "orchestration"
    / "evidence_agent"
    / "nabh_chapter_map"
    / "chapters.json"
)


def load_catalogue():
    with open(CATALOGUE_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_catalogue_uses_sixth_edition():
    catalogue = load_catalogue()
    assert catalogue["edition"] == "6th"
    assert catalogue["effective_from"] == "2025-01-01"


def test_chapter_totals_match_official_summary():
    catalogue = load_catalogue()
    chapters = catalogue["chapters"]
    assert len(chapters) == 10
    assert sum(chapter["standards"] for chapter in chapters.values()) == 100
    assert sum(chapter["objective_elements"] for chapter in chapters.values()) == 639
    assert sum(chapter["core"] for chapter in chapters.values()) == 105
    assert sum(chapter["commitment"] for chapter in chapters.values()) == 457
    assert sum(chapter["achievement"] for chapter in chapters.values()) == 60
    assert sum(chapter["excellence"] for chapter in chapters.values()) == 17


def test_current_chapter_codes_and_names():
    chapters = load_catalogue()["chapters"]
    assert "IPC" in chapters
    assert chapters["IPC"]["name"] == "Infection Prevention and Control"
    assert "PSQ" in chapters
    assert chapters["PSQ"]["name"] == "Patient Safety and Quality Improvement"
    assert "HIC" not in chapters
    assert "CQI" not in chapters


def test_event_map_targets_known_chapters():
    catalogue = load_catalogue()
    event_map = catalogue["event_map"]
    assert set(event_map) == {
        "nursing_round",
        "consent_capture",
        "medication_order_documentation",
    }
    assert all(mapping["chapter"] in catalogue["chapters"] for mapping in event_map.values())
