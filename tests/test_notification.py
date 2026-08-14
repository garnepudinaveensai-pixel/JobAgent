import pytest

from app.notifications.notification import (
    Notification,
    NotificationResult,
)


# ============================================================
# TEST IMPLEMENTATION
# ============================================================


class MockNotification(Notification):
    """Simple notification implementation for testing."""

    name = "Test Notification"

    def __init__(self, enabled=True):
        super().__init__(enabled=enabled)
        self.sent_messages = []

    def send(
        self,
        title: str,
        message: str,
        **kwargs,
    ) -> bool:

        self.validate(title, message)

        if not self.enabled:
            return False

        self.sent_messages.append(
            {
                "title": title,
                "message": message,
                "kwargs": kwargs,
            }
        )

        return True


# ============================================================
# INITIALIZATION
# ============================================================


def test_notification_initialization():

    notification = MockNotification()

    assert notification.enabled is True
    assert notification.is_enabled() is True


def test_notification_disabled():

    notification = MockNotification(
        enabled=False
    )

    assert notification.is_enabled() is False


# ============================================================
# CHANNEL NAME
# ============================================================


def test_channel_name():

    notification = MockNotification()

    assert (
        notification.channel_name
        == "Test Notification"
    )


# ============================================================
# ENABLE / DISABLE
# ============================================================


def test_disable_notification():

    notification = MockNotification()

    notification.disable()

    assert notification.enabled is False
    assert notification.is_enabled() is False


def test_enable_notification():

    notification = MockNotification(
        enabled=False
    )

    notification.enable()

    assert notification.enabled is True
    assert notification.is_enabled() is True


# ============================================================
# VALIDATION
# ============================================================


def test_empty_title_fails():

    notification = MockNotification()

    with pytest.raises(ValueError):

        notification.send(
            "",
            "Application shortlisted.",
        )


def test_empty_message_fails():

    notification = MockNotification()

    with pytest.raises(ValueError):

        notification.send(
            "Job Update",
            "",
        )


def test_invalid_title_type_fails():

    notification = MockNotification()

    with pytest.raises(TypeError):

        notification.send(
            123,
            "Application shortlisted.",
        )


def test_invalid_message_type_fails():

    notification = MockNotification()

    with pytest.raises(TypeError):

        notification.send(
            "Job Update",
            123,
        )


# ============================================================
# SEND
# ============================================================


def test_send_notification():

    notification = MockNotification()

    result = notification.send(
        "Application Update",
        "You have been shortlisted.",
    )

    assert result is True

    assert len(
        notification.sent_messages
    ) == 1

    assert (
        notification.sent_messages[0]["title"]
        == "Application Update"
    )

    assert (
        notification.sent_messages[0]["message"]
        == "You have been shortlisted."
    )


def test_disabled_notification_does_not_send():

    notification = MockNotification(
        enabled=False
    )

    result = notification.send(
        "Application Update",
        "You have been shortlisted.",
    )

    assert result is False

    assert (
        len(notification.sent_messages)
        == 0
    )


# ============================================================
# NOTIFICATION RESULT
# ============================================================


def test_notification_result():

    result = NotificationResult(
        success=True,
        channel="Email",
        title="Application Update",
        message="You have been shortlisted.",
    )

    data = result.to_dict()

    assert data["success"] is True
    assert data["channel"] == "Email"
    assert (
        data["title"]
        == "Application Update"
    )
    assert (
        data["message"]
        == "You have been shortlisted."
    )
    assert data["error"] is None


def test_notification_result_with_error():

    result = NotificationResult(
        success=False,
        channel="Email",
        title="Application Update",
        message="Application status changed.",
        error="SMTP connection failed.",
    )

    data = result.to_dict()

    assert data["success"] is False
    assert data["channel"] == "Email"
    assert (
        data["error"]
        == "SMTP connection failed."
    )