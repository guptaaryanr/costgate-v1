from __future__ import annotations


def test_package_version_exists() -> None:
    import costgate

    assert costgate.__version__


def test_cli_import_does_not_instantiate_openai_provider(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import costgate.cli as cli

    assert cli.app is not None


def test_provider_registry_is_lazy() -> None:
    from costgate.providers import available_providers

    assert "openai" in available_providers()
