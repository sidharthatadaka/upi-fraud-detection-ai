import os
import re
import uuid
import json
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from flask import Flask, request, jsonify, render_template, send_from_directory, session

from config import Config
from database import db
from ai_detector import ai_detector
from risk_engine import risk_engine

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config.from_object(Config)

# Ensure upload directory exists
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

# Auto-initialize database tables and seed initial data if missing (handles Render, Vercel & local WSGI)
try:
    db.init_tables()
    db.seed_initial_data()
except Exception as e:
    print(f"[DB Init Note] {e}")

# Initialize and retrain AI with all existing reports on launch
try:
    all_reports = db.fetch_all("SELECT category, description FROM fraud_reports WHERE description != ''")
    if all_reports:
        ai_detector.add_reports_and_retrain(all_reports)
        print(f"[AI] Initialized with {len(all_reports)} historical reports.")
except Exception as e:
    print(f"[AI] Init note: {e}")

# Helper: Allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

# Admin auth decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id') or session.get('role') != 'admin':
            return jsonify({'success': False, 'message': 'Admin authentication required.'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ==========================================
# Frontend Routes
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(Config.UPLOAD_FOLDER, filename)


# ==========================================
# Database & System Status APIs
# ==========================================

@app.route('/api/db-status', methods=['GET'])
def get_db_status():
    return jsonify({
        'engine_type': db.engine_type,
        'engine_name': db.engine_name,
        'connection_error': db.connection_error,
        'mysql_configured': Config.DB_PASSWORD != ''
    })

@app.route('/api/stats', methods=['GET'])
def get_dashboard_stats():
    """
    Returns real-time dashboard statistics:
    total fraud reports, suspicious UPI IDs, high-risk receivers,
    payments checked, and blocked payment attempts.
    """
    try:
        total_reports = db.fetch_one("SELECT COUNT(*) as count FROM fraud_reports")['count']
        
        # Suspicious UPI IDs: receivers with at least 1 report or score >= threshold_low
        low_t, high_t = risk_engine.get_thresholds()
        suspicious_receivers = db.fetch_one(
            "SELECT COUNT(*) as count FROM receivers WHERE total_reports > 0 OR risk_score >= %s",
            (low_t,)
        )['count']
        
        high_risk_receivers = db.fetch_one(
            "SELECT COUNT(*) as count FROM receivers WHERE risk_score >= %s OR risk_level = 'HIGH RISK'",
            (high_t,)
        )['count']
        
        payments_checked = db.fetch_one("SELECT COUNT(*) as count FROM risk_assessments")['count']
        blocked_attempts = db.fetch_one("SELECT COUNT(*) as count FROM blocked_payments")['count']
        completed_payments = db.fetch_one("SELECT COUNT(*) as count FROM simulated_transactions WHERE status = 'COMPLETED'")['count']

        # Category distribution
        categories = db.fetch_all(
            "SELECT category, COUNT(*) as count FROM fraud_reports GROUP BY category ORDER BY count DESC"
        )

        # Recent 5 reports
        recent_reports = db.fetch_all(
            "SELECT report_ref, receiver_upi_id, receiver_name, category, amount_lost, status, created_at FROM fraud_reports ORDER BY id DESC LIMIT 5"
        )

        # Recent 5 blocked attempts
        recent_blocked = db.fetch_all(
            "SELECT block_ref, receiver_upi_id, amount, block_reason, attempted_at FROM blocked_payments ORDER BY id DESC LIMIT 5"
        )

        return jsonify({
            'success': True,
            'stats': {
                'total_fraud_reports': total_reports,
                'suspicious_receivers': suspicious_receivers,
                'high_risk_receivers': high_risk_receivers,
                'payments_checked': payments_checked,
                'blocked_payment_attempts': blocked_attempts,
                'completed_payments': completed_payments
            },
            'categories': categories,
            'recent_reports': recent_reports,
            'recent_blocked': recent_blocked,
            'db_engine': db.engine_name
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ==========================================
# Payment Risk Checking & Simulation APIs
# ==========================================

@app.route('/api/payments/check-risk', methods=['POST'])
def check_payment_risk():
    """
    Evaluates receiver risk before simulated payment is executed.
    Accepts: receiver_upi_id, receiver_name, phone, amount, note, url.
    Returns: risk_score, risk_level, reasons, ai_analysis, is_blocked.
    """
    data = request.get_json() or {}
    receiver_upi = (data.get('receiver_upi_id') or '').strip()
    receiver_name = (data.get('receiver_name') or '').strip()
    phone = (data.get('phone') or '').strip()
    amount = data.get('amount', 0.0)
    note = (data.get('note') or '').strip()
    url = (data.get('url') or '').strip()

    if not receiver_upi:
        return jsonify({'success': False, 'message': 'Receiver UPI ID is required.'}), 400

    # Basic UPI ID format validation (must contain @)
    if '@' not in receiver_upi:
        return jsonify({'success': False, 'message': 'Invalid UPI ID format. Must contain "@" (e.g., name@okaxis).'}), 400

    try:
        evaluation = risk_engine.evaluate_payment_risk(
            receiver_upi_id=receiver_upi,
            receiver_name=receiver_name,
            phone=phone,
            amount=amount,
            note=note,
            url=url
        )
        return jsonify({
            'success': True,
            'evaluation': evaluation
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f"Error evaluating risk: {str(e)}"}), 500


@app.route('/api/payments/pay', methods=['POST'])
def process_simulated_payment():
    """
    Backend payment authorization and simulation endpoint.
    Strictly blocks payments if risk level is HIGH RISK.
    Enforces server-side blocking rules so frontend cannot bypass.
    """
    data = request.get_json() or {}
    receiver_upi = (data.get('receiver_upi_id') or '').strip()
    receiver_name = (data.get('receiver_name') or '').strip()
    phone = (data.get('phone') or '').strip()
    note = (data.get('note') or '').strip()
    confirmed_warning = bool(data.get('confirmed_warning', False))

    try:
        amount = float(data.get('amount', 0.0))
        if amount <= 0:
            return jsonify({'success': False, 'message': 'Payment amount must be greater than 0.'}), 400
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid payment amount specified.'}), 400

    if not receiver_upi:
        return jsonify({'success': False, 'message': 'Receiver UPI ID is required.'}), 400

    # 1. Independent Server-side Risk Verification
    eval_result = risk_engine.evaluate_payment_risk(
        receiver_upi_id=receiver_upi,
        receiver_name=receiver_name,
        phone=phone,
        amount=amount,
        note=note
    )

    risk_score = eval_result['risk_score']
    risk_level = eval_result['risk_level']
    reasons = eval_result['reasons']

    # 2. Strict Rule: High Risk Payments are BLOCKED by backend
    if risk_level == 'HIGH RISK':
        block_ref = f"BLK-{uuid.uuid4().hex[:8].upper()}"
        primary_reason = reasons[0] if reasons else "High-risk fraudulent receiver pattern detected."
        full_reason = f"Payment BLOCKED by AI Security Engine (Score: {risk_score}/100 - HIGH RISK). Reason: {primary_reason}"

        # Record blocked attempt in DB
        db.execute(
            """INSERT INTO blocked_payments 
            (block_ref, receiver_upi_id, receiver_name, amount, note, risk_score, block_reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (block_ref, receiver_upi, receiver_name or "Unknown", amount, note, risk_score, full_reason)
        )

        # Update risk assessment action
        try:
            db.execute(
                """UPDATE risk_assessments SET action_taken = 'blocked' 
                WHERE id = (SELECT id FROM risk_assessments WHERE LOWER(receiver_upi_id) = %s ORDER BY id DESC LIMIT 1)""",
                (receiver_upi.lower(),)
            )
        except Exception:
            pass

        return jsonify({
            'success': False,
            'status': 'BLOCKED',
            'block_ref': block_ref,
            'risk_level': risk_level,
            'risk_score': risk_score,
            'message': 'PAYMENT BLOCKED: The recipient exhibits critical fraud indicators. Simulated payment was rejected by backend security rules.',
            'reasons': reasons
        }), 403

    # 3. Medium Risk: Requires user confirmation
    if risk_level == 'MEDIUM RISK' and not confirmed_warning:
        return jsonify({
            'success': False,
            'status': 'WARNING_CONFIRMATION_REQUIRED',
            'risk_level': risk_level,
            'risk_score': risk_score,
            'message': 'Warning: Medium risk indicators detected. Please explicitly confirm you wish to proceed despite warnings.',
            'reasons': reasons
        }), 400

    # 4. Low Risk or Confirmed Medium Risk: Execute simulated payment
    txn_ref = f"UPI-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    db.execute(
        """INSERT INTO simulated_transactions 
        (transaction_ref, receiver_upi_id, receiver_name, amount, note, risk_level, risk_score, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'COMPLETED')""",
        (txn_ref, receiver_upi, receiver_name or "Merchant", amount, note, risk_level, risk_score)
    )

    try:
        db.execute(
            """UPDATE risk_assessments SET action_taken = 'paid' 
            WHERE id = (SELECT id FROM risk_assessments WHERE LOWER(receiver_upi_id) = %s ORDER BY id DESC LIMIT 1)""",
            (receiver_upi.lower(),)
        )
    except Exception:
        pass

    return jsonify({
        'success': True,
        'status': 'COMPLETED',
        'transaction_ref': txn_ref,
        'amount': amount,
        'receiver_upi_id': receiver_upi,
        'receiver_name': receiver_name or "Merchant",
        'risk_level': risk_level,
        'risk_score': risk_score,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'message': f'Simulated payment of Rs {amount:,.2f} to {receiver_upi} completed successfully.'
    })


# ==========================================
# Fraud Reporting & Auto-Update APIs
# ==========================================

@app.route('/api/reports/submit', methods=['POST'])
def submit_fraud_report():
    """
    Submits a new fraud report with optional evidence file upload.
    Automatically:
    - Saves report in DB
    - Extracts AI NLP patterns and urgency
    - Updates receiver record
    - Recalculates receiver risk assessment
    - Retrains AI model
    - Prevents duplicates and false reporting
    """
    # Support both JSON and multipart/form-data
    if request.is_json:
        data = request.get_json()
        evidence_filename = None
    else:
        data = request.form.to_dict()
        evidence_file = request.files.get('evidence_file')
        evidence_filename = None
        if evidence_file and evidence_file.filename and allowed_file(evidence_file.filename):
            ext = evidence_file.filename.rsplit('.', 1)[1].lower()
            evidence_filename = f"ev_{uuid.uuid4().hex[:10]}.{ext}"
            evidence_file.save(os.path.join(Config.UPLOAD_FOLDER, evidence_filename))

    receiver_upi = (data.get('receiver_upi_id') or '').strip().lower()
    receiver_name = (data.get('receiver_name') or '').strip()
    receiver_phone = (data.get('receiver_phone') or '').strip()
    category = (data.get('category') or '').strip()
    description = (data.get('description') or '').strip()
    suspicious_url = (data.get('suspicious_url') or '').strip()
    reporter_contact = (data.get('reporter_contact') or '').strip()

    try:
        amount_lost = float(data.get('amount_lost', 0.0))
    except (ValueError, TypeError):
        amount_lost = 0.0

    # Validation
    if not receiver_upi or '@' not in receiver_upi:
        return jsonify({'success': False, 'message': 'Valid Receiver UPI ID is required.'}), 400
    if not category:
        return jsonify({'success': False, 'message': 'Fraud category is required.'}), 400
    if not description or len(description.strip()) < 10:
        return jsonify({'success': False, 'message': 'Please provide a descriptive explanation (at least 10 characters).'}), 400

    # Anti-Spam / Duplicate Detection Safeguard:
    # Check if identical description or report was submitted for this UPI in the last 15 minutes
    existing_duplicate = db.fetch_one(
        """SELECT id, report_ref FROM fraud_reports 
        WHERE LOWER(receiver_upi_id) = %s AND LOWER(description) = %s""",
        (receiver_upi, description.lower())
    )
    if existing_duplicate:
        return jsonify({
            'success': False,
            'message': f'Duplicate report detected. An identical complaint is already registered under Reference #{existing_duplicate["report_ref"]}.'
        }), 409

    # AI NLP Analysis on description
    ai_analysis = ai_detector.analyze_text(description)
    detected_cat = ai_analysis['detected_category']
    confidence = ai_analysis['confidence_score']
    urgency_score = ai_analysis['urgency_score']

    report_ref = f"REP-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

    try:
        # 1. Save Report in Database
        db.execute(
            """INSERT INTO fraud_reports 
            (report_ref, receiver_upi_id, receiver_name, receiver_phone, category, description,
             suspicious_url, amount_lost, evidence_filename, reporter_contact, status,
             ai_category_detected, ai_confidence, ai_urgency_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s)""",
            (report_ref, receiver_upi, receiver_name, receiver_phone, category, description,
             suspicious_url, amount_lost, evidence_filename, reporter_contact,
             detected_cat, confidence, urgency_score)
        )

        # 2. Automatically update receiver and recalculate risk
        risk_engine.recalculate_receiver_risk(receiver_upi)

        # 3. Add to AI Detector knowledge base and dynamically retrain
        ai_detector.add_reports_and_retrain([{'category': category, 'description': description}])

        # Fetch updated receiver risk
        updated_receiver = db.fetch_one("SELECT * FROM receivers WHERE LOWER(upi_id) = %s", (receiver_upi,))

        return jsonify({
            'success': True,
            'message': 'Fraud report successfully recorded. Receiver risk profile and pattern database updated automatically.',
            'report_ref': report_ref,
            'ai_analysis': ai_analysis,
            'updated_receiver': updated_receiver
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f"Failed to record report: {str(e)}"}), 500


@app.route('/api/reports/preview-ai', methods=['POST'])
def preview_ai_analysis():
    """Live NLP preview endpoint for description input."""
    data = request.get_json() or {}
    text = (data.get('description') or '').strip()
    res = ai_detector.analyze_text(text)
    return jsonify({'success': True, 'analysis': res})


# ==========================================
# Fraud Report History & Details APIs
# ==========================================

@app.route('/api/reports', methods=['GET'])
def list_fraud_reports():
    """
    Searchable and filterable list of fraud reports.
    Query params: search, category, status, limit, offset.
    """
    search = request.args.get('search', '').strip().lower()
    category = request.args.get('category', '').strip()
    status = request.args.get('status', '').strip()
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))

    query = "SELECT * FROM fraud_reports WHERE 1=1"
    params = []

    if search:
        query += " AND (LOWER(receiver_upi_id) LIKE %s OR LOWER(receiver_name) LIKE %s OR LOWER(description) LIKE %s OR LOWER(report_ref) LIKE %s)"
        like_term = f"%{search}%"
        params.extend([like_term, like_term, like_term, like_term])

    if category:
        query += " AND category = %s"
        params.append(category)

    if status:
        query += " AND status = %s"
        params.append(status)

    query += " ORDER BY id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    reports = db.fetch_all(query, tuple(params))
    total_count = db.fetch_one("SELECT COUNT(*) as count FROM fraud_reports")['count']

    return jsonify({
        'success': True,
        'reports': reports,
        'total': total_count
    })


@app.route('/api/reports/<int:report_id>', methods=['GET'])
def get_report_detail(report_id):
    report = db.fetch_one("SELECT * FROM fraud_reports WHERE id = %s", (report_id,))
    if not report:
        return jsonify({'success': False, 'message': 'Report not found.'}), 404

    # Fetch matching receiver info
    receiver = db.fetch_one("SELECT * FROM receivers WHERE LOWER(upi_id) = %s", (report['receiver_upi_id'].lower(),))

    return jsonify({
        'success': True,
        'report': report,
        'receiver': receiver
    })


# ==========================================
# Receiver Risk Details Lookup API
# ==========================================

@app.route('/api/receivers/lookup', methods=['GET'])
def lookup_receiver():
    """
    Detailed receiver risk profile by UPI ID or Phone number.
    Returns cumulative risk score, level, verified status,
    historical complaints, and blocked payment attempts.
    """
    query_val = request.args.get('query', '').strip().lower()
    if not query_val:
        return jsonify({'success': False, 'message': 'Please provide a UPI ID or phone number to look up.'}), 400

    receiver = db.fetch_one(
        "SELECT * FROM receivers WHERE LOWER(upi_id) = %s OR phone LIKE %s",
        (query_val, f"%{query_val}%")
    )

    reports = db.fetch_all(
        "SELECT id, report_ref, category, description, amount_lost, status, created_at FROM fraud_reports WHERE LOWER(receiver_upi_id) = %s ORDER BY id DESC",
        (query_val if '@' in query_val else (receiver['upi_id'] if receiver else query_val),)
    )

    blocked = db.fetch_all(
        "SELECT block_ref, amount, block_reason, attempted_at FROM blocked_payments WHERE LOWER(receiver_upi_id) = %s ORDER BY id DESC",
        (query_val if '@' in query_val else (receiver['upi_id'] if receiver else query_val),)
    )

    if not receiver and not reports:
        # Not found in database -> Calculate baseline live assessment
        baseline = risk_engine.evaluate_payment_risk(receiver_upi_id=query_val)
        return jsonify({
            'success': True,
            'is_known': False,
            'receiver': {
                'upi_id': query_val,
                'name': 'Unregistered in Fraud Database',
                'phone': 'N/A',
                'total_reports': 0,
                'verified_reports': 0,
                'risk_score': baseline['risk_score'],
                'risk_level': baseline['risk_level'],
                'is_verified_fraud': 0
            },
            'reports': [],
            'blocked_payments': [],
            'reasons': baseline['reasons']
        })

    return jsonify({
        'success': True,
        'is_known': True,
        'receiver': receiver,
        'reports': reports,
        'blocked_payments': blocked
    })


# ==========================================
# Admin Authentication & Moderation APIs
# ==========================================

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required.'}), 400

    user = db.fetch_one("SELECT * FROM users WHERE username = %s", (username,))
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'success': False, 'message': 'Invalid admin username or password.'}), 401

    if user['role'] != 'admin':
        return jsonify({'success': False, 'message': 'Access restricted to administrators.'}), 403

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']

    return jsonify({
        'success': True,
        'message': 'Logged in successfully.',
        'user': {
            'username': user['username'],
            'email': user['email'],
            'role': user['role']
        }
    })

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully.'})

@app.route('/api/admin/me', methods=['GET'])
def admin_me():
    if not session.get('user_id') or session.get('role') != 'admin':
        return jsonify({'success': False, 'logged_in': False}), 200
    return jsonify({
        'success': True,
        'logged_in': True,
        'user': {
            'username': session.get('username'),
            'role': session.get('role')
        }
    })

@app.route('/api/admin/reports/<int:report_id>/status', methods=['POST'])
@admin_required
def update_report_status(report_id):
    """
    Moderates a report: 'verified', 'rejected', or 'under_review'.
    Automatically recalculates affected receiver's risk score and level.
    """
    data = request.get_json() or {}
    new_status = (data.get('status') or '').strip().lower()

    if new_status not in ('verified', 'rejected', 'under_review'):
        return jsonify({'success': False, 'message': "Status must be 'verified', 'rejected', or 'under_review'."}), 400

    report = db.fetch_one("SELECT * FROM fraud_reports WHERE id = %s", (report_id,))
    if not report:
        return jsonify({'success': False, 'message': 'Report not found.'}), 404

    db.execute(
        "UPDATE fraud_reports SET status = %s WHERE id = %s",
        (new_status, report_id)
    )

    # Automatically recalculate affected receiver risk
    receiver_upi = report['receiver_upi_id']
    risk_engine.recalculate_receiver_risk(receiver_upi)

    # If verified, trigger AI retrain with high weight
    if new_status == 'verified':
        ai_detector.add_reports_and_retrain([{'category': report['category'], 'description': report['description']}])

    updated_rec = db.fetch_one("SELECT * FROM receivers WHERE LOWER(upi_id) = %s", (receiver_upi.lower(),))

    return jsonify({
        'success': True,
        'message': f"Report #{report['report_ref']} status updated to '{new_status}'. Receiver risk recalculated.",
        'receiver': updated_rec
    })

@app.route('/api/admin/settings', methods=['GET', 'POST'])
@admin_required
def manage_settings():
    """View or update system risk thresholds."""
    if request.method == 'GET':
        low, high = risk_engine.get_thresholds()
        return jsonify({
            'success': True,
            'threshold_low': low,
            'threshold_high': high
        })
    else:
        data = request.get_json() or {}
        low = int(data.get('threshold_low', 35))
        high = int(data.get('threshold_high', 70))
        if low >= high:
            return jsonify({'success': False, 'message': 'Low threshold must be less than High threshold.'}), 400

        risk_engine.update_thresholds(low, high)
        return jsonify({
            'success': True,
            'message': f"Thresholds updated: Low < {low}, High >= {high}",
            'threshold_low': low,
            'threshold_high': high
        })

@app.route('/api/admin/logs', methods=['GET'])
@admin_required
def admin_logs():
    """Retrieve audit logs of blocked payment attempts and simulated transactions."""
    blocks = db.fetch_all("SELECT * FROM blocked_payments ORDER BY id DESC LIMIT 50")
    txns = db.fetch_all("SELECT * FROM simulated_transactions ORDER BY id DESC LIMIT 50")
    return jsonify({
        'success': True,
        'blocked_payments': blocks,
        'simulated_transactions': txns
    })


# ==========================================
# Main Execution
# ==========================================

if __name__ == '__main__':
    # Initialize DB tables and seed if necessary on startup
    try:
        db.init_tables()
        db.seed_initial_data()
    except Exception as e:
        print(f"[Startup Warning] DB init error: {e}")

    print("\n" + "=" * 60)
    print("UPI FRAUD REPORTING & PATTERN DETECTION USING AI")
    print(f"Server starting on http://localhost:{Config.PORT}")
    print(f"Active Database: {db.engine_name}")
    print("=" * 60 + "\n")

    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
