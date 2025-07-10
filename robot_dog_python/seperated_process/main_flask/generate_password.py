#!/usr/bin/env python3
"""
Password hash generator for Flask app authentication.
Use this script to generate secure password hashes for new users.
"""

import hashlib
import secrets
import sys

def hash_password(password):
    """Hash a password with salt for secure storage."""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{password_hash}"

def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_password.py <password>")
        print("Example: python generate_password.py MySecurePassword123!")
        sys.exit(1)
    
    password = sys.argv[1]
    
    if len(password) < 8:
        print("Warning: Password should be at least 8 characters long for security.")
    
    hashed = hash_password(password)
    print(f"Password hash for '{password}':")
    print(f'"{hashed}"')
    print("\nCopy this hash and update the USERS dictionary in app.py")

if __name__ == "__main__":
    main()
