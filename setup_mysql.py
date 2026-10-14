"""
MySQL Configuration and Migration Utility
Run this script to connect the application to your local MySQL 8.0 server:
python setup_mysql.py
"""
import os
import sys
import getpass
import pymysql
from pathlib import Path
from dotenv import load_dotenv, set_key

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / '.env'
load_dotenv(ENV_PATH)

def prompt_and_configure():
    print("=" * 65)
    print("UPI FRAUD GUARD AI - MySQL Server Configuration")
    print("=" * 65)
    
    current_host = os.getenv('DB_HOST', 'localhost')
    current_port = os.getenv('DB_PORT', '3306')
    current_user = os.getenv('DB_USER', 'root')
    current_name = os.getenv('DB_NAME', 'upi_fraud_db')
    
    print(f"Current Host: {current_host}")
    print(f"Current Port: {current_port}")
    print(f"Current User: {current_user}")
    print(f"Database Name: {current_name}")
    print("-" * 65)
    
    # Prompt for password if not set
    password = os.getenv('DB_PASSWORD', '')
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        user_input = input(f"Enter MySQL password for '{current_user}' (press Enter if blank): ")
        password = user_input.strip()

    print(f"\n[1/3] Testing connection to MySQL at {current_host}:{current_port}...")
    try:
        conn = pymysql.connect(
            host=current_host,
            port=int(current_port),
            user=current_user,
            password=password,
            connect_timeout=5
        )
        print("  -> Connected to MySQL server successfully!")
    except Exception as e:
        print(f"  -> ERROR: Failed to connect to MySQL: {e}")
        print("  -> Please verify your MySQL server is running and the password is correct.")
        return False

    print(f"[2/3] Creating database '{current_name}' if not exists...")
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{current_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        conn.commit()
        conn.close()
        print(f"  -> Database '{current_name}' is ready.")
    except Exception as e:
        print(f"  -> ERROR creating database: {e}")
        conn.close()
        return False

    # Connect to the database and run schema.sql
    print(f"[3/3] Initializing MySQL tables and sample dataset...")
    try:
        db_conn = pymysql.connect(
            host=current_host,
            port=int(current_port),
            user=current_user,
            password=password,
            database=current_name,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        # Read schema.sql
        with open(BASE_DIR / 'schema.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()

        statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        with db_conn.cursor() as cur:
            for stmt in statements:
                if stmt.lower().startswith('create database') or stmt.lower().startswith('use '):
                    continue
                cur.execute(stmt)
        db_conn.commit()
        db_conn.close()
        print("  -> Schema executed successfully in MySQL!")

        # Update .env
        set_key(str(ENV_PATH), 'DB_TYPE', 'mysql')
        set_key(str(ENV_PATH), 'DB_PASSWORD', password)
        print(f"  -> Updated .env configuration: DB_TYPE=mysql, DB_PASSWORD configured.")

        # Re-run init_db to seed initial data in MySQL
        print("\nSeeding synthetic fraud dataset into MySQL...")
        from database import DatabaseManager
        db_mysql = DatabaseManager()
        db_mysql.seed_initial_data()

        print("\n" + "=" * 65)
        print("SUCCESS! Your application is now fully connected to MySQL 8.0.")
        print("Start the application by running: python app.py")
        print("=" * 65)
        return True

    except Exception as e:
        print(f"  -> ERROR during schema execution: {e}")
        return False

if __name__ == '__main__':
    prompt_and_configure()
