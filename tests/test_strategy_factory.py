import pytest

from drive_organizer.strategies.by_date import DateStrategy
from drive_organizer.strategies.by_project import ProjectTopicStrategy
from drive_organizer.strategies.by_type import FileTypeStrategy
from drive_organizer.strategies.factory import build, registered_names


def test_build_type():
    assert isinstance(build("type"), FileTypeStrategy)


def test_build_date_default():
    strat = build("date")
    assert isinstance(strat, DateStrategy)
    assert strat._year_only is False


def test_build_date_year_only():
    strat = build("date", year_only=True)
    assert isinstance(strat, DateStrategy)
    assert strat._year_only is True


def test_build_project():
    assert isinstance(build("project"), ProjectTopicStrategy)


def test_unknown_strategy_raises():
    with pytest.raises(ValueError, match="Strategia sconosciuta"):
        build("nonexistent")


def test_custom_not_in_registry():
    assert "custom" not in registered_names()


def test_registered_names_sorted():
    names = registered_names()
    assert names == sorted(names)
    assert {"type", "date", "project"}.issubset(set(names))
