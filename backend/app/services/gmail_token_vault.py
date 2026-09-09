from cryptography.fernet import Fernet, InvalidToken


class GmailTokenVaultError(RuntimeError):
    pass


def valid_encryption_key(encryption_key: str) -> bool:
    try:
        Fernet(encryption_key.encode())
        return True
    except (ValueError, TypeError):
        return False


def encrypt_refresh_token(token: str, encryption_key: str) -> str:
    try:
        return Fernet(encryption_key.encode()).encrypt(token.encode()).decode()
    except (ValueError, TypeError) as error:
        raise GmailTokenVaultError("Gmail token encryption is not configured correctly.") from error


def decrypt_refresh_token(encrypted_token: str, encryption_key: str) -> str:
    try:
        return Fernet(encryption_key.encode()).decrypt(encrypted_token.encode()).decode()
    except (InvalidToken, ValueError, TypeError) as error:
        raise GmailTokenVaultError("The stored Gmail credential could not be decrypted.") from error
