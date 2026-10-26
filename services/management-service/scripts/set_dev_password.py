"""
Development Password Provisioning Script

Safely provisions or updates a password for an EXISTING user in management_db
using Argon2 password hashing.

RULES:
- Operates ONLY on existing users.
- Never creates fake users.
- No default passwords.
- No plaintext password output or logging.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

# Add services/management-service to sys.path so app modules can be loaded
SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.core.security import hash_password
from app.repositories.user_repository import user_repository


def set_password(email: str, password: str | None = None) -> bool:
    clean_email = email.strip().lower()
    user = user_repository.get_user_by_email(clean_email)

    if not user:
        print(f"[ERROR] User with email '{clean_email}' not found in management_db.")
        print("[INFO] This script operates ONLY on existing users and will not invent new identities.")
        return False

    if not password:
        password = os.getenv("DEV_PASSWORD")

    if not password:
        try:
            password = getpass.getpass(f"Enter new password for '{clean_email}': ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("[ERROR] Passwords do not match.")
                return False
        except (KeyboardInterrupt, EOFError):
            print("\n[CANCELLED] Operation aborted by user.")
            return False

    if not password or len(password.strip()) == 0:
        print("[ERROR] Password cannot be empty.")
        return False

    # Securely hash with Argon2
    hashed = hash_password(password)

    # Persist in management_db
    success = user_repository.update_password_hash(user["id"], hashed)
    if success:
        print(f"[SUCCESS] Password securely provisioned for user '{clean_email}' (ID: {user['id']}).")
        print("[INFO] Authentication is now available for this user.")
        return True
    else:
        print("[ERROR] Failed to update password in database.")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Provision an Argon2 password for an existing user in management_db.",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email address of the existing user in management_db",
    )
    parser.add_argument(
        "--password",
        required=False,
        default=None,
        help="Password (optional, will prompt securely via getpass if omitted)",
    )

    args = parser.parse_args()
    success = set_password(args.email, args.password)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
