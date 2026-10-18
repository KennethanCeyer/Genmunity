#!/usr/bin/env python3
"""
OAuth 2.0 Mail Administrator Registration & Real-time Email Receive Trigger Setup.

Usage:
    .venv/bin/python register_mail_admin.py
    .venv/bin/python register_mail_admin.py --email devstar5011@gcplab.me
    .venv/bin/python register_mail_admin.py --status
"""
import argparse
import json
import sys
from genmunity_agent.services.mail_trigger import (
    DEFAULT_ADMIN_EMAIL,
    register_mail_admin_via_oauth,
    sync_live_gmail_profile,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Register Mail Administrator account (devstar5011@gcplab.me) via OAuth 2.0 for Genmunity Email Receive Triggering."
    )
    parser.add_argument(
        "--email",
        default=DEFAULT_ADMIN_EMAIL,
        help=f"Target Mail Administrator Google account (default: {DEFAULT_ADMIN_EMAIL})",
    )
    parser.add_argument(
        "--no-pubsub-watch",
        action="store_true",
        help="Skip registering Gmail users.watch on Cloud Pub/Sub (use local polling trigger only)",
    )
    parser.add_argument(
        "--no-secret-sync",
        action="store_true",
        help="Skip syncing token.json to Google Cloud Secret Manager [gmail-credentials]",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current registered Mail Administrator status without launching browser OAuth",
    )
    args = parser.parse_args()

    if args.status:
        reg = sync_live_gmail_profile()
        print(json.dumps(reg, ensure_ascii=False, indent=2))
        return

    print("=" * 72)
    print("Genmunity — 메일 관리자 계정 OAuth 2.0 로그인 및 이메일 수신 트리거 등록")
    print("=" * 72)
    print(f"• 목표 관리자 계정 (login_hint): {args.email}")
    print("• 브라우저 창이 열리면 위 메일 관리자 계정으로 로그인하고 권한을 허용해 주세요.")
    print("-" * 72)

    try:
        reg = register_mail_admin_via_oauth(
            target_email=args.email,
            register_pubsub_watch=not args.no_pubsub_watch,
            sync_secret_manager=not args.no_secret_sync,
            open_browser=True,
        )
    except Exception as exc:
        print(f"\n[ERROR] OAuth 인증 또는 관리자 등록 실패: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\n메일 관리자 계정 등록 및 수신 트리거 설정 완료!")
    print(f"  - 인증된 이메일 계정 : {reg.get('authenticated_email')}")
    print(f"  - 목표 관리자 일치   : {reg.get('is_target_admin_active')}")
    print(f"  - 초기 History ID    : {reg.get('initial_history_id')}")
    print(f"  - Pub/Sub Watch 상태 : {json.dumps(reg.get('pubsub_watch'), ensure_ascii=False)}")
    print(f"  - Secret Manager 동기화: {reg.get('secret_manager_synced')}")
    print(f"  - 등록 정보 저장 위치: data/mail_admin_registry.json & token.json")
    print("=" * 72)


if __name__ == "__main__":
    main()
