from btengine.strategy.versioning import StrategyRegistry, StrategyVersion


def test_qualified_name() -> None:
    version = StrategyVersion(name="funding-momentum", version="1.0.0")
    assert version.qualified_name == "funding-momentum@1.0.0"


def test_registry_starts_empty() -> None:
    registry = StrategyRegistry()
    assert registry.list_names() == []
    assert registry.list_versions("anything") == []
    assert registry.get("anything", "1.0.0") is None


def test_register_and_get() -> None:
    registry = StrategyRegistry()
    version = StrategyVersion(name="funding-momentum", version="1.0.0", description="first cut")
    registry.register(version)
    assert registry.get("funding-momentum", "1.0.0") is version
    assert registry.list_names() == ["funding-momentum"]


def test_multiple_versions_of_the_same_strategy() -> None:
    registry = StrategyRegistry()
    v1 = StrategyVersion(name="funding-momentum", version="1.0.0")
    v2 = StrategyVersion(name="funding-momentum", version="2.0.0")
    registry.register(v1)
    registry.register(v2)
    versions = registry.list_versions("funding-momentum")
    assert {v.version for v in versions} == {"1.0.0", "2.0.0"}


def test_registering_same_name_and_version_overwrites() -> None:
    registry = StrategyRegistry()
    registry.register(StrategyVersion(name="x", version="1.0.0", description="old"))
    registry.register(StrategyVersion(name="x", version="1.0.0", description="new"))
    assert registry.get("x", "1.0.0").description == "new"
    assert len(registry.list_versions("x")) == 1


def test_multiple_strategy_names_are_independent() -> None:
    registry = StrategyRegistry()
    registry.register(StrategyVersion(name="a", version="1.0.0"))
    registry.register(StrategyVersion(name="b", version="1.0.0"))
    assert sorted(registry.list_names()) == ["a", "b"]
