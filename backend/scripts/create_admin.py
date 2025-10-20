"""
backend/scripts/create_admin.py
Script to create an initial admin user for Adaptive IDS
"""

import getpass
import os
import sys
from pathlib import Path

# Add parent directory to path to import from api module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'api'))

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import auth utilities
try:
    from flask import Flask
    from auth import init_bcrypt, hash_password, validate_email, validate_password, validate_username
    
    # Create minimal Flask app for bcrypt
    app = Flask(__name__)
    init_bcrypt(app)
except ImportError as e:
    print(f"Error: Required packages not installed: {e}")
    print("Please run: pip install -r backend/requirements.txt")
    sys.exit(1)


def get_db_connection():
    """Get database connection"""
    config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', '55432')),
        'dbname': os.getenv('POSTGRES_DB', 'adaptive_ids'),
        'user': os.getenv('POSTGRES_USER', 'adaptive_ids'),
        'password': os.getenv('POSTGRES_PASSWORD', 'adaptive_ids_password'),
    }
    return psycopg2.connect(**config)


def create_admin_user(username: str, email: str, password: str) -> bool:
    """
    Create an admin user in the database
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Validate inputs
        is_valid, error = validate_username(username)
        if not is_valid:
            print(f"Error: {error}")
            return False
        
        if not validate_email(email):
            print("Error: Invalid email format")
            return False
        
        is_valid, error = validate_password(password)
        if not is_valid:
            print(f"Error: {error}")
            return False
        
        # Hash password
        password_hash = hash_password(password)
        
        # Connect to database
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if user already exists
                cur.execute(
                    "SELECT id FROM users WHERE username = %s OR email = %s",
                    (username, email)
                )
                if cur.fetchone():
                    print(f"Error: User with username '{username}' or email '{email}' already exists")
                    return False
                
                # Insert admin user
                cur.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, username, email, role, created_at
                    """,
                    (username, email, password_hash, 'admin')
                )
                row = cur.fetchone()
                conn.commit()
                
                print(f"\n✓ Admin user created successfully!")
                print(f"  ID: {row['id']}")
                print(f"  Username: {row['username']}")
                print(f"  Email: {row['email']}")
                print(f"  Role: {row['role']}")
                print(f"  Created: {row['created_at']}")
                return True
        finally:
            conn.close()
    
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    """Main function"""
    print("=" * 60)
    print("Adaptive IDS - Admin User Creation")
    print("=" * 60)
    print()
    
    # Try to get credentials from environment variables first
    username = os.getenv('ADMIN_USERNAME')
    email = os.getenv('ADMIN_EMAIL')
    password = os.getenv('ADMIN_PASSWORD')
    
    use_env = False
    if username and email and password:
        print(f"Found admin credentials in environment variables:")
        print(f"  Username: {username}")
        print(f"  Email: {email}")
        print()
        response = input("Use these credentials? (y/n): ").strip().lower()
        use_env = response in ('y', 'yes')
    
    if not use_env:
        # Prompt for credentials
        print("Enter admin user credentials:")
        print()
        
        username = input("Username: ").strip()
        if not username:
            print("Error: Username is required")
            sys.exit(1)
        
        email = input("Email: ").strip()
        if not email:
            print("Error: Email is required")
            sys.exit(1)
        
        password = getpass.getpass("Password: ").strip()
        if not password:
            print("Error: Password is required")
            sys.exit(1)
        
        password_confirm = getpass.getpass("Confirm password: ").strip()
        if password != password_confirm:
            print("Error: Passwords do not match")
            sys.exit(1)
    
    print()
    print("Creating admin user...")
    
    # Create admin user
    success = create_admin_user(username, email, password)
    
    if success:
        print()
        print("You can now login with these credentials at:")
        print("  POST http://localhost:5000/api/auth/login")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
