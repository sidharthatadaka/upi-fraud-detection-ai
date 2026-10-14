-- UPI Fraud Reporting & Pattern Detection Using AI
-- SQLite Fallback Database Schema

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Receivers Profile Table
CREATE TABLE IF NOT EXISTS receivers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upi_id TEXT NOT NULL UNIQUE,
    name TEXT,
    phone TEXT,
    total_reports INTEGER DEFAULT 0,
    verified_reports INTEGER DEFAULT 0,
    rejected_reports INTEGER DEFAULT 0,
    risk_score INTEGER DEFAULT 10,
    risk_level TEXT DEFAULT 'LOW RISK',
    is_verified_fraud INTEGER DEFAULT 0,
    flagged_urls TEXT,
    last_assessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rec_upi ON receivers(upi_id);
CREATE INDEX IF NOT EXISTS idx_rec_phone ON receivers(phone);

-- 3. Fraud Reports Table
CREATE TABLE IF NOT EXISTS fraud_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_ref TEXT NOT NULL UNIQUE,
    receiver_upi_id TEXT NOT NULL,
    receiver_name TEXT,
    receiver_phone TEXT,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    suspicious_url TEXT,
    amount_lost REAL DEFAULT 0.0,
    evidence_filename TEXT,
    reporter_contact TEXT,
    status TEXT DEFAULT 'pending',
    ai_category_detected TEXT,
    ai_confidence REAL DEFAULT 0.0,
    ai_urgency_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rep_upi ON fraud_reports(receiver_upi_id);
CREATE INDEX IF NOT EXISTS idx_rep_status ON fraud_reports(status);
CREATE INDEX IF NOT EXISTS idx_rep_cat ON fraud_reports(category);

-- 4. Risk Assessments History Table
CREATE TABLE IF NOT EXISTS risk_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_ref TEXT NOT NULL UNIQUE,
    receiver_upi_id TEXT NOT NULL,
    payer_amount REAL DEFAULT 0.0,
    payer_note TEXT,
    risk_score INTEGER NOT NULL,
    risk_level TEXT NOT NULL,
    reasons_json TEXT,
    ai_score INTEGER DEFAULT 0,
    action_taken TEXT DEFAULT 'checked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Simulated Transactions Table
CREATE TABLE IF NOT EXISTS simulated_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_ref TEXT NOT NULL UNIQUE,
    receiver_upi_id TEXT NOT NULL,
    receiver_name TEXT,
    amount REAL NOT NULL,
    note TEXT,
    risk_level TEXT NOT NULL,
    risk_score INTEGER NOT NULL,
    status TEXT DEFAULT 'COMPLETED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Blocked Payment Attempts Table
CREATE TABLE IF NOT EXISTS blocked_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    block_ref TEXT NOT NULL UNIQUE,
    receiver_upi_id TEXT NOT NULL,
    receiver_name TEXT,
    amount REAL NOT NULL,
    note TEXT,
    risk_score INTEGER NOT NULL,
    block_reason TEXT NOT NULL,
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. System Settings Table
CREATE TABLE IF NOT EXISTS system_settings (
    key_name TEXT PRIMARY KEY,
    key_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
