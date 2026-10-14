/**
 * history_receiver.js - Fraud Report Registry, Search, and Receiver Risk Intelligence
 */

let historySearchTimer = null;

function debounceHistorySearch() {
  clearTimeout(historySearchTimer);
  historySearchTimer = setTimeout(loadReportHistory, 300);
}

async function loadReportHistory() {
  const search = document.getElementById('history-search').value.trim();
  const category = document.getElementById('history-category-filter').value;
  const status = document.getElementById('history-status-filter').value;
  const tbody = document.getElementById('history-table-body');

  tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">Loading fraud records...</td></tr>';

  try {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (category) params.append('category', category);
    if (status) params.append('status', status);

    const res = await fetch(`/api/reports?${params.toString()}`);
    const data = await res.json();

    if (!data.success || !data.reports || data.reports.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No matching reports found</td></tr>';
      return;
    }

    tbody.innerHTML = data.reports.map(r => `
      <tr>
        <td><strong style="font-family:'JetBrains Mono',monospace; font-size:0.8rem; color:#818cf8;">${r.report_ref}</strong></td>
        <td>
          <a href="javascript:void(0)" onclick="quickLookupReceiver('${r.receiver_upi_id}')" style="color:#a5b4fc; text-decoration:none; font-weight:500;">
            ${r.receiver_upi_id}
          </a>
        </td>
        <td><span style="font-size:0.84rem;">${r.category}</span></td>
        <td><strong>₹${Number(r.amount_lost || 0).toLocaleString()}</strong></td>
        <td>
          <span style="font-size:0.75rem; color:var(--text-secondary);">${r.ai_category_detected || 'Analyzed'}</span>
          <span class="badge badge-info" style="font-size:0.68rem; margin-left:4px;">${r.ai_confidence || 0}%</span>
        </td>
        <td>${getStatusBadge(r.status)}</td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="viewReportDetails(${r.id})">Details</button>
        </td>
      </tr>
    `).join('');

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:#f87171;">Failed to load records: ${err.message}</td></tr>`;
  }
}

async function viewReportDetails(reportId) {
  try {
    const res = await fetch(`/api/reports/${reportId}`);
    const data = await res.json();
    if (!data.success) {
      showToast('Error loading report', 'error');
      return;
    }

    const rep = data.report;
    const rec = data.receiver || {};
    const content = document.getElementById('modal-report-content');

    let evidenceHtml = '<p style="color:var(--text-muted); font-size:0.84rem;">No evidence file attached</p>';
    if (rep.evidence_filename) {
      evidenceHtml = `
        <div style="margin-top:8px;">
          <a href="/uploads/${rep.evidence_filename}" target="_blank" class="btn btn-secondary btn-sm" style="display:inline-flex; gap:6px;">
            📎 View / Download Evidence File (${rep.evidence_filename})
          </a>
        </div>
      `;
    }

    content.innerHTML = `
      <div style="margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <strong style="font-family:'JetBrains Mono',monospace; color:#818cf8; font-size:1.1rem;">${rep.report_ref}</strong>
          <span style="margin-left:8px;">${getStatusBadge(rep.status)}</span>
        </div>
        <span style="font-size:0.8rem; color:var(--text-secondary);">${rep.created_at}</span>
      </div>

      <div style="background:rgba(15,23,42,0.8); border:1px solid var(--border-color); border-radius:8px; padding:12px; margin-bottom:14px; font-size:0.88rem; line-height:1.7;">
        <div><strong>Reported UPI:</strong> <span style="color:#a5b4fc;">${rep.receiver_upi_id}</span></div>
        <div><strong>Reported Name:</strong> ${rep.receiver_name || 'N/A'}</div>
        <div><strong>Phone:</strong> ${rep.receiver_phone || 'N/A'}</div>
        <div><strong>Scam Category:</strong> ${rep.category}</div>
        <div><strong>Amount Defrauded:</strong> ₹${Number(rep.amount_lost || 0).toLocaleString()}</div>
        ${rep.suspicious_url ? `<div><strong>Suspicious Link:</strong> <a href="${rep.suspicious_url}" target="_blank" style="color:#38bdf8;">${rep.suspicious_url}</a></div>` : ''}
      </div>

      <div style="margin-bottom:14px;">
        <h4 style="font-size:0.88rem; color:var(--text-secondary); margin-bottom:4px;">Incident Narrative:</h4>
        <div style="background:rgba(255,255,255,0.03); padding:10px; border-radius:6px; font-size:0.86rem; border:1px solid var(--border-color); line-height:1.5;">
          ${rep.description}
        </div>
      </div>

      <div style="background:rgba(99,102,241,0.08); border:1px solid rgba(99,102,241,0.25); border-radius:8px; padding:10px; margin-bottom:14px; font-size:0.82rem;">
        <div style="font-weight:600; color:#a5b4fc; margin-bottom:4px;">🤖 AI Pattern Diagnostics:</div>
        <div>AI Detected Category: <strong>${rep.ai_category_detected || 'N/A'}</strong> (Confidence: <strong>${rep.ai_confidence || 0}%</strong>)</div>
        <div>Urgency Threat Score: <strong>${rep.ai_urgency_score || 0}/100</strong></div>
      </div>

      <div style="margin-bottom:14px;">
        <h4 style="font-size:0.88rem; color:var(--text-secondary); margin-bottom:4px;">Evidence Attachment:</h4>
        ${evidenceHtml}
      </div>

      <div style="display:flex; justify-content:flex-end; gap:10px;">
        <button class="btn btn-secondary btn-sm" onclick="quickLookupReceiver('${rep.receiver_upi_id}'); closeModal('report-modal');">
          Inspect Receiver Profile
        </button>
      </div>
    `;

    openModal('report-modal');

  } catch (err) {
    showToast('Failed to view report: ' + err.message, 'error');
  }
}

// Receiver Risk Intelligence Lookup
async function handleReceiverLookup(event) {
  if (event) event.preventDefault();
  const query = document.getElementById('lookup-input').value.trim();
  if (!query) {
    showToast('Please enter a UPI ID or phone number', 'warning');
    return;
  }
  executeReceiverLookup(query);
}

function quickLookupReceiver(upi) {
  navigateTo('receiver-lookup');
  document.getElementById('lookup-input').value = upi;
  executeReceiverLookup(upi);
}

async function executeReceiverLookup(query) {
  const container = document.getElementById('lookup-result-container');
  const profileCard = document.getElementById('lookup-profile-card');
  const reportsBody = document.getElementById('lookup-reports-body');
  const blockedBody = document.getElementById('lookup-blocked-body');

  try {
    const res = await fetch(`/api/receivers/lookup?query=${encodeURIComponent(query)}`);
    const data = await res.json();

    if (!data.success) {
      showToast(data.message || 'Lookup failed', 'error');
      return;
    }

    container.style.display = 'block';
    const rec = data.receiver || {};
    const score = rec.risk_score || 0;
    const level = rec.risk_level || 'LOW RISK';

    // Profile Card Rendering
    profileCard.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:16px;">
        <div>
          <div style="display:flex; align-items:center; gap:8px;">
            <h2 style="font-size:1.4rem; color:white;">${rec.upi_id}</h2>
            ${rec.is_verified_fraud ? '<span class="badge badge-high">⚠️ CONFIRMED FRAUDSTER</span>' : (data.is_known ? '<span class="badge badge-med">Under Monitoring</span>' : '<span class="badge badge-low">Unreported</span>')}
          </div>
          <p style="color:var(--text-secondary); font-size:0.88rem; margin-top:4px;">
            Name: <strong>${rec.name || 'Not provided'}</strong> | Phone: <strong>${rec.phone || 'N/A'}</strong>
          </p>
          ${rec.flagged_urls ? `<p style="font-size:0.8rem; color:#f87171; margin-top:4px;">Flagged URLs: ${rec.flagged_urls}</p>` : ''}
        </div>

        <div style="text-align:right;">
          <div class="score-num" style="color: ${score >= 70 ? '#ef4444' : (score >= 35 ? '#f59e0b' : '#10b981')};">
            ${score}<span style="font-size:1rem; color:var(--text-secondary);">/100</span>
          </div>
          <div>${getRiskBadge(level)}</div>
        </div>
      </div>

      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:12px; margin-top:1.2rem; padding-top:1.2rem; border-top:1px solid var(--border-color);">
        <div style="background:rgba(255,255,255,0.02); padding:10px; border-radius:8px;">
          <div style="font-size:1.1rem; font-weight:700;">${rec.total_reports || 0}</div>
          <div style="font-size:0.75rem; color:var(--text-secondary);">Total Complaints</div>
        </div>
        <div style="background:rgba(239,68,68,0.06); padding:10px; border-radius:8px;">
          <div style="font-size:1.1rem; font-weight:700; color:#f87171;">${rec.verified_reports || 0}</div>
          <div style="font-size:0.75rem; color:var(--text-secondary);">Verified Frauds</div>
        </div>
        <div style="background:rgba(255,255,255,0.02); padding:10px; border-radius:8px;">
          <div style="font-size:1.1rem; font-weight:700; color:#34d399;">${rec.rejected_reports || 0}</div>
          <div style="font-size:0.75rem; color:var(--text-secondary);">Dismissed Reports</div>
        </div>
        <div style="background:rgba(220,38,38,0.08); padding:10px; border-radius:8px;">
          <div style="font-size:1.1rem; font-weight:700; color:#f87171;">${(data.blocked_payments || []).length}</div>
          <div style="font-size:0.75rem; color:var(--text-secondary);">Blocked Payments</div>
        </div>
      </div>
    `;

    // Linked Reports
    if (!data.reports || data.reports.length === 0) {
      reportsBody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-muted);">No reports linked to this UPI ID</td></tr>';
    } else {
      reportsBody.innerHTML = data.reports.map(r => `
        <tr>
          <td><strong style="font-family:'JetBrains Mono',monospace; font-size:0.8rem; color:#818cf8;">${r.report_ref}</strong></td>
          <td>${r.category}</td>
          <td>₹${Number(r.amount_lost || 0).toLocaleString()}</td>
          <td>${getStatusBadge(r.status)}</td>
        </tr>
      `).join('');
    }

    // Linked Blocked Attempts
    if (!data.blocked_payments || data.blocked_payments.length === 0) {
      blockedBody.innerHTML = '<tr><td colspan="3" style="text-align:center; color:var(--text-muted);">No blocked transactions for this receiver</td></tr>';
    } else {
      blockedBody.innerHTML = data.blocked_payments.map(b => `
        <tr>
          <td><strong style="font-family:'JetBrains Mono',monospace; font-size:0.8rem; color:#f87171;">${b.block_ref}</strong></td>
          <td>₹${Number(b.amount || 0).toLocaleString()}</td>
          <td style="font-size:0.78rem; color:var(--text-secondary);">${b.block_reason}</td>
        </tr>
      `).join('');
    }

    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  } catch (err) {
    showToast('Receiver search error: ' + err.message, 'error');
  }
}
