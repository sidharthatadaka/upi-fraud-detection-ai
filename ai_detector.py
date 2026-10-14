import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics.pairwise import cosine_similarity

class AIFraudDetector:
    CATEGORIES = [
        "Fake KYC Messages",
        "Fraudulent Payment Requests",
        "QR-Code Scams",
        "Fake Insurance Agents",
        "Fake Bank Employees",
        "Fake Customer Care Representatives",
        "Impersonation and Investment Scams"
    ]

    # Pre-compiled high-risk keywords and patterns
    URGENCY_KEYWORDS = [
        r'\b(immediately|urgent|within\s+\d+\s*(hours?|mins?)|tonight|expir(ed|ing)|suspend(ed)?|blocked?|disconnect(ed)?|freeze)\b',
        r'\b(power\s+cut|electricity\s+bill\s+unpaid|sim\s+block|pan\s+card\s+deactivated|kyc\s+mandatory)\b',
        r'\b(fir|police|legal\s+action|warrant|rbi\s+order)\b'
    ]

    RAT_TOOLS_KEYWORDS = [
        r'\b(anydesk|teamviewer|rustdesk|quicksupport|screen\s*share|apk\s+file|download\s+link|airdroid)\b'
    ]

    SUSPICIOUS_UPI_KEYWORDS = [
        'kyc', 'support', 'helpdesk', 'care', 'refund', 'official', 'recovery',
        'verification', 'manager', 'nodal', 'claim', 'bonus', 'crypto', 'vip'
    ]

    def __init__(self):
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english', min_df=1)
        self.classifier = MultinomialNB()
        self.trained_texts = []
        self.trained_labels = []
        self.is_trained = False
        self._init_training_corpus()

    def _init_training_corpus(self):
        """Curated synthetic training dataset covering all 7 UPI scam categories."""
        training_data = [
            # Fake KYC Messages
            ("Dear customer your SBI bank account is blocked due to expired PAN KYC update urgently click link", "Fake KYC Messages"),
            ("Your SIM card will be deactivated in 24 hours. Complete KYC verification by paying 10 rupees", "Fake KYC Messages"),
            ("HDFC bank alert: KYC verification pending. Install QuickSupport or AnyDesk app to verify Aadhaar", "Fake KYC Messages"),
            ("Paytm KYC expired. Account suspended. Complete your document upload through APK link immediately", "Fake KYC Messages"),
            ("Urgent Notice: Axis Bank debit card and net banking frozen due to KYC non-compliance submit PAN", "Fake KYC Messages"),
            ("Update your ICICI bank KYC online or your balance will be frozen within 2 hours", "Fake KYC Messages"),

            # Fraudulent Payment Requests
            ("Received a sudden UPI collect request from unknown merchant claiming refund confirmation", "Fraudulent Payment Requests"),
            ("Fraudster asked for payment advance processing fee to unlock courier delivery parcel", "Fraudulent Payment Requests"),
            ("Demanded registration charge before releasing winning lottery amount", "Fraudulent Payment Requests"),
            ("Sent repeated UPI pay requests pretending to be security deposit for apartment rental lease", "Fraudulent Payment Requests"),
            ("Posing as buyer on marketplace and requested advance delivery charge payment", "Fraudulent Payment Requests"),

            # QR-Code Scams
            ("OLX buyer sent QR code saying scan this QR code to receive money in your bank account", "QR-Code Scams"),
            ("Scammer told me to enter UPI PIN to accept payment for old furniture sale", "QR-Code Scams"),
            ("Received QR code for cashback prize. Scanning it debited money instead of crediting", "QR-Code Scams"),
            ("Reverse payment scam: seller asked to scan QR code to refund excess amount paid", "QR-Code Scams"),
            ("Merchant printed fake QR sticker over genuine payment stand at shop counter", "QR-Code Scams"),
            ("Scammer sent QR code screenshot via WhatsApp promising government subsidy credit", "QR-Code Scams"),

            # Fake Insurance Agents
            ("Caller claimed to be IRDA officer offering bonus payout of 2 lakhs on lapsed LIC policy", "Fake Insurance Agents"),
            ("Fake agent demanded 15000 fee to release matured insurance fund dividend payment", "Fake Insurance Agents"),
            ("Pretended to be Max Life insurance manager offering loan against policy after commission fee", "Fake Insurance Agents"),
            ("Offered zero cost insurance policy topup but transferred money to personal UPI account", "Fake Insurance Agents"),
            ("Insurance surrender value release agent requested GST payment via UPI", "Fake Insurance Agents"),

            # Fake Bank Employees
            ("Caller posed as SBI credit card department offering reward point redemption and asked for OTP", "Fake Bank Employees"),
            ("Pretended to be HDFC bank fraud prevention team and asked to move funds to safe pool account", "Fake Bank Employees"),
            ("Claimed to be RBI nodal officer investigating unauthorized international transaction", "Fake Bank Employees"),
            ("Bank manager impersonator requested card limit enhancement verification fee", "Fake Bank Employees"),
            ("Posed as loan department officer asking for processing charges via UPI before loan disbursal", "Fake Bank Employees"),

            # Fake Customer Care Representatives
            ("Electricity board SMS: Power will be disconnected tonight at 9:30 PM due to unpaid electricity bill", "Fake Customer Care Representatives"),
            ("Electricity officer demanded immediate payment of bill arrears to avoid disconnection", "Fake Customer Care Representatives"),
            ("Searched Google for airline customer care number, executive sent UPI link for flight cancellation refund", "Fake Customer Care Representatives"),
            ("Swiggy delivery refund customer care asked to download remote app to process refund", "Fake Customer Care Representatives"),
            ("Amazon customer support fake agent claimed package stuck in customs pay clearance tax", "Fake Customer Care Representatives"),
            ("Fake courier FedEx helpline asked for custom clearance fees via UPI transfer", "Fake Customer Care Representatives"),

            # Impersonation and Investment Scams
            ("Joined Telegram investment group promising 300% profit in 24 hours via crypto arbitrage", "Impersonation and Investment Scams"),
            ("Part-time job task scam: paid 150 for liking YouTube videos, then asked to deposit 50,000 in VIP task", "Impersonation and Investment Scams"),
            ("Fake Instagram trader claimed guaranteed return on share trading pool investment", "Impersonation and Investment Scams"),
            ("WhatsApp invitation to earn 5000 daily working from home after paying registration fee", "Impersonation and Investment Scams"),
            ("Cryptocurrency doubling scheme required transferring money to personal UPI handle", "Impersonation and Investment Scams"),
            ("Fake celebrity endorsement of quantum trading bot requiring initial UPI deposit", "Impersonation and Investment Scams")
        ]

        texts, labels = zip(*training_data)
        self.train(list(texts), list(labels))

    def train(self, texts, labels):
        """Fit vectorizer and classifier on provided texts and labels."""
        self.trained_texts = texts
        self.trained_labels = labels
        X = self.vectorizer.fit_transform(texts)
        self.classifier.fit(X, labels)
        self.is_trained = True

    def add_reports_and_retrain(self, db_reports):
        """Augment baseline training dataset with reports from database and retrain."""
        new_texts = list(self.trained_texts)
        new_labels = list(self.trained_labels)
        for r in db_reports:
            desc = r.get('description', '')
            cat = r.get('category', '')
            if desc and cat and cat in self.CATEGORIES:
                new_texts.append(desc)
                new_labels.append(cat)
        if len(new_texts) > len(self.trained_texts):
            self.train(new_texts, new_labels)

    def analyze_text(self, text):
        """
        Runs comprehensive NLP analysis on a fraud description or payment note.
        Returns:
            - detected_category: best matching category
            - confidence_score: classification probability (0 - 100%)
            - urgency_score: presence of urgency / threat patterns (0 - 100)
            - rat_tool_detected: boolean
            - matched_keywords: list of detected high-risk words
        """
        if not text or not text.strip():
            return {
                "detected_category": "Unknown",
                "confidence_score": 0.0,
                "urgency_score": 0,
                "rat_tool_detected": False,
                "matched_keywords": []
            }

        text_lower = text.lower()
        matched_keywords = []

        # 1. Pattern analysis for Urgency
        urgency_score = 0
        for pattern in self.URGENCY_KEYWORDS:
            matches = re.findall(pattern, text_lower)
            if matches:
                urgency_score += 35
                for m in matches:
                    matched_keywords.append(m if isinstance(m, str) else m[0])
        urgency_score = min(urgency_score, 100)

        # 2. Pattern analysis for Remote Access Tools / APKs
        rat_tool_detected = False
        for pattern in self.RAT_TOOLS_KEYWORDS:
            matches = re.findall(pattern, text_lower)
            if matches:
                rat_tool_detected = True
                urgency_score = min(urgency_score + 30, 100)
                for m in matches:
                    matched_keywords.append(m if isinstance(m, str) else m[0])

        # 3. ML Classification
        X_vec = self.vectorizer.transform([text])
        probs = self.classifier.predict_proba(X_vec)[0]
        max_idx = np.argmax(probs)
        detected_category = self.classifier.classes_[max_idx]
        top_prob = float(probs[max_idx])
        num_classes = len(self.classifier.classes_)
        baseline = 1.0 / max(1, num_classes)

        if top_prob > baseline:
            # Calibrate confidence based on margin above random chance
            confidence_score = round(min(98.0, 50.0 + ((top_prob - baseline) / (1.0 - baseline)) * 48.0), 2)
        else:
            confidence_score = round(top_prob * 100, 2)

        # Low word count penalty on confidence
        word_count = len(text.split())
        if word_count < 4:
            confidence_score = round(confidence_score * 0.5, 2)

        return {
            "detected_category": detected_category,
            "confidence_score": confidence_score,
            "urgency_score": urgency_score,
            "rat_tool_detected": rat_tool_detected,
            "matched_keywords": list(set(matched_keywords))
        }

    def compute_similarity_with_known_reports(self, text, known_reports):
        """
        Computes TF-IDF Cosine Similarity between the incoming text and existing reports.
        Returns:
            - max_similarity: float percentage (0 - 100)
            - most_similar_report: dict or None
        """
        if not text or not known_reports:
            return 0.0, None

        descriptions = [r.get('description', '') for r in known_reports if r.get('description')]
        if not descriptions:
            return 0.0, None

        try:
            vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english')
            all_texts = [text] + descriptions
            tfidf_matrix = vectorizer.fit_transform(all_texts)
            
            # Cosine similarity between text (index 0) and all previous reports (index 1..)
            cosine_sims = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
            best_idx = int(np.argmax(cosine_sims))
            max_sim = round(float(cosine_sims[best_idx]) * 100, 2)
            
            matching_report = known_reports[best_idx] if best_idx < len(known_reports) else None
            return max_sim, matching_report
        except Exception:
            return 0.0, None

    def analyze_upi_handle(self, upi_id):
        """Checks for suspicious patterns in UPI handle naming (e.g. impersonation keywords)."""
        if not upi_id or '@' not in upi_id:
            return {
                "is_suspicious_handle": False,
                "flags": ["Invalid UPI format"] if upi_id else []
            }
        
        handle_prefix = upi_id.split('@')[0].lower()
        flags = []
        for kw in self.SUSPICIOUS_UPI_KEYWORDS:
            if kw in handle_prefix:
                flags.append(f"UPI ID prefix contains suspicious keyword '{kw}'")
        
        # Check for numeric or gibberish suspicious pattern
        if re.search(r'\d{6,}', handle_prefix):
            flags.append("Handle contains extended numeric sequence")

        return {
            "is_suspicious_handle": len(flags) > 0,
            "flags": flags
        }

# Global AI detector instance
ai_detector = AIFraudDetector()
