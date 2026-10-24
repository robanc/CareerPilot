"""Backend operating-mode configuration.

CareerPilot runs in exactly one of two modes, selected by CAREERPILOT_MODE:

- ``local`` (default): the developer's own instance with full read/write
  access. This is what Docker Compose and the test suite use.
- ``public_demo``: a publicly reachable demonstration instance.

WARNING: public_demo is NOT SAFE TO DEPLOY yet. It blocks HTTP writes (see
readonly.py), uses read-only database sessions, rate limits and size limits
requests (limits.py), caps resume input lengths (schemas.py), and at startup
refuses a database role that is not strictly SELECT-only (database.py). The
fictional seed lives in backend/scripts/seed_demo_data.py. But the
SELECT-only demo role is not provisioned or verified on the hosting
platform, and the rate limiter's client address behind the platform's
proxy is unverified. Do not expose a public_demo instance until both are
resolved and tested.

public_demo database configuration (settings-level only): startup requires a
non-empty CAREERPILOT_DEMO_DATABASE_URL, intended to hold the credentials of
a SELECT-only database role. Startup is refused if DATABASE_URL or
CAREERPILOT_ADMIN_DATABASE_URL is present at all (even empty), so owner or
administrative credentials -- for example a connection string injected by
linking a Render database -- never reach the public API process. database.py
connects with CAREERPILOT_DEMO_DATABASE_URL only (never POSTGRES_*) and
validates its format, and makes those sessions read-only with a short
statement timeout. The demo role's actual privileges are the
database-level security boundary (the read-only session is
defense-in-depth): startup verifies them through the demo connection and
fails closed, but the role itself is NOT provisioned yet.
Error messages name these variables but never include their values.

Render fail-closed rule: when the process appears to run on Render, startup is
refused unless CAREERPILOT_MODE is explicitly ``public_demo``, so a hosted
instance can never silently fall back to the unrestricted local mode.

Render detection (UNVERIFIED -- confirm before deployment): Render's
documentation describes a ``RENDER`` environment variable set on its services.
This has not been confirmed against a real CareerPilot Render service. To bias
towards failing closed, any non-empty ``RENDER`` value counts as Render. If
Render does not set this variable, detection silently fails and the guard does
nothing, so verify it in the Render shell (and set CAREERPILOT_MODE explicitly
in the service configuration) before relying on it.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum


MODE_ENV_VAR = "CAREERPILOT_MODE"
RENDER_ENV_VAR = "RENDER"
DEMO_DATABASE_URL_ENV_VAR = "CAREERPILOT_DEMO_DATABASE_URL"
# Variables that may carry owner or administrative database credentials and
# must never be visible to a public_demo process.
FORBIDDEN_PUBLIC_DEMO_ENV_VARS = ("DATABASE_URL", "CAREERPILOT_ADMIN_DATABASE_URL")


class Mode(str, Enum):
    LOCAL = "local"
    PUBLIC_DEMO = "public_demo"


class SettingsError(RuntimeError):
    """Raised when the configuration is invalid or unsafe to start with."""


@dataclass(frozen=True)
class Settings:
    mode: Mode
    on_render: bool
    metrics_enabled: bool = False
    # Set only in public_demo. Excluded from repr so the credentials it
    # contains are never printed by logging or a failing test.
    demo_database_url: str | None = field(default=None, repr=False)

    @property
    def is_public_demo(self) -> bool:
        return self.mode is Mode.PUBLIC_DEMO


def _is_render(environ: Mapping[str, str]) -> bool:
    # Any non-empty value counts, including "false": misdetecting a non-Render
    # host only forces an explicit mode, while missing Render is unsafe.
    return bool(environ.get(RENDER_ENV_VAR, "").strip())


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Build Settings from the environment (or the given mapping, for tests).

    An unset or empty CAREERPILOT_MODE means ``local``. Any other value must
    match a mode name exactly; anything else raises SettingsError.
    In public_demo, the database variables are validated as described in
    the module docstring.
    """
    if environ is None:
        environ = os.environ

    raw_mode = environ.get(MODE_ENV_VAR, "").strip()
    on_render = _is_render(environ)

    if not raw_mode:
        mode = Mode.LOCAL
    else:
        try:
            mode = Mode(raw_mode)
        except ValueError:
            allowed = ", ".join(m.value for m in Mode)
            raise SettingsError(
                f"Invalid {MODE_ENV_VAR}={raw_mode!r}; "
                f"expected one of: {allowed}."
            ) from None

    if on_render and mode is not Mode.PUBLIC_DEMO:
        reason = "is not set" if not raw_mode else f"is {raw_mode!r}"
        raise SettingsError(
            f"Refusing to start: running on Render but {MODE_ENV_VAR} "
            f"{reason}. Set {MODE_ENV_VAR}=public_demo for hosted deployments."
        )

    if mode is not Mode.PUBLIC_DEMO:
        metrics_enabled = (
            environ.get("CAREERPILOT_METRICS_ENABLED", "").strip().lower()
            == "true"
        )
        return Settings(
            mode=mode,
            on_render=on_render,
            metrics_enabled=metrics_enabled,
        )


    # Presence alone is rejected, so an empty value cannot slip through.
    forbidden = [name for name in FORBIDDEN_PUBLIC_DEMO_ENV_VARS if name in environ]
    if forbidden:
        raise SettingsError(
            f"Refusing to start: {MODE_ENV_VAR}=public_demo but "
            f"{', '.join(forbidden)} is set. Remove it from the service "
            f"configuration; the public demo must connect only through "
            f"{DEMO_DATABASE_URL_ENV_VAR} with read-only credentials."
        )

    demo_database_url = environ.get(DEMO_DATABASE_URL_ENV_VAR, "").strip()
    if not demo_database_url:
        raise SettingsError(
            f"Refusing to start: {MODE_ENV_VAR}=public_demo requires a "
            f"non-empty {DEMO_DATABASE_URL_ENV_VAR}."
        )

    return Settings(
        mode=mode,
        on_render=on_render,
        demo_database_url=demo_database_url,
    )
