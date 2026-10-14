"""
Database initialization and data seeding script.
Run directly with: python init_db.py
"""
import sys
from config import Config
from database import db

def main():
    print("=" * 60)
    print("UPI Fraud Reporting & Pattern Detection - Database Setup")
    print(f"Target Engine: {db.engine_name}")
    print("=" * 60)
    
    try:
        print("[1/2] Creating tables and schema...")
        db.init_tables()
        print("[2/2] Seeding initial synthetic fraud dataset and admin account...")
        db.seed_initial_data()
        print("\nSUCCESS: Database initialized and seeded successfully!")
        print(f"Active Engine: {db.engine_name}")
        print("Default Admin Credentials: admin / Admin@123")
        print("=" * 60)
    except Exception as e:
        print(f"\nERROR initializing database: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
