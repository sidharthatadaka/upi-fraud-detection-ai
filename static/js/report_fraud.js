/**
 * report_fraud.js - Fraud Reporting with Live NLP Preview and Auto-Recalculation
 */

let typingTimer = null;

function handleDescriptionTyping() {
  clearTimeout(typingTimer);
  const text = document.getElementById('report-desc').value.trim();
  const previewBox = document.getElementById('ai-live-preview');

  if (text.length < 12) {
    previewBox.style.display = 'none';
    return;
  }

  typingTimer = setTimeout(async () => {
    try {
      const res = await fetch('/api/reports/preview-ai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: text })
      });
      const data = await res.json();
      if (data.success && data.analysis) {
        const ai = data.analysis;
        previewBox.style.display = 'flex';

        const catBadge = document.getElementById('live-cat-badge');
        catBadge.textContent = `AI Predicted: ${ai.detected_category} (${ai.confidence_score}%)`;

        const urgBadge = document.getElementById('live-urgency-badge');
        urgBadge.textContent = `Urgency Intensity: ${ai.urgency_score}/100`;
        urgBadge.className = `badge ${ai.urgency_score > 60 ? 'badge-high' : (ai.urgency_score > 25 ? 'badge-med' : 'badge-low')}`;

        const ratBadge = document.getElementById('live-rat-badge');
        if (ai.rat_tool_detected) {
          ratBadge.style.display = 'inline-flex';
          ratBadge.className = 'badge badge-high';
          ratBadge.textContent = '⚠️ Remote Access App Flagged';
        } else {
          ratBadge.style.display = 'none';
        }
      }
    } catch (e) {
      console.warn('AI preview error:', e);
    }
  }, 400);
}

async function handleSubmitFraudReport(event) {
  event.preventDefault();
  const btn = document.getElementById('btn-submit-report');
  const upi = document.getElementById('report-upi').value.trim();
  const name = document.getElementById('report-name').value.trim();
  const phone = document.getElementById('report-phone').value.trim();
  const amount = document.getElementById('report-amount').value.trim();
  const category = document.getElementById('report-category').value;
  const url = document.getElementById('report-url').value.trim();
  const desc = document.getElementById('report-desc').value.trim();
  const reporter = document.getElementById('report-reporter').value.trim();
  const fileInput = document.getElementById('report-file');

  if (!upi || !category || !desc) {
    showToast('Please fill all mandatory fields (UPI ID, Category, Description)', 'warning');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '⏳ Submitting & Recalculating AI Patterns...';

  // Build FormData for file support
  const formData = new FormData();
  formData.append('receiver_upi_id', upi);
  formData.append('receiver_name', name);
  formData.append('receiver_phone', phone);
  formData.append('amount_lost', amount);
  formData.append('category', category);
  formData.append('suspicious_url', url);
  formData.append('description', desc);
  formData.append('reporter_contact', reporter);
  if (fileInput.files.length > 0) {
    formData.append('evidence_file', fileInput.files[0]);
  }

  try {
    const res = await fetch('/api/reports/submit', {
      method: 'POST',
      body: formData
    });

    const data = await res.json();
    btn.disabled = false;
    btn.innerHTML = '🚀 Submit Fraud Report';

    if (res.status === 409) {
      showToast(data.message || 'Duplicate report detected', 'warning', 6000);
      return;
    }

    if (!data.success) {
      showToast(data.message || 'Failed to submit report', 'error');
      return;
    }

    // Success Handling
    showToast('Fraud report accepted & receiver risk updated automatically!', 'success', 5000);

    const successBox = document.getElementById('report-success-box');
    const refNum = document.getElementById('success-ref-num');
    const impactBox = document.getElementById('success-receiver-impact');

    refNum.textContent = data.report_ref;

    const rec = data.updated_receiver || {};
    impactBox.innerHTML = `
      <div><strong>Target Recipient:</strong> ${rec.upi_id || upi}</div>
      <div><strong>New Total Reports:</strong> ${rec.total_reports || 1} complaints</div>
      <div><strong>Recalculated Risk Level:</strong> <span class="badge ${rec.risk_level === 'HIGH RISK' ? 'badge-high' : 'badge-med'}">${rec.risk_level || 'MEDIUM RISK'} (${rec.risk_score || 50}/100)</span></div>
      <div style="margin-top:6px; color:#94a3b8; font-size:0.8rem;">
        ⚡ The latest pattern has been committed to the active database and will immediately trigger warnings for any user attempting to pay this UPI ID.
      </div>
    `;

    successBox.style.display = 'block';
    successBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    // Instantly refresh dashboard statistics without page reload
    loadDashboardStats();

  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = '🚀 Submit Fraud Report';
    showToast('Error submitting report: ' + err.message, 'error');
  }
}

function resetReportForm() {
  document.getElementById('fraud-report-form').reset();
  document.getElementById('ai-live-preview').style.display = 'none';
  document.getElementById('report-success-box').style.display = 'none';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
