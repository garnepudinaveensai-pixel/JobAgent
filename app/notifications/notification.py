from abc import ABC, abstractmethod
from typing import Any, Optional


class Notification(ABC):
    """
    Base interface for all JobAgent notification channels.

    A notification channel receives a message and delivers it
    through a specific mechanism such as email or desktop notification.
    """

    name: str = ""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    @property
    def channel_name(self) -> str:
        """Return the human-readable notification channel name."""

        if self.name:
            return self.name

        return self.__class__.__name__

    @abstractmethod
    def send(
        self,
        title: str,
        message: str,
        **kwargs: Any,
    ) -> bool:
        """
        Send a notification.

        Returns:
            True  -> notification was successfully sent
            False -> notification could not be sent
        """
        raise NotImplementedError

    def validate(
        self,
        title: str,
        message: str,
    ) -> None:
        """
        Validate common notification input.
        """

        if not isinstance(title, str):
            raise TypeError("title must be a string.")

        if not isinstance(message, str):
            raise TypeError("message must be a string.")

        if not title.strip():
            raise ValueError("title cannot be empty.")

        if not message.strip():
            raise ValueError("message cannot be empty.")

    def is_enabled(self) -> bool:
        """Return whether this notification channel is enabled."""

        return self.enabled

    def enable(self) -> None:
        """Enable this notification channel."""

        self.enabled = True

    def disable(self) -> None:
        """Disable this notification channel."""

        self.enabled = False


class NotificationResult:
    """
    Structured result for notification delivery.

    This allows the rest of JobAgent to know whether a notification
    succeeded without depending on a particular notification provider.
    """

    def __init__(
        self,
        success: bool,
        channel: str,
        title: str,
        message: str,
        error: Optional[str] = None,
    ):
        self.success = success
        self.channel = channel
        self.title = title
        self.message = message
        self.error = error

    def to_dict(self) -> dict:
        """Convert the result to a dictionary."""

        return {
            "success": self.success,
            "channel": self.channel,
            "title": self.title,
            "message": self.message,
            "error": self.error,
        }