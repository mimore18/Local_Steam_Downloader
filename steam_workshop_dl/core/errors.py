"""Domain exceptions.

UI and service layers translate these into user-facing messages.  Keeping them
small and explicit makes it easy to test error paths without touching argparse
or Tkinter.
"""

from __future__ import annotations


class WorkshopError(Exception):
    """Base class for all expected project errors."""


class InvalidTargetError(WorkshopError):
    """The supplied URL/ID cannot be parsed or does not exist."""


class WrongTargetTypeError(WorkshopError):
    """The user selected 'mod' for a collection (or the other way around)."""

    def __init__(self, message: str, *, actual_type: str) -> None:
        super().__init__(message)
        self.actual_type = actual_type


class ApiError(WorkshopError):
    """Steam Web API failed after retries."""


class SteamCmdNotFoundError(WorkshopError):
    """SteamCMD executable could not be located."""


class LoginFailedError(WorkshopError):
    """SteamCMD login did not complete successfully."""


class DownloadError(WorkshopError):
    """A single workshop item could not be downloaded or copied."""


class PendingFeatureError(WorkshopError):
    """Feature intentionally left for a later implementation phase."""
