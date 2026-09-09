import base64
from email import policy
from email.parser import BytesParser

import httpx
import pytest

from app.integrations import gmail_oauth
from app.integrations.gmail_oauth import GmailOAuthClient, GmailSendUncertainError


def test_gmail_sender_builds_a_mime_message_and_returns_provider_ids(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return httpx.Response(
            200,
            json={"id": "message-1", "threadId": "thread-1"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(gmail_oauth.httpx, "post", fake_post)
    client = GmailOAuthClient("client", "secret", "https://example.com/callback")

    result = client.send_email(
        "access-token",
        "sender@gmail.com",
        "prospect@example.com",
        "Evidence-backed idea",
        "A grounded message.",
    )

    decoded = base64.urlsafe_b64decode(captured["json"]["raw"])
    message = BytesParser(policy=policy.default).parsebytes(decoded)
    assert result == ("message-1", "thread-1")
    assert message["From"] == "sender@gmail.com"
    assert message["To"] == "prospect@example.com"
    assert message["Subject"] == "Evidence-backed idea"
    assert message.get_content().strip() == "A grounded message."


def test_transport_failure_is_treated_as_uncertain_delivery(monkeypatch):
    def fail_post(url, **kwargs):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(gmail_oauth.httpx, "post", fail_post)
    client = GmailOAuthClient("client", "secret", "https://example.com/callback")

    with pytest.raises(GmailSendUncertainError, match="Do not resend"):
        client.send_email(
            "access-token",
            "sender@gmail.com",
            "prospect@example.com",
            "Evidence-backed idea",
            "A grounded message.",
        )


def test_thread_metadata_reads_only_the_known_thread(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return httpx.Response(
            200,
            json={"id": "thread-1", "messages": []},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(gmail_oauth.httpx, "get", fake_get)
    client = GmailOAuthClient("client", "secret", "https://example.com/callback")

    result = client.thread_metadata("access-token", "thread-1")

    assert result["id"] == "thread-1"
    assert captured["url"].endswith("/threads/thread-1")
    assert captured["params"] == {
        "format": "metadata",
        "fields": "messages(id,internalDate,labelIds)",
    }
