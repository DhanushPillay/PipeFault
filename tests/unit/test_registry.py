from __future__ import annotations

import pytest

from pipefault.inject import registry
from pipefault.inject.base import InjectionResult
from pipefault.inject.coercion import SilentCoercion
from pipefault.inject.duplicate import DuplicateIngestion
from pipefault.inject.fanout import JoinFanout
from pipefault.inject.late_dimension import LatestVersionJoin


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("D1", JoinFanout),
        ("D3", LatestVersionJoin),
        ("D5", DuplicateIngestion),
        ("D6", SilentCoercion),
    ],
)
def test_builtin_injectors_load_on_demand(name: str, expected: type) -> None:
    assert isinstance(registry.get(name.lower()), expected)
    assert name in registry.available()


def test_unknown_injector_still_fails() -> None:
    with pytest.raises(ValueError, match="unknown injector"):
        registry.get("D99")


def test_register_and_lookup_round_trip() -> None:
    class Dummy:
        name = "D99-test"

        def apply(self, frame, *, severity: float, seed: int) -> InjectionResult:
            raise NotImplementedError

    injector = registry.register(Dummy())
    assert registry.get("d99-test") is injector
    assert "D99-TEST" in registry.available()
    with pytest.raises(ValueError, match="already registered"):
        registry.register(Dummy())
