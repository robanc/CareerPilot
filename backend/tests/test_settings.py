import pytest
from fastapi.testclient import TestClient

import backend.app.main as main_module
from backend.app.settings import Mode, SettingsError, load_settings


# Unit tests pass an explicit mapping so the real environment never leaks in.


def test_default_mode_is_local():
    settings = load_settings({})

    assert settings.mode is Mode.LOCAL
    assert settings.on_render is False
    assert settings.is_public_demo is False


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_mode_is_local(value):
    assert load_settings({"CAREERPILOT_MODE": value}).mode is Mode.LOCAL


def test_explicit_local_mode():
    assert load_settings({"CAREERPILOT_MODE": "local"}).mode is Mode.LOCAL


def test_explicit_public_demo_mode():
    settings = load_settings({"CAREERPILOT_MODE": "public_demo"})

    assert settings.mode is Mode.PUBLIC_DEMO
    assert settings.is_public_demo is True


@pytest.mark.parametrize(
    "value",
    ["production", "PUBLIC_DEMO", "Local", "public-demo", "demo", "readonly"],
)
def test_invalid_mode_is_rejected(value):
    with pytest.raises(SettingsError) as exc_info:
        load_settings({"CAREERPILOT_MODE": value})

    message = str(exc_info.value)
    assert "CAREERPILOT_MODE" in message
    assert repr(value) in message
    assert "local" in message and "public_demo" in message


@pytest.mark.parametrize("render_value", ["true", "1", "false", "anything"])
def test_render_without_mode_fails_closed(render_value):
    with pytest.raises(SettingsError, match="Refusing to start.*not set"):
        load_settings({"RENDER": render_value})


def test_render_with_local_mode_fails_closed():
    with pytest.raises(SettingsError, match="Refusing to start.*'local'"):
        load_settings({"RENDER": "true", "CAREERPILOT_MODE": "local"})


def test_render_with_invalid_mode_is_rejected():
    with pytest.raises(SettingsError, match="Invalid CAREERPILOT_MODE"):
        load_settings({"RENDER": "true", "CAREERPILOT_MODE": "prod"})


def test_render_with_public_demo_mode_starts():
    settings = load_settings({"RENDER": "true", "CAREERPILOT_MODE": "public_demo"})

    assert settings.mode is Mode.PUBLIC_DEMO
    assert settings.on_render is True


def test_empty_render_value_is_not_render():
    settings = load_settings({"RENDER": ""})

    assert settings.mode is Mode.LOCAL
    assert settings.on_render is False


def test_load_settings_reads_process_environment(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("CAREERPILOT_MODE", "public_demo")

    assert load_settings().mode is Mode.PUBLIC_DEMO


def test_app_startup_refused_on_render_without_mode(monkeypatch):
    """The lifespan validates settings before init_db touches any database."""

    def init_db_must_not_run():
        pytest.fail("init_db ran despite an unsafe Render configuration")

    monkeypatch.setattr(main_module, "init_db", init_db_must_not_run)
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("CAREERPILOT_MODE", raising=False)

    with pytest.raises(SettingsError, match="Refusing to start"):
        with TestClient(main_module.app):
            pass
