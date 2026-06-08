from __future__ import annotations

from typing import Callable

from drive_organizer.strategies.base import OrganizationStrategy

_REGISTRY: dict[str, Callable[..., OrganizationStrategy]] = {}


def build(name: str, **kwargs) -> OrganizationStrategy:
    if name not in _REGISTRY:
        raise ValueError(f"Strategia sconosciuta: {name!r}. Disponibili: {sorted(_REGISTRY)}")
    return _REGISTRY[name](**kwargs)


def registered_names() -> list[str]:
    return sorted(_REGISTRY)


def _register(name: str) -> Callable:
    def decorator(fn: Callable[..., OrganizationStrategy]) -> Callable:
        _REGISTRY[name] = fn
        return fn
    return decorator


@_register("type")
def _type(**_) -> OrganizationStrategy:
    from drive_organizer.strategies.by_type import FileTypeStrategy
    return FileTypeStrategy()


@_register("date")
def _date(year_only: bool = False, **_) -> OrganizationStrategy:
    from drive_organizer.strategies.by_date import DateStrategy
    return DateStrategy(year_only=year_only)


@_register("project")
def _project(**_) -> OrganizationStrategy:
    from drive_organizer.strategies.by_project import ProjectTopicStrategy
    return ProjectTopicStrategy()
