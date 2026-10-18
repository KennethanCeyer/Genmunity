# Genmunity Agent Guide

## Environment Configuration (`.env`)

All credentials, OAuth client settings, and assigned Google Cloud / Workspace account metadata are stored in:

- **Path**: `/Users/pignose/Genmunity/.env` (relative to project root: `./.env`)

### Environment Variables in `.env`

| Variable | Description | Value / Reference |
| --- | --- | --- |
| `GCP_USERNAME` | Assigned Google Cloud / Workspace Username | `devstar5011@gcplab.me` |
| `GCP_PASSWORD` | Assigned Account Password | Stored in `/Users/pignose/Genmunity/.env` (`GCP_PASSWORD`) |
| `GCP_FIRSTNAME` | Account First Name | `Star` |
| `GCP_LASTNAME` | Account Last Name | `Developer 5011` |
| `GCP_PROJECT_ID` | Assigned Google Cloud Project ID | `kr-devsummit26icn-501` |
| `MAIL_ADMIN_EMAIL` | Mail Administrator Account for OAuth & Inbound Trigger | `devstar5011@gcplab.me` |
| `GENMUNITY_MODEL` | Primary Gemini Model | `gemini-4-argon` |
| `GENMUNITY_SECONDARY_MODEL` | Secondary Fallback Gemini Model | `gemini-3.8-flash` |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Gemini API Key | Stored in `/Users/pignose/Genmunity/.env` |
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth 2.0 Client ID | Stored in `/Users/pignose/Genmunity/.env` |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth 2.0 Client Secret | Stored in `/Users/pignose/Genmunity/.env` |

## Model Policy

- Always use **`gemini-4-argon`** (Gemini 4.0 Argon) as the primary model.
- Use **`gemini-3.8-flash`** (Gemini 3.8 Flash) as the secondary fallback model.
- Do not use legacy `gemini-2.5-*` models.

## Style & Formatting Guidelines

- Do not use emojis in documentation, code, CLI output, or Web UI templates.
