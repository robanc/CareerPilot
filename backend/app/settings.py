"""Backend operating-mode configuration.

CareerPilot runs in exactly one of two modes, selected by CAREERPILOT_MODE:

- ``local`` (default): the developer's own instance with full read/write
  access. This is what Docker Compose and the test suite use.
- ``public_demo``: a publicly reachable demonstration instance.

WARNING: public_demo is NOT SAFE TO DEPLOY yet. It blocks HTTP writes (see
readonly.py), but there are no database restrictions, rate limiting, resume
input limits, or synthetic-data safeguards. Do not expose a public_demo
instance until those are implemented and tested.

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
from dataclasses import dataclass
from enum import Enum


MODE_ENV_VAR = "CAREERPILOT_MODE"
RENDER_ENV_VAR = "RENDER"


class Mode(str, Enum):
    LOCAL = "local"
    PUBLIC_DEMO = "public_demo"


class SettingsError(RuntimeError):
    """Raised when the configuration is invalid or unsafe to start with."""


@dataclass(frozen=True)
class Settings:
    mode: Mode
    on_render: bool

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

    return Settings(mode=mode, on_render=on_render)
