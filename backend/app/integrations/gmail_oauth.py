import base64
from email.message import EmailMessage
from urllib.parse import quote, urlencode

import httpx


GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_REVOCATION_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_METADATA_SCOPE = "https://www.googleapis.com/auth/gmail.metadata"
GMAIL_OAUTH_SCOPES = ("openid", "email", GMAIL_SEND_SCOPE, GMAIL_METADATA_SCOPE)


class GmailOAuthProviderError(RuntimeError):
    pass


class GmailSendRejectedError(RuntimeError):
    pass


class GmailSendUncertainError(RuntimeError):
    pass


class GmailOAuthClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        timeout_seconds: float = 15,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.timeout_seconds = timeout_seconds

    def authorization_url(self, state: str, login_hint: str | None = None) -> str:
        parameters = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(GMAIL_OAUTH_SCOPES),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent select_account",
            "state": state,
        }
        if login_hint:
            parameters["login_hint"] = login_hint
        return f"{GOOGLE_AUTHORIZATION_URL}?{urlencode(parameters)}"

    def exchange_code(self, code: str) -> dict:
        try:
            response = httpx.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise GmailOAuthProviderError("Google token exchange failed.") from error
        payload = response.json()
        if not isinstance(payload.get("access_token"), str):
            raise GmailOAuthProviderError("Google did not return an access token.")
        return payload

    def user_info(self, access_token: str) -> dict:
        try:
            response = httpx.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise GmailOAuthProviderError("Google account verification failed.") from error
        payload = response.json()
        if not payload.get("sub") or not payload.get("email") or payload.get("email_verified") is not True:
            raise GmailOAuthProviderError("Google did not return a verified account identity.")
        return payload

    def revoke(self, refresh_token: str) -> bool:
        try:
            response = httpx.post(
                GOOGLE_REVOCATION_URL,
                data={"token": refresh_token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout_seconds,
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def refresh_access_token(self, refresh_token: str) -> str:
        try:
            response = httpx.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise GmailOAuthProviderError("Google could not refresh Gmail access.") from error
        try:
            access_token = response.json().get("access_token")
        except ValueError as error:
            raise GmailOAuthProviderError("Google returned an unreadable token response.") from error
        if not isinstance(access_token, str):
            raise GmailOAuthProviderError("Google did not return a Gmail access token.")
        return access_token

    def send_email(
        self,
        access_token: str,
        sender: str,
        recipient: str,
        subject: str,
        body: str,
    ) -> tuple[str, str]:
        message = EmailMessage()
        try:
            message["From"] = sender
            message["To"] = recipient
            message["Subject"] = subject
        except ValueError as error:
            raise GmailSendRejectedError("The saved email headers are invalid.") from error
        message.set_content(body)
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        try:
            response = httpx.post(
                GMAIL_SEND_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                json={"raw": raw_message},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TransportError as error:
            raise GmailSendUncertainError(
                "Gmail delivery could not be confirmed. Do not resend this attempt."
            ) from error
        except httpx.HTTPStatusError as error:
            raise GmailSendRejectedError("Gmail rejected the email.") from error
        try:
            payload = response.json()
        except ValueError as error:
            raise GmailSendUncertainError(
                "Gmail accepted the request but returned an unreadable result. Do not resend this attempt."
            ) from error
        message_id = payload.get("id")
        thread_id = payload.get("threadId")
        if not isinstance(message_id, str) or not isinstance(thread_id, str):
            raise GmailSendUncertainError(
                "Gmail accepted the request but did not confirm its identifiers. Do not resend this attempt."
            )
        return message_id, thread_id

    def thread_metadata(self, access_token: str, thread_id: str) -> dict:
        try:
            response = httpx.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{quote(thread_id, safe='')}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"format": "metadata", "fields": "messages(id,internalDate,labelIds)"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise GmailOAuthProviderError("Gmail thread metadata could not be retrieved.") from error
        if not isinstance(payload.get("messages"), list):
            raise GmailOAuthProviderError("Gmail returned invalid thread metadata.")
        return payload
