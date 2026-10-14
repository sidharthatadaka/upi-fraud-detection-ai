import json
import re
from config import Config
from database import db
from ai_detector import ai_detector

class RiskEngine:
    def __init__(self):
        self.threshold_low = Config.RISK_THRESHOLD_LOW
        self.threshold_high = Config.RISK_THRESHOLD_HIGH

    def get_thresholds(self):
        """Fetch live thresholds from settings table if present."""
        try:
            low_row = db.fetch_one("SELECT key_value FROM system_settings WHERE key_name = 'risk_threshold_low'")
            high_row = db.fetch_one("SELECT key_value FROM system_settings WHERE key_name = 'risk_threshold_high'")
            if low_row:
                self.threshold_low = int(low_row['key_value'])
            if high_row:
                self.threshold_high = int(high_row['key_value'])
        except Exception:
            pass
        return self.threshold_low, self.threshold_high

    def update_thresholds(self, low, high):
        """Update system risk thresholds in database."""
        self.threshold_low = int(low)
        self.threshold_high = int(high)
        db.execute("INSERT INTO system_settings (key_name, key_value) VALUES ('risk_threshold_low', %s) ON DUPLICATE KEY UPDATE key_value = %s", (str(low), str(low)))
        db.execute("INSERT INTO system_settings (key_name, key_value) VALUES ('risk_threshold_high', %s) ON DUPLICATE KEY UPDATE key_value = %s", (str(high), str(high)))

    def evaluate_payment_risk(self, receiver_upi_id, receiver_name=None, phone=None, amount=0.0, note="", url=""):
        """
        Calculates comprehensive risk score (0-100), risk level (LOW/MEDIUM/HIGH),
        and detailed explanatory reasons.
        """
        self.get_thresholds()
        reasons = []
        score = 0
        upi_clean = (receiver_upi_id or "").strip().lower()
        phone_clean = re.sub(r'[^0-9+]', '', phone) if phone else ""
        combined_text = f"{note} {url}".strip()

        # 1. Receiver Database Lookup
        receiver = db.fetch_one("SELECT * FROM receivers WHERE LOWER(upi_id) = %s", (upi_clean,))
        reports_for_receiver = db.fetch_all("SELECT * FROM fraud_reports WHERE LOWER(receiver_upi_id) = %s", (upi_clean,))
        
        verified_count = 0
        pending_count = 0
        rejected_count = 0

        if receiver:
            base_score = receiver.get('risk_score', 0)
            score = base_score
            verified_count = receiver.get('verified_reports', 0)
            rejected_count = receiver.get('rejected_reports', 0)
            pending_count = max(0, receiver.get('total_reports', 0) - verified_count - rejected_count)

            if receiver.get('is_verified_fraud') == 1:
                score = max(score, 85)
                reasons.append("Receiver is officially marked as a Verified Fraudster in the database.")
            elif base_score >= self.threshold_high:
                reasons.append(f"Receiver has an established high-risk profile in database (Score: {base_score}/100).")
            elif base_score >= self.threshold_low:
                reasons.append(f"Receiver has an established medium-risk monitoring status (Score: {base_score}/100).")

            if verified_count > 0:
                reasons.append(f"Receiver has {verified_count} verified fraud report(s) on record.")
            if pending_count > 0:
                reasons.append(f"Receiver has {pending_count} unverified community report(s) under review.")
        elif reports_for_receiver:
            verified_count = sum(1 for r in reports_for_receiver if r.get('status') == 'verified')
            pending_count = sum(1 for r in reports_for_receiver if r.get('status') in ('pending', 'under_review'))
            rejected_count = sum(1 for r in reports_for_receiver if r.get('status') == 'rejected')

            if verified_count > 0:
                verified_pts = min(verified_count * 25, 60)
                score += verified_pts
                reasons.append(f"Receiver has {verified_count} verified fraud report(s) on record (+{verified_pts} risk).")

            if pending_count > 0:
                pending_pts = min(pending_count * 8, 20)
                score += pending_pts
                reasons.append(f"Receiver has {pending_count} unverified community report(s) under review (+{pending_pts} risk).")

        # 2. Blocked Payment Attempts Check
        blocks = db.fetch_all("SELECT * FROM blocked_payments WHERE LOWER(receiver_upi_id) = %s", (upi_clean,))
        if blocks and not receiver:
            block_pts = min(len(blocks) * 12, 24)
            score += block_pts
            reasons.append(f"System previously blocked {len(blocks)} suspicious payment attempt(s) to this receiver (+{block_pts} risk).")

        # 3. Phone Number Check
        if phone_clean:
            matching_phone_reports = db.fetch_all(
                "SELECT status, COUNT(*) as cnt FROM fraud_reports WHERE receiver_phone LIKE %s GROUP BY status",
                (f"%{phone_clean[-10:]}%",)
            )
            phone_verified = sum(r['cnt'] for r in matching_phone_reports if r['status'] == 'verified')
            phone_pending = sum(r['cnt'] for r in matching_phone_reports if r['status'] in ('pending', 'under_review'))
            
            if phone_verified > 0:
                score += 25
                reasons.append(f"Phone number ({phone}) matches {phone_verified} verified fraud complaint(s) (+25 risk).")
            elif phone_pending > 0:
                score += 10
                reasons.append(f"Phone number ({phone}) is associated with {phone_pending} pending report(s) (+10 risk).")

        # 4. UPI Handle Analysis (Heuristics for unregistered receivers)
        if not receiver:
            upi_analysis = ai_detector.analyze_upi_handle(upi_clean)
            if upi_analysis["is_suspicious_handle"]:
                score += 15
                for flag in upi_analysis["flags"]:
                    reasons.append(f"UPI Handle Indicator: {flag} (+15 risk).")

        # 5. AI NLP Analysis on Payment Note / Description
        ai_res = ai_detector.analyze_text(combined_text)
        ai_score = 0
        if combined_text:
            if ai_res["rat_tool_detected"]:
                score += 25
                ai_score += 35
                reasons.append("AI Pattern Alert: Remote Desktop application or APK download reference detected in note (+25 risk).")

            if ai_res["urgency_score"] > 50:
                score += 15
                ai_score += 20
                reasons.append(f"AI Urgency Alert: High pressure / urgent deadline pattern detected ({ai_res['urgency_score']}% urgency intensity).")

            # Check similarity with database of verified fraud reports
            verified_reports_all = db.fetch_all("SELECT description FROM fraud_reports WHERE status = 'verified'")
            max_sim, best_match = ai_detector.compute_similarity_with_known_reports(combined_text, verified_reports_all)
            if max_sim >= 60.0:
                score += 20
                ai_score += 30
                reasons.append(f"AI Similarity: Note text has {max_sim:.1f}% semantic similarity to known {best_match.get('category', 'fraud')} scam descriptions.")
            elif max_sim >= 40.0:
                score += 10
                reasons.append(f"AI Similarity: Note text shows moderate similarity ({max_sim:.1f}%) to existing fraud reports.")

        # 6. High Amount with Low Trust Warning
        try:
            amt_val = float(amount)
            if amt_val >= 25000 and (pending_count > 0 or score >= 25):
                score += 10
                reasons.append(f"High transaction value (Rs {amt_val:,.2f}) combined with existing risk indicators (+10 risk).")
        except (ValueError, TypeError):
            pass

        # Default safe baseline if no indicators found
        if not reasons:
            score = 5
            reasons.append("No suspicious indicators or previous fraud complaints found for this receiver.")

        # Clamp score between 0 and 100
        score = max(0, min(100, score))

        # Determine Risk Level
        if score < self.threshold_low:
            risk_level = "LOW RISK"
        elif score < self.threshold_high:
            risk_level = "MEDIUM RISK"
        else:
            risk_level = "HIGH RISK"

        # Record this assessment in database
        import uuid
        assessment_ref = f"ASM-{uuid.uuid4().hex[:8].upper()}"
        try:
            db.execute(
                """INSERT INTO risk_assessments 
                (assessment_ref, receiver_upi_id, payer_amount, payer_note, risk_score, risk_level, reasons_json, ai_score, action_taken)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (assessment_ref, upi_clean, amount, combined_text, score, risk_level, json.dumps(reasons), ai_score, 'checked')
            )
        except Exception as e:
            print(f"[RiskEngine] Failed to save assessment log: {e}")

        return {
            "assessment_ref": assessment_ref,
            "receiver_upi_id": upi_clean,
            "receiver_name": receiver_name or (receiver['name'] if receiver else "Unknown"),
            "risk_score": score,
            "risk_level": risk_level,
            "reasons": reasons,
            "ai_analysis": ai_res,
            "is_blocked": (risk_level == "HIGH RISK"),
            "thresholds": {
                "low": self.threshold_low,
                "high": self.threshold_high
            }
        }

    def recalculate_receiver_risk(self, upi_id):
        """
        Recalculates and updates the cumulative risk profile for a receiver
        whenever a new fraud report is added or moderated.
        """
        upi_clean = (upi_id or "").strip().lower()
        if not upi_clean:
            return

        self.get_thresholds()
        reports = db.fetch_all("SELECT * FROM fraud_reports WHERE LOWER(receiver_upi_id) = %s", (upi_clean,))
        total_reports = len(reports)
        verified_reports = sum(1 for r in reports if r.get('status') == 'verified')
        rejected_reports = sum(1 for r in reports if r.get('status') == 'rejected')
        pending_reports = total_reports - verified_reports - rejected_reports

        # Calculate base receiver risk score
        score = 5
        if verified_reports > 0:
            score += min(verified_reports * 28, 65)
        if pending_reports > 0:
            score += min(pending_reports * 8, 20)

        # Check for blocked payments
        blocks = db.fetch_all("SELECT id FROM blocked_payments WHERE LOWER(receiver_upi_id) = %s", (upi_clean,))
        if blocks:
            score += min(len(blocks) * 10, 20)

        score = max(5, min(100, score))
        if score < self.threshold_low:
            risk_level = "LOW RISK"
        elif score < self.threshold_high:
            risk_level = "MEDIUM RISK"
        else:
            risk_level = "HIGH RISK"

        is_verified_fraud = 1 if (verified_reports >= 1 or score >= self.threshold_high) else 0

        # Update or Insert receiver record
        existing = db.fetch_one("SELECT id FROM receivers WHERE LOWER(upi_id) = %s", (upi_clean,))
        if existing:
            db.execute(
                """UPDATE receivers 
                SET total_reports = %s, verified_reports = %s, rejected_reports = %s,
                    risk_score = %s, risk_level = %s, is_verified_fraud = %s, last_assessed_at = CURRENT_TIMESTAMP
                WHERE LOWER(upi_id) = %s""",
                (total_reports, verified_reports, rejected_reports, score, risk_level, is_verified_fraud, upi_clean)
            )
        else:
            # Extract sample receiver name and phone from reports if available
            rep = reports[0] if reports else {}
            db.execute(
                """INSERT INTO receivers 
                (upi_id, name, phone, total_reports, verified_reports, rejected_reports, risk_score, risk_level, is_verified_fraud)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (upi_clean, rep.get('receiver_name', 'Reported Receiver'), rep.get('receiver_phone', ''),
                 total_reports, verified_reports, rejected_reports, score, risk_level, is_verified_fraud)
            )

        print(f"[RiskEngine] Recalculated risk for {upi_clean}: Score {score} ({risk_level})")

# Global Risk Engine instance
risk_engine = RiskEngine()
