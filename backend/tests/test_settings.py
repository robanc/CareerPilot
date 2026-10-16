import pytest
from fastapi.testclient import TestClient

import backend.app.main as main_module
from backend.app.settings import Mode, SettingsError, load_settings


# Unit tests pass an explicit mapping so the real environment never leaks in.

# Placeholder only: the .invalid domain never resolves, and nothing connects.
DEMO_URL = "postgresql+psycopg://demo_reader:placeholder@db.invalid:5432/demo"
PUBLIC_DEMO_ENV = {
    "CAREERPILOT_MODE": "public_demo",
    "CAREERPILOT_DEMO_DATABASE_URL": DEMO_URL,
}
FORBIDDEN_VARS = ["DATABASE_URL", "CAREERPILOT_ADMIN_DATABASE_URL"]
# Distinctive value so tests can prove it never appears in error messages.
FORBIDDEN_VALUE = "postgresql://owner:owner-secret-value@db.invalid/demo"


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
    settings = load_settings(PUBLIC_DEMO_ENV)

    assert settings.mode is Mode.PUBLIC_DEMO
    assert settings.is_public_demo is True
    assert settings.demo_database_url == DEMO_URL


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
    settings = load_settings({"RENDER": "true", **PUBLIC_DEMO_ENV})

    assert settings.mode is Mode.PUBLIC_DEMO
    assert settings.on_render is True


def test_empty_render_value_is_not_render():
    settings = load_settings({"RENDER": ""})

    assert settings.mode is Mode.LOCAL
    assert settings.on_render is False


def test_load_settings_reads_process_environment(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    for name in FORBIDDEN_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CAREERPILOT_MODE", "public_demo")
    monkeypatch.setenv("CAREERPILOT_DEMO_DATABASE_URL", DEMO_URL)

    settings = load_settings()

    assert settings.mode is Mode.PUBLIC_DEMO
    assert settings.demo_database_url == DEMO_URL


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


# --- public_demo database configuration -------------------------------------


@pytest.mark.parametrize("on_render", [False, True])
def test_public_demo_without_demo_database_url_fails_closed(on_render):
    environ = {"CAREERPILOT_MODE": "public_demo"}
    if on_render:
        environ["RENDER"] = "true"

    with pytest.raises(
        SettingsError, match="Refusing to start.*CAREERPILOT_DEMO_DATABASE_URL"
    ):
        load_settings(environ)


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_public_demo_with_blank_demo_database_url_fails_closed(value):
    with pytest.raises(SettingsError, match="non-empty CAREERPILOT_DEMO_DATABASE_URL"):
        load_settings({**PUBLIC_DEMO_ENV, "CAREERPILOT_DEMO_DATABASE_URL": value})


def test_public_demo_strips_demo_database_url():
    settings = load_settings(
        {**PUBLIC_DEMO_ENV, "CAREERPILOT_DEMO_DATABASE_URL": f"  {DEMO_URL}\n"}
    )

    assert settings.demo_database_url == DEMO_URL


@pytest.mark.parametrize("name", FORBIDDEN_VARS)
@pytest.mark.parametrize("value", [FORBIDDEN_VALUE, "", "   "])
@pytest.mark.parametrize("on_render", [False, True])
def test_public_demo_rejects_privileged_database_variables(name, value, on_render):
    """Presence alone is refused, even when empty or alongside a valid demo URL."""
    environ = {**PUBLIC_DEMO_ENV, name: value}
    if on_render:
        environ["RENDER"] = "true"

    with pytest.raises(SettingsError, match=f"Refusing to start.*{name} is set"):
        load_settings(environ)


@pytest.mark.parametrize("name", FORBIDDEN_VARS)
def test_privileged_variable_rejected_even_without_demo_database_url(name):
    with pytest.raises(SettingsError, match=f"{name} is set"):
        load_settings({"CAREERPILOT_MODE": "public_demo", name: FORBIDDEN_VALUE})


def test_all_present_privileged_variables_are_named():
    environ = {**PUBLIC_DEMO_ENV}
    environ.update({name: FORBIDDEN_VALUE for name in FORBIDDEN_VARS})

    with pytest.raises(SettingsError) as exc_info:
        load_settings(environ)

    message = str(exc_info.value)
    for name in FORBIDDEN_VARS:
        assert name in message


@pytest.mark.parametrize("name", FORBIDDEN_VARS)
def test_errors_never_include_database_url_values(name):
    with pytest.raises(SettingsError) as exc_info:
        load_settings({**PUBLIC_DEMO_ENV, name: FORBIDDEN_VALUE})

    message = str(exc_info.value)
    assert FORBIDDEN_VALUE not in message
    assert "owner-secret-value" not in message
    assert DEMO_URL not in message
    assert "placeholder" not in message


def test_settings_repr_hides_demo_database_url():
    settings = load_settings(PUBLIC_DEMO_ENV)

    assert DEMO_URL not in repr(settings)
    assert "placeholder" not in repr(settings)
    assert "PUBLIC_DEMO" in repr(settings)


def test_local_mode_ignores_database_variables():
    """Local mode keeps its defaults; these variables only matter in public_demo."""
    environ = {
        "CAREERPILOT_MODE": "local",
        "CAREERPILOT_DEMO_DATABASE_URL": DEMO_URL,
    }
    environ.update({name: FORBIDDEN_VALUE for name in FORBIDDEN_VARS})

    settings = load_settings(environ)

    assert settings.mode is Mode.LOCAL
    assert settings.demo_database_url is None


def test_default_mode_ignores_database_variables():
    settings = load_settings({name: FORBIDDEN_VALUE for name in FORBIDDEN_VARS})

    assert settings.mode is Mode.LOCAL
    assert settings.demo_database_url is None


def test_render_check_precedes_database_checks():
    """On Render without public_demo, the mode error is reported, not a URL error."""
    with pytest.raises(SettingsError, match="Refusing to start.*not set"):
        load_settings({"RENDER": "true", "DATABASE_URL": FORBIDDEN_VALUE})


@pytest.mark.parametrize(
    "extra_env",
    [
        {},
        {"CAREERPILOT_DEMO_DATABASE_URL": DEMO_URL, "DATABASE_URL": FORBIDDEN_VALUE},
        {
            "CAREERPILOT_DEMO_DATABASE_URL": DEMO_URL,
            "CAREERPILOT_ADMIN_DATABASE_URL": FORBIDDEN_VALUE,
        },
    ],
    ids=["missing-demo-url", "database-url-present", "admin-url-present"],
)
def test_app_startup_refused_on_public_demo_database_misconfiguration(
    monkeypatch, extra_env
):
    """The lifespan refuses to start before init_db touches any database."""

    def init_db_must_not_run():
        pytest.fail("init_db ran despite an unsafe public_demo configuration")

    monkeypatch.setattr(main_module, "init_db", init_db_must_not_run)
    monkeypatch.delenv("RENDER", raising=False)
    for name in ["CAREERPILOT_DEMO_DATABASE_URL", *FORBIDDEN_VARS]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CAREERPILOT_MODE", "public_demo")
    for name, value in extra_env.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(SettingsError, match="Refusing to start"):
        with TestClient(main_module.app):
            pass
