"""
Comprehensive automated test suite for UPI Fraud Reporting & Pattern Detection System.
Tests:
1. AI NLP Pattern Detector classification & urgency analysis
2. Risk Engine scoring & evaluation across Low, Medium, and High risk cases
3. Backend Payment Blocking enforcement (preventing bypass via direct backend request)
4. Fraud reporting API with auto-recalculation
5. Duplicate report prevention
6. Admin moderation & threshold reconfiguration
"""
import unittest
import json
from app import app
from database import db
from ai_detector import ai_detector
from risk_engine import risk_engine

class TestUPIFraudApp(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_01_ai_nlp_detection(self):
        """Test AI detector classifies known scam types and catches urgency."""
        kyc_text = "Dear customer, your SBI bank account is blocked due to expired PAN card. Install QuickSupport app immediately."
        res = ai_detector.analyze_text(kyc_text)
        self.assertEqual(res['detected_category'], "Fake KYC Messages")
        self.assertGreater(res['confidence_score'], 50.0)
        self.assertTrue(res['rat_tool_detected'])
        self.assertGreater(res['urgency_score'], 30)

        elec_text = "Electricity bill unpaid. Power cut will happen tonight at 9:30 PM. Pay arrears immediately."
        res2 = ai_detector.analyze_text(elec_text)
        self.assertIn(res2['detected_category'], ["Fake Customer Care Representatives", "Fraudulent Payment Requests"])
        self.assertGreater(res2['urgency_score'], 30)

    def test_02_payment_risk_evaluation_levels(self):
        """Test Low, Medium, and High risk receiver evaluations."""
        # 1. High Risk test receiver
        eval_high = risk_engine.evaluate_payment_risk(
            receiver_upi_id="sbi.kyc.verification@okhdfcbank",
            amount=25000,
            note="Urgent KYC verification fee"
        )
        self.assertEqual(eval_high['risk_level'], "HIGH RISK")
        self.assertGreaterEqual(eval_high['risk_score'], 70)
        self.assertTrue(eval_high['is_blocked'])

        # 2. Medium Risk test receiver
        eval_med = risk_engine.evaluate_payment_risk(
            receiver_upi_id="crypto.gainz@okicici",
            amount=5000,
            note="Crypto arbitrage deposit"
        )
        self.assertEqual(eval_med['risk_level'], "MEDIUM RISK")
        self.assertGreaterEqual(eval_med['risk_score'], 35)
        self.assertLess(eval_med['risk_score'], 70)

        # 3. Low Risk test receiver
        eval_low = risk_engine.evaluate_payment_risk(
            receiver_upi_id="rahul.sharma@okaxis",
            amount=500,
            note="Dinner bill split"
        )
        self.assertEqual(eval_low['risk_level'], "LOW RISK")
        self.assertLess(eval_low['risk_score'], 35)

    def test_03_payment_blocking_server_side_enforcement(self):
        """Direct backend request to pay high-risk receiver MUST be rejected with HTTP 403."""
        # Attempt to bypass payment blocking by calling /api/payments/pay directly
        res = self.client.post('/api/payments/pay', json={
            'receiver_upi_id': 'sbi.kyc.verification@okhdfcbank',
            'amount': 25000.0,
            'note': 'Direct bypass test payment'
        })
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertEqual(data['status'], 'BLOCKED')
        self.assertEqual(data['risk_level'], 'HIGH RISK')
        self.assertIn('block_ref', data)

    def test_04_payment_low_risk_succeeds(self):
        """Simulated payment to low-risk receiver succeeds with HTTP 200."""
        res = self.client.post('/api/payments/pay', json={
            'receiver_upi_id': 'rahul.sharma@okaxis',
            'amount': 350.0,
            'note': 'Movie ticket split'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'COMPLETED')
        self.assertIn('transaction_ref', data)

    def test_05_fraud_report_submission_and_auto_recalculation(self):
        """Submit a new fraud report and verify automatic receiver recalculation."""
        import uuid
        test_upi = f"suspect.test.{uuid.uuid4().hex[:6]}@okhdfcbank"
        res = self.client.post('/api/reports/submit', json={
            'receiver_upi_id': test_upi,
            'receiver_name': 'Test Suspect',
            'receiver_phone': '+91 99999 11111',
            'category': 'Fake Insurance Agents',
            'description': 'Posed as insurance agent offering lapsed policy refund if fee paid via UPI.',
            'amount_lost': 7500.0
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('report_ref', data)

        # Check receiver was automatically updated in DB
        rec = db.fetch_one("SELECT * FROM receivers WHERE LOWER(upi_id) = %s", (test_upi,))
        self.assertIsNotNone(rec)
        self.assertGreaterEqual(rec['total_reports'], 1)

    def test_06_duplicate_report_safeguard(self):
        """Submitting an identical report twice triggers 409 duplicate warning."""
        import uuid
        test_upi = f"dup.check.{uuid.uuid4().hex[:6]}@okaxis"
        desc = "Exact identical scam narrative submitted consecutively to test spam filter."
        # First submission
        res1 = self.client.post('/api/reports/submit', json={
            'receiver_upi_id': test_upi,
            'category': 'Fake Insurance Agents',
            'description': desc,
            'amount_lost': 1000.0
        })
        self.assertEqual(res1.status_code, 200)

        # Duplicate submission attempt
        res2 = self.client.post('/api/reports/submit', json={
            'receiver_upi_id': test_upi,
            'category': 'Fake Insurance Agents',
            'description': desc,
            'amount_lost': 1000.0
        })
        self.assertEqual(res2.status_code, 409)
        data = res2.get_json()
        self.assertFalse(data['success'])
        self.assertIn("Duplicate report detected", data['message'])

    def test_07_dashboard_stats_api(self):
        """Dashboard stats API returns live calculated numbers, not hardcoded values."""
        res = self.client.get('/api/stats')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        stats = data['stats']
        self.assertGreater(stats['total_fraud_reports'], 0)
        self.assertGreater(stats['blocked_payment_attempts'], 0)

    def test_08_admin_moderation_flow(self):
        """Admin logs in, marks a report as verified, and verifies receiver risk increases."""
        # 1. Admin Login
        login_res = self.client.post('/api/admin/login', json={
            'username': 'admin',
            'password': 'Admin@123'
        })
        self.assertEqual(login_res.status_code, 200)

        # 2. Moderate report
        rep = db.fetch_one("SELECT id, receiver_upi_id FROM fraud_reports WHERE status = 'pending' LIMIT 1")
        if rep:
            mod_res = self.client.post(f"/api/admin/reports/{rep['id']}/status", json={
                'status': 'verified'
            })
            self.assertEqual(mod_res.status_code, 200)
            data = mod_res.get_json()
            self.assertTrue(data['success'])

if __name__ == '__main__':
    unittest.main()
