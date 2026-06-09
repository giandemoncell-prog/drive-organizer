from __future__ import annotations

from pathlib import Path

import click
import requests as _requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    try:
        import ssl as _ssl

        import certifi as _certifi
        _ssl_ctx = _ssl.create_default_context(cafile=_certifi.where())
    except ImportError:
        pass


def _authed_request() -> Request:
    session = _requests.Session()
    return Request(session=session)

from drive_organizer.config import settings


def _token_path(email: str) -> Path:
    tokens_dir = Path(settings.tokens_dir)
    tokens_dir.mkdir(exist_ok=True)
    return tokens_dir / f"{email}.json"


def list_accounts() -> list[str]:
    tokens_dir = Path(settings.tokens_dir)
    if not tokens_dir.exists():
        return []
    return sorted(f.stem for f in tokens_dir.glob("*.json"))


def _resolve_account(account: str | None) -> str | None:
    """Return email to use for token lookup, or None if fresh auth needed."""
    accounts = list_accounts()

    if account:
        match = next((a for a in accounts if a == account), None)
        return match or account  # if not found, will trigger fresh auth

    if len(accounts) == 1:
        return accounts[0]

    if len(accounts) > 1:
        click.echo("\nAccount disponibili:")
        for i, a in enumerate(accounts, 1):
            click.echo(f"  {i}. {a}")
        idx = click.prompt(
            "Scegli account",
            type=click.IntRange(1, len(accounts)),
            default=1,
        )
        return accounts[idx - 1]

    return None  # no accounts yet → fresh auth


def get_drive_service(account: str | None = None):
    creds: Credentials | None = None
    token_file: Path | None = None

    selected = _resolve_account(account)
    if selected:
        token_file = _token_path(selected)
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), settings.drive_scopes)

    if creds and creds.valid:
        return build("drive", "v3", credentials=creds)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(_authed_request())
            if token_file:
                token_file.write_text(creds.to_json(), encoding="utf-8")
            return build("drive", "v3", credentials=creds)
        except Exception:
            creds = None  # fall through to fresh OAuth flow

    # Fresh OAuth flow
    flow = InstalledAppFlow.from_client_secrets_file(
        settings.credentials_path,
        settings.drive_scopes,
    )
    creds = flow.run_local_server(port=0)
    svc = build("drive", "v3", credentials=creds)
    email = get_authenticated_email(svc)
    _token_path(email).write_text(creds.to_json(), encoding="utf-8")
    return svc


def get_authenticated_email(service) -> str:
    try:
        info = service.about().get(fields="user").execute()
        return info.get("user", {}).get("emailAddress", "unknown")
    except Exception:
        return "unknown"
