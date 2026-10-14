/**
 * risk_checker.js - Payment Risk Evaluation & Simulated Payment Blocking
 */

let currentEvaluation = null;

function fillRiskForm(upi, name, phone, amount, note, url = '') {
  document.getElementById('risk-receiver-upi').value = upi || '';
  document.getElementById('risk-receiver-name').value = name || '';
  document.getElementById('risk-receiver-phone').value = phone || '';
  document.getElementById('risk-amount').value = amount || '';
  document.getElementById('risk-note').value = note || '';
  document.getElementById('risk-url').value = url || '';
}

async function handleCheckRisk(event) {
  event.preventDefault();
  const btn = document.getElementById('btn-check-risk');
  const upi = document.getElementById('risk-receiver-upi').value.trim();
  const name = document.getElementById('risk-receiver-name').value.trim();
  const phone = document.getElementById('risk-receiver-phone').value.trim();
  const amount = parseFloat(document.getElementById('risk-amount').value) || 0;
  const note = document.getElementById('risk-note').value.trim();
  const url = document.getElementById('risk-url').value.trim();

  if (!upi) {
    showToast('Please enter a receiver UPI ID', 'warning');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '⏳ Analyzing Patterns & Risk Database...';

  try {
    const res = await fetch('/api/payments/check-risk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        receiver_upi_id: upi,
        receiver_name: name,
        phone: phone,
        amount: amount,
        note: note,
        url: url
      })
    });

    const data = await res.json();
    btn.disabled = false;
    btn.innerHTML = '🔍 Check Payment Risk Now';

    if (!data.success) {
      showToast(data.message || 'Error evaluating risk', 'error');
      return;
    }

    currentEvaluation = data.evaluation;
    renderRiskEvaluation(data.evaluation, amount, note);
    showToast(`Evaluation complete: ${data.evaluation.risk_level}`, data.evaluation.risk_level === 'HIGH RISK' ? 'error' : (data.evaluation.risk_level === 'MEDIUM RISK' ? 'warning' : 'success'));

  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = '🔍 Check Payment Risk Now';
    showToast('Network error while checking risk: ' + err.message, 'error');
  }
}

function renderRiskEvaluation(evalData, amount, note) {
  const container = document.getElementById('risk-result-container');
  const card = document.getElementById('risk-card');
  const badge = document.getElementById('risk-level-badge');
  const title = document.getElementById('risk-title');
  const info = document.getElementById('risk-receiver-info');
  const scoreVal = document.getElementById('risk-score-val');
  const bar = document.getElementById('risk-progress-bar');
  const aiBox = document.getElementById('ai-nlp-details');
  const reasonsList = document.getElementById('risk-reasons-list');
  const actionArea = document.getElementById('payment-action-area');

  container.style.display = 'block';

  // Card classes
  card.className = 'risk-result-card';
  const level = evalData.risk_level;
  const score = evalData.risk_score;

  scoreVal.textContent = score;
  bar.style.width = `${score}%`;

  if (level === 'HIGH RISK') {
    card.classList.add('high');
    badge.className = 'badge badge-high';
    badge.textContent = 'HIGH RISK: SEVERE FRAUD INDICATORS';
    title.textContent = 'Payment Risk: Critical Threat Detected';
    title.style.color = '#f87171';
    bar.style.backgroundColor = '#ef4444';
  } else if (level === 'MEDIUM RISK') {
    card.classList.add('med');
    badge.className = 'badge badge-med';
    badge.textContent = 'MEDIUM RISK: CAUTION ADVISED';
    title.textContent = 'Payment Risk: Suspicious Activity Detected';
    title.style.color = '#fbbf24';
    bar.style.backgroundColor = '#f59e0b';
  } else {
    card.classList.add('low');
    badge.className = 'badge badge-low';
    badge.textContent = 'LOW RISK: NO SIGNIFICANT THREATS';
    title.textContent = 'Payment Risk: Verified Safe';
    title.style.color = '#34d399';
    bar.style.backgroundColor = '#10b981';
  }

  info.textContent = `Receiver: ${evalData.receiver_upi_id} (${evalData.receiver_name})`;

  // AI NLP Details
  const ai = evalData.ai_analysis || {};
  let aiHtml = `<div>Detected Scam Pattern: <strong>${ai.detected_category || 'General / Non-Scam'}</strong> (Confidence: <strong>${ai.confidence_score || 0}%</strong>)</div>`;
  if (ai.urgency_score > 0) {
    aiHtml += `<div style="margin-top:3px; color:#fbbf24;">Urgency Intensity Score: <strong>${ai.urgency_score}/100</strong> (detected time-pressure cues)</div>`;
  }
  if (ai.rat_tool_detected) {
    aiHtml += `<div style="margin-top:3px; color:#f87171; font-weight:600;">⚠️ Critical: Remote Access Software (AnyDesk/QuickSupport/APK) pattern identified!</div>`;
  }
  aiBox.innerHTML = aiHtml;

  // Reasons
  reasonsList.innerHTML = (evalData.reasons || []).map(r => `<li>${r}</li>`).join('');

  // Payment Action Simulation Area
  if (level === 'HIGH RISK') {
    actionArea.innerHTML = `
      <div style="background:rgba(239, 68, 68, 0.15); border:1px solid rgba(239,68,68,0.4); border-radius:10px; padding:16px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
          <span style="font-size:1.6rem;">🛑</span>
          <div>
            <h4 style="color:#f87171; margin:0; font-size:1.05rem;">PAYMENT BLOCKED BY AI SECURITY ENGINE</h4>
            <p style="color:var(--text-secondary); font-size:0.84rem; margin-top:2px;">
              Server-side security rules strictly prohibit transfers to confirmed fraudulent recipients.
            </p>
          </div>
        </div>
        <div style="margin-top:12px; display:flex; gap:10px;">
          <button class="btn btn-danger" onclick="attemptBlockedPayment()" style="flex:1;">
            Attempt Payment (Will Be Blocked by Backend)
          </button>
          <button class="btn btn-secondary" onclick="prefillFraudReport('${evalData.receiver_upi_id}', '${evalData.receiver_name}')">
            🚨 Report Receiver Now
          </button>
        </div>
      </div>
    `;
  } else if (level === 'MEDIUM RISK') {
    actionArea.innerHTML = `
      <div style="background:rgba(245, 158, 11, 0.12); border:1px solid rgba(245, 158, 11, 0.35); border-radius:10px; padding:16px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
          <span style="font-size:1.6rem;">⚠️</span>
          <div>
            <h4 style="color:#fbbf24; margin:0; font-size:1.05rem;">Caution: Potential Risk Indicators</h4>
            <p style="color:var(--text-secondary); font-size:0.84rem; margin-top:2px;">
              This recipient has either unverified reports or suspicious handle patterns. Verify the person's identity before transferring money.
            </p>
          </div>
        </div>
        <div style="margin-bottom:12px;">
          <label style="font-size:0.86rem; color:var(--text-primary); cursor:pointer; display:flex; align-items:center; gap:8px;">
            <input type="checkbox" id="medium-risk-ack" style="width:16px; height:16px; accent-color:#f59e0b;">
            I acknowledge the warning and want to proceed with simulated payment of ₹${Number(amount).toLocaleString()}
          </label>
        </div>
        <div style="display:flex; gap:10px;">
          <button class="btn btn-primary" onclick="executeSimulatedPayment(true)">
            Proceed with Caution (Simulate Payment)
          </button>
          <button class="btn btn-secondary" onclick="prefillFraudReport('${evalData.receiver_upi_id}', '${evalData.receiver_name}')">
            Cancel & Report Fraud
          </button>
        </div>
      </div>
    `;
  } else {
    // LOW RISK
    actionArea.innerHTML = `
      <div style="background:rgba(16, 185, 129, 0.1); border:1px solid rgba(16, 185, 129, 0.3); border-radius:10px; padding:16px; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <h4 style="color:#34d399; margin:0; font-size:1.05rem;">Safe Receiver Profile</h4>
          <p style="color:var(--text-secondary); font-size:0.84rem; margin-top:2px;">
            No known fraud reports found. You can proceed with the simulated transaction safely.
          </p>
        </div>
        <button class="btn btn-success" onclick="executeSimulatedPayment(false)">
          💳 Pay ₹${Number(amount).toLocaleString()} (Simulate)
        </button>
      </div>
    `;
  }

  // Scroll to results smoothly
  container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Executes or Attempts simulated payment through the backend API
async function executeSimulatedPayment(isMediumRiskConfirmed = false) {
  if (!currentEvaluation) return;

  const upi = currentEvaluation.receiver_upi_id;
  const name = currentEvaluation.receiver_name;
  const amount = parseFloat(document.getElementById('risk-amount').value) || 0;
  const note = document.getElementById('risk-note').value.trim();

  let confirmed = false;
  if (isMediumRiskConfirmed) {
    const ackBox = document.getElementById('medium-risk-ack');
    if (!ackBox || !ackBox.checked) {
      showToast('Please check the confirmation checkbox before proceeding.', 'warning');
      return;
    }
    confirmed = true;
  }

  showToast('Connecting to payment gateway simulation...', 'info', 2000);

  try {
    const res = await fetch('/api/payments/pay', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        receiver_upi_id: upi,
        receiver_name: name,
        amount: amount,
        note: note,
        confirmed_warning: confirmed
      })
    });

    const data = await res.json();

    if (res.status === 403 || data.status === 'BLOCKED') {
      // Backend blocked the payment!
      showToast('PAYMENT BLOCKED BY SERVER SECURITY RULES!', 'error', 6000);
      alert(`🛑 BACKEND SECURITY ENFORCEMENT:\n\nPayment to ${upi} was REJECTED by the backend server.\n\nBlock Reference: ${data.block_ref}\nReason: ${data.message}\nRisk Score: ${data.risk_score}/100`);
      loadDashboardStats();
      return;
    }

    if (!data.success) {
      showToast(data.message || 'Payment execution failed', 'error');
      return;
    }

    // Success Modal
    const receiptBox = document.getElementById('receipt-details');
    receiptBox.innerHTML = `
      <div><strong>Transaction Ref:</strong> <span style="font-family:'JetBrains Mono',monospace; color:#818cf8;">${data.transaction_ref}</span></div>
      <div><strong>Recipient UPI:</strong> <span>${data.receiver_upi_id}</span></div>
      <div><strong>Recipient Name:</strong> <span>${data.receiver_name}</span></div>
      <div><strong>Amount Paid:</strong> <span style="color:#34d399; font-weight:700;">₹${Number(data.amount).toLocaleString()}</span></div>
      <div><strong>Security Risk Level:</strong> <span class="badge ${data.risk_level === 'LOW RISK' ? 'badge-low' : 'badge-med'}">${data.risk_level} (${data.risk_score}/100)</span></div>
      <div><strong>Timestamp:</strong> <span>${data.timestamp}</span></div>
      <div><strong>Status:</strong> <span style="color:#34d399; font-weight:600;">COMPLETED (SIMULATED)</span></div>
    `;

    openModal('receipt-modal');
    loadDashboardStats();

  } catch (err) {
    showToast('Payment submission error: ' + err.message, 'error');
  }
}

// Specifically test that backend rejects high risk payment when forced
async function attemptBlockedPayment() {
  executeSimulatedPayment(false);
}

// Prefill fraud report form from check results
function prefillFraudReport(upi, name) {
  navigateTo('report-fraud');
  document.getElementById('report-upi').value = upi || '';
  document.getElementById('report-name').value = name || '';
  if (currentEvaluation && currentEvaluation.ai_analysis) {
    const cat = currentEvaluation.ai_analysis.detected_category;
    const catSelect = document.getElementById('report-category');
    for (let opt of catSelect.options) {
      if (opt.value === cat) {
        catSelect.value = cat;
        break;
      }
    }
  }
  showToast('Receiver details populated in Fraud Reporting form', 'info');
}
