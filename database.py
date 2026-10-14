import os
import sqlite3
import pymysql
import pymysql.cursors
from werkzeug.security import generate_password_hash
from config import Config

class DatabaseManager:
    def __init__(self):
        self.engine_type = 'sqlite'
        self.engine_name = 'SQLite (Fallback)'
        self.connection_error = None
        self._test_and_select_engine()

    def _test_and_select_engine(self):
        """Attempts connection to MySQL. If fails, gracefully falls back to SQLite."""
        if Config.DB_TYPE == 'mysql':
            try:
                # First connect to server without database to create it if needed
                temp_conn = pymysql.connect(
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD,
                    connect_timeout=3
                )
                with temp_conn.cursor() as cur:
                    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
                temp_conn.commit()
                temp_conn.close()

                # Test connection to specific database
                conn = pymysql.connect(
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD,
                    database=Config.DB_NAME,
                    cursorclass=pymysql.cursors.DictCursor,
                    connect_timeout=3
                )
                conn.close()
                self.engine_type = 'mysql'
                self.engine_name = f"MySQL 8.0 ({Config.DB_NAME}@{Config.DB_HOST})"
                print(f"[DB] Successfully connected to {self.engine_name}")
                return
            except Exception as e:
                self.connection_error = str(e)
                print(f"[DB Notice] Could not connect to MySQL ({e}). Using embedded SQLite database.")
        
        # SQLite mode
        self.engine_type = 'sqlite'
        self.engine_name = f"SQLite ({os.path.basename(Config.SQLITE_DB_PATH)})"
        print(f"[DB] Active database engine: {self.engine_name}")

    def get_connection(self):
        if self.engine_type == 'mysql':
            return pymysql.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False
            )
        else:
            conn = sqlite3.connect(Config.SQLITE_DB_PATH)
            conn.row_factory = sqlite3.Row
            return conn

    def _prepare_sql(self, sql):
        if self.engine_type == 'sqlite':
            # Convert MySQL %s placeholder to SQLite ? placeholder
            return sql.replace('%s', '?')
        return sql

    def execute(self, query, params=None):
        """Execute INSERT/UPDATE/DELETE and commit. Returns lastrowid or affected rows."""
        prepared_query = self._prepare_sql(query)
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(prepared_query, params)
            else:
                cursor.execute(prepared_query)
            conn.commit()
            last_id = cursor.lastrowid
            row_count = cursor.rowcount
            cursor.close()
            conn.close()
            return last_id or row_count
        except Exception as e:
            conn.rollback()
            conn.close()
            raise e

    def fetch_one(self, query, params=None):
        """Fetch a single dictionary row."""
        prepared_query = self._prepare_sql(query)
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(prepared_query, params)
            else:
                cursor.execute(prepared_query)
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row is None:
                return None
            if self.engine_type == 'sqlite':
                return dict(row)
            return row
        except Exception as e:
            conn.close()
            raise e

    def fetch_all(self, query, params=None):
        """Fetch multiple dictionary rows."""
        prepared_query = self._prepare_sql(query)
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(prepared_query, params)
            else:
                cursor.execute(prepared_query)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            if self.engine_type == 'sqlite':
                return [dict(r) for r in rows]
            return list(rows)
        except Exception as e:
            conn.close()
            raise e

    def init_tables(self):
        """Initialize database schema tables."""
        if self.engine_type == 'mysql':
            schema_file = os.path.join(os.path.dirname(__file__), 'schema.sql')
            with open(schema_file, 'r', encoding='utf-8') as f:
                content = f.read()
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    statements = [s.strip() for s in content.split(';') if s.strip()]
                    for stmt in statements:
                        if stmt.lower().startswith('create database') or stmt.lower().startswith('use '):
                            continue
                        cur.execute(stmt)
                conn.commit()
                conn.close()
                print("[DB] MySQL schema initialized successfully.")
            except Exception as e:
                conn.close()
                raise e
        else:
            schema_file = os.path.join(os.path.dirname(__file__), 'schema_sqlite.sql')
            with open(schema_file, 'r', encoding='utf-8') as f:
                content = f.read()
            conn = sqlite3.connect(Config.SQLITE_DB_PATH)
            try:
                conn.executescript(content)
                conn.commit()
                conn.close()
                print("[DB] SQLite schema initialized successfully.")
            except Exception as e:
                conn.close()
                raise e

    def seed_initial_data(self):
        """Seeds default admin, initial settings, and realistic synthetic fraud reports if empty."""
        user_count = self.fetch_one("SELECT COUNT(*) as cnt FROM users")
        if user_count and user_count['cnt'] > 0:
            print("[DB] Database already initialized with data.")
            return

        print("[DB] Seeding initial admin account, settings, and synthetic fraud patterns...")
        
        # 1. Admin account (admin / Admin@123)
        admin_pass = generate_password_hash("Admin@123")
        self.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (%s, %s, %s, %s)",
            ("admin", "admin@upifraudguard.ai", admin_pass, "admin")
        )

        # 2. System settings
        self.execute(
            "INSERT INTO system_settings (key_name, key_value) VALUES (%s, %s)",
            ("risk_threshold_low", str(Config.RISK_THRESHOLD_LOW))
        )
        self.execute(
            "INSERT INTO system_settings (key_name, key_value) VALUES (%s, %s)",
            ("risk_threshold_high", str(Config.RISK_THRESHOLD_HIGH))
        )
        self.execute(
            "INSERT INTO system_settings (key_name, key_value) VALUES (%s, %s)",
            ("auto_block_high_risk", "1" if Config.AUTO_BLOCK_HIGH_RISK else "0")
        )

        # 3. Realistic Synthetic Receivers & Fraud Reports
        sample_receivers = [
            {
                "upi_id": "sbi.kyc.verification@okhdfcbank",
                "name": "SBI Helpdesk KYC Official",
                "phone": "+91 98231 44521",
                "total_reports": 6,
                "verified_reports": 5,
                "rejected_reports": 0,
                "risk_score": 96,
                "risk_level": "HIGH RISK",
                "is_verified_fraud": 1,
                "flagged_urls": "http://sbikyc-update-quicksupport.apk, http://bit.ly/sbi-kyc-verify"
            },
            {
                "upi_id": "electricity.bill.desk@paytm",
                "name": "Mahavitaran Bill Recovery Officer",
                "phone": "+91 87654 32190",
                "total_reports": 4,
                "verified_reports": 4,
                "rejected_reports": 0,
                "risk_score": 92,
                "risk_level": "HIGH RISK",
                "is_verified_fraud": 1,
                "flagged_urls": "http://power-cut-notice-bill.online"
            },
            {
                "upi_id": "telegram.investment.vip@axisbank",
                "name": "VIP Wealth Quantum Global",
                "phone": "+91 70123 99881",
                "total_reports": 5,
                "verified_reports": 3,
                "rejected_reports": 0,
                "risk_score": 88,
                "risk_level": "HIGH RISK",
                "is_verified_fraud": 1,
                "flagged_urls": "https://t.me/vip_task_earnings_daily"
            },
            {
                "upi_id": "qr.refund.officer@ybl",
                "name": "Paytm Customer Support Agent",
                "phone": "+91 91234 56780",
                "total_reports": 3,
                "verified_reports": 2,
                "rejected_reports": 0,
                "risk_score": 85,
                "risk_level": "HIGH RISK",
                "is_verified_fraud": 1,
                "flagged_urls": "http://reverse-pay-qr-generator.net"
            },
            {
                "upi_id": "crypto.gainz@okicici",
                "name": "Binance P2P Rapid Arbitrage",
                "phone": "+91 95432 10987",
                "total_reports": 2,
                "verified_reports": 0,
                "rejected_reports": 0,
                "risk_score": 52,
                "risk_level": "MEDIUM RISK",
                "is_verified_fraud": 0,
                "flagged_urls": "https://fast-crypto-p2p.site"
            },
            {
                "upi_id": "job.processing.fee@postbank",
                "name": "Global HR Career Recruitment",
                "phone": "+91 88990 11223",
                "total_reports": 1,
                "verified_reports": 0,
                "rejected_reports": 0,
                "risk_score": 45,
                "risk_level": "MEDIUM RISK",
                "is_verified_fraud": 0,
                "flagged_urls": ""
            },
            {
                "upi_id": "rahul.sharma@okaxis",
                "name": "Rahul Sharma",
                "phone": "+91 98765 43210",
                "total_reports": 0,
                "verified_reports": 0,
                "rejected_reports": 0,
                "risk_score": 5,
                "risk_level": "LOW RISK",
                "is_verified_fraud": 0,
                "flagged_urls": ""
            },
            {
                "upi_id": "corner.grocery.store@icici",
                "name": "Shree Ganesh Supermarket",
                "phone": "+91 97654 12309",
                "total_reports": 0,
                "verified_reports": 0,
                "rejected_reports": 0,
                "risk_score": 8,
                "risk_level": "LOW RISK",
                "is_verified_fraud": 0,
                "flagged_urls": ""
            }
        ]

        for rec in sample_receivers:
            self.execute(
                """INSERT INTO receivers 
                (upi_id, name, phone, total_reports, verified_reports, rejected_reports, risk_score, risk_level, is_verified_fraud, flagged_urls)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (rec["upi_id"], rec["name"], rec["phone"], rec["total_reports"], rec["verified_reports"],
                 rec["rejected_reports"], rec["risk_score"], rec["risk_level"], rec["is_verified_fraud"], rec["flagged_urls"])
            )

        sample_reports = [
            {
                "report_ref": "REP-2026-KYC-001",
                "receiver_upi_id": "sbi.kyc.verification@okhdfcbank",
                "receiver_name": "SBI Helpdesk KYC Official",
                "receiver_phone": "+91 98231 44521",
                "category": "Fake KYC Messages",
                "description": "Received SMS claiming my SBI bank account will be suspended within 24 hours due to expired PAN card. Asked to download QuickSupport APK and transfer Rs 10 for KYC verification.",
                "suspicious_url": "http://sbikyc-update-quicksupport.apk",
                "amount_lost": 24999.00,
                "status": "verified",
                "ai_category_detected": "Fake KYC Messages",
                "ai_confidence": 96.5,
                "ai_urgency_score": 90
            },
            {
                "report_ref": "REP-2026-ELEC-002",
                "receiver_upi_id": "electricity.bill.desk@paytm",
                "receiver_name": "Mahavitaran Bill Recovery Officer",
                "receiver_phone": "+91 87654 32190",
                "category": "Fake Customer Care Representatives",
                "description": "SMS stated electricity power will be disconnected at 9:30 PM tonight due to unpaid bill. Caller posed as electricity officer and demanded immediate UPI payment of Rs 1,450.",
                "suspicious_url": "http://power-cut-notice-bill.online",
                "amount_lost": 1450.00,
                "status": "verified",
                "ai_category_detected": "Fake Customer Care Representatives",
                "ai_confidence": 94.0,
                "ai_urgency_score": 85
            },
            {
                "report_ref": "REP-2026-INV-003",
                "receiver_upi_id": "telegram.investment.vip@axisbank",
                "receiver_name": "VIP Wealth Quantum Global",
                "receiver_phone": "+91 70123 99881",
                "category": "Impersonation and Investment Scams",
                "description": "Added to a Telegram investment group offering guaranteed 400% daily returns. First deposit of Rs 2000 gave Rs 2600 fake payout. Then they demanded Rs 50,000 for VIP arbitrage task.",
                "suspicious_url": "https://t.me/vip_task_earnings_daily",
                "amount_lost": 52000.00,
                "status": "verified",
                "ai_category_detected": "Impersonation and Investment Scams",
                "ai_confidence": 98.2,
                "ai_urgency_score": 75
            },
            {
                "report_ref": "REP-2026-QR-004",
                "receiver_upi_id": "qr.refund.officer@ybl",
                "receiver_name": "Paytm Customer Support Agent",
                "receiver_phone": "+91 91234 56780",
                "category": "QR-Code Scams",
                "description": "I posted an OLX sofa ad. Buyer claimed he is paying via UPI and sent a QR code stating 'Scan to receive Rs 15,000'. When scanned and PIN entered, Rs 15,000 was debited from my account instead.",
                "suspicious_url": "http://reverse-pay-qr-generator.net",
                "amount_lost": 15000.00,
                "status": "verified",
                "ai_category_detected": "QR-Code Scams",
                "ai_confidence": 95.8,
                "ai_urgency_score": 80
            },
            {
                "report_ref": "REP-2026-INS-005",
                "receiver_upi_id": "sbi.kyc.verification@okhdfcbank",
                "receiver_name": "Insurance Claim Recovery Dept",
                "receiver_phone": "+91 98231 44521",
                "category": "Fake Insurance Agents",
                "description": "Caller claimed to be an IRDA officer and stated my lapsed LIC policy has an unclaimed bonus of Rs 1,80,000, requiring a processing fee payment of Rs 12,000 via UPI.",
                "suspicious_url": "",
                "amount_lost": 12000.00,
                "status": "verified",
                "ai_category_detected": "Fake Insurance Agents",
                "ai_confidence": 91.5,
                "ai_urgency_score": 70
            },
            {
                "report_ref": "REP-2026-JOB-006",
                "receiver_upi_id": "job.processing.fee@postbank",
                "receiver_name": "Global HR Career Recruitment",
                "receiver_phone": "+91 88990 11223",
                "category": "Fraudulent Payment Requests",
                "description": "WhatsApp message offered remote work liking YouTube videos for Rs 500 per task. Later asked for security deposit registration fee.",
                "suspicious_url": "",
                "amount_lost": 3500.00,
                "status": "under_review",
                "ai_category_detected": "Fraudulent Payment Requests",
                "ai_confidence": 88.0,
                "ai_urgency_score": 60
            }
        ]

        for rep in sample_reports:
            self.execute(
                """INSERT INTO fraud_reports 
                (report_ref, receiver_upi_id, receiver_name, receiver_phone, category, description, suspicious_url, amount_lost, status, ai_category_detected, ai_confidence, ai_urgency_score)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (rep["report_ref"], rep["receiver_upi_id"], rep["receiver_name"], rep["receiver_phone"],
                 rep["category"], rep["description"], rep["suspicious_url"], rep["amount_lost"], rep["status"],
                 rep["ai_category_detected"], rep["ai_confidence"], rep["ai_urgency_score"])
            )

        # 4. Sample blocked payment attempts
        sample_blocks = [
            {
                "block_ref": "BLK-2026-9081",
                "receiver_upi_id": "sbi.kyc.verification@okhdfcbank",
                "receiver_name": "SBI Helpdesk KYC Official",
                "amount": 25000.00,
                "note": "Urgent KYC fee to prevent freeze",
                "risk_score": 96,
                "block_reason": "High-risk fraud receiver: Matched 5 verified fake KYC scam reports and dangerous APK download indicators."
            },
            {
                "block_ref": "BLK-2026-9082",
                "receiver_upi_id": "electricity.bill.desk@paytm",
                "receiver_name": "Mahavitaran Bill Recovery Officer",
                "amount": 1450.00,
                "note": "Bill payment electricity overdue",
                "risk_score": 92,
                "block_reason": "High-risk fraud receiver: Matched 4 verified complaints for fake power disconnection fraud."
            }
        ]

        for blk in sample_blocks:
            self.execute(
                """INSERT INTO blocked_payments 
                (block_ref, receiver_upi_id, receiver_name, amount, note, risk_score, block_reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (blk["block_ref"], blk["receiver_upi_id"], blk["receiver_name"], blk["amount"], blk["note"],
                 blk["risk_score"], blk["block_reason"])
            )

        print("[DB] Initial synthetic dataset seeded successfully.")

# Global database manager instance
db = DatabaseManager()
