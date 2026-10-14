-- UPI Fraud Reporting & Pattern Detection Using AI
-- MySQL Database Schema

CREATE DATABASE IF NOT EXISTS upi_fraud_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE upi_fraud_db;

-- 1. Users Table (Admin & System users)
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(60) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. Receivers Profile Table
CREATE TABLE IF NOT EXISTS receivers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    upi_id VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(120),
    phone VARCHAR(20),
    total_reports INT DEFAULT 0,
    verified_reports INT DEFAULT 0,
    rejected_reports INT DEFAULT 0,
    risk_score INT DEFAULT 10,
    risk_level VARCHAR(20) DEFAULT 'LOW RISK',
    is_verified_fraud TINYINT(1) DEFAULT 0,
    flagged_urls TEXT,
    last_assessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_upi_id (upi_id),
    INDEX idx_phone (phone)
) ENGINE=InnoDB;

-- 3. Fraud Reports Table
CREATE TABLE IF NOT EXISTS fraud_reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    report_ref VARCHAR(40) NOT NULL UNIQUE,
    receiver_upi_id VARCHAR(100) NOT NULL,
    receiver_name VARCHAR(120),
    receiver_phone VARCHAR(20),
    category VARCHAR(60) NOT NULL,
    description TEXT NOT NULL,
    suspicious_url VARCHAR(255),
    amount_lost DECIMAL(12, 2) DEFAULT 0.00,
    evidence_filename VARCHAR(255),
    reporter_contact VARCHAR(100),
    status VARCHAR(30) DEFAULT 'pending',
    ai_category_detected VARCHAR(60),
    ai_confidence DECIMAL(5, 2) DEFAULT 0.00,
    ai_urgency_score INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_rep_upi (receiver_upi_id),
    INDEX idx_rep_status (status),
    INDEX idx_rep_cat (category)
) ENGINE=InnoDB;

-- 4. Risk Assessments History Table
CREATE TABLE IF NOT EXISTS risk_assessments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assessment_ref VARCHAR(40) NOT NULL UNIQUE,
    receiver_upi_id VARCHAR(100) NOT NULL,
    payer_amount DECIMAL(12, 2) DEFAULT 0.00,
    payer_note TEXT,
    risk_score INT NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    reasons_json TEXT,
    ai_score INT DEFAULT 0,
    action_taken VARCHAR(30) DEFAULT 'checked',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_risk_upi (receiver_upi_id)
) ENGINE=InnoDB;

-- 5. Simulated Transactions Table
CREATE TABLE IF NOT EXISTS simulated_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_ref VARCHAR(40) NOT NULL UNIQUE,
    receiver_upi_id VARCHAR(100) NOT NULL,
    receiver_name VARCHAR(120),
    amount DECIMAL(12, 2) NOT NULL,
    note VARCHAR(255),
    risk_level VARCHAR(20) NOT NULL,
    risk_score INT NOT NULL,
    status VARCHAR(30) DEFAULT 'COMPLETED',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tx_upi (receiver_upi_id)
) ENGINE=InnoDB;

-- 6. Blocked Payment Attempts Table
CREATE TABLE IF NOT EXISTS blocked_payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    block_ref VARCHAR(40) NOT NULL UNIQUE,
    receiver_upi_id VARCHAR(100) NOT NULL,
    receiver_name VARCHAR(120),
    amount DECIMAL(12, 2) NOT NULL,
    note VARCHAR(255),
    risk_score INT NOT NULL,
    block_reason TEXT NOT NULL,
    attempted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_block_upi (receiver_upi_id)
) ENGINE=InnoDB;

-- 7. System Settings Table
CREATE TABLE IF NOT EXISTS system_settings (
    key_name VARCHAR(60) PRIMARY KEY,
    key_value VARCHAR(255) NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;
