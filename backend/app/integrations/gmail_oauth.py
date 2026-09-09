from urllib.parse import urlencode

import httpx


GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_REVOCATION_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_OAUTH_SCOPES = ("openid", "email", GMAIL_SEND_SCOPE)


class GmailOAuthProviderError(RuntimeError):
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
