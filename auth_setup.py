#!/usr/bin/env python3
"""
Helper script to authorize or refresh Google Workspace OAuth credentials (token.json)
for Gmail, Google Forms, and Google Calendar APIs.
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/calendar",
]


def main() -> None:
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w", encoding="utf-8") as token:
            token.write(creds.to_json())
    print("Successfully saved token.json")


if __name__ == "__main__":
    main()
