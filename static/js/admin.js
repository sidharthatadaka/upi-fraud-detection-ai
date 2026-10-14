/**
 * admin.js - Administrative Authentication, Moderation & Audit Controls
 */

async function checkAdminAuth() {
  try {
    const res = await fetch('/api/admin/me');
    const data = await res.json();

    const loginView = document.getElementById('admin-login-view');
    const authView = document.getElementById('admin-authenticated-view');

    if (data.success && data.logged_in) {
      loginView.style.display = 'none';
      authView.style.display = 'block';
      document.getElementById('admin-user-display').textContent = data.user.username;
      loadAdminDashboardData();
    } else {
      loginView.style.display = 'block';
      authView.style.display = 'none';
    }
  } catch (err) {
    console.error('Error checking admin auth:', err);
  }
}

async function handleAdminLogin(event) {
  event.preventDefault();
  const username = document.getElementById('admin-user-input').value.trim();
  const password = document.getElementById('admin-pass-input').value.trim();

  try {
    const res = await fetch('/api/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });

    const data = await res.json();
    if (!data.success) {
      showToast(data.message || 'Login failed', 'error');
      return;
    }

    showToast('Admin authenticated successfully', 'success');
    checkAdminAuth();

  } catch (err) {
    showToast('Admin login error: ' + err.message, 'error');
  }
}

async function handleAdminLogout() {
  try {
    await fetch('/api/admin/logout', { method: 'POST' });
    showToast('Logged out of Admin session', 'info');
    checkAdminAuth();
  } catch (err) {
    console.error(err);
  }
}

async function loadAdminDashboardData() {
  loadAdminModerationQueue();
  loadAdminThresholds();
  loadAdminAuditLogs();
}

async function loadAdminThresholds() {
  try {
    const res = await fetch('/api/admin/settings');
    const data = await res.json();
    if (data.success) {
      document.getElementById('threshold-low-input').value = data.threshold_low;
      document.getElementById('threshold-high-input').value = data.threshold_high;
    }
  } catch (err) {
    console.error(err);
  }
}

async function handleSaveThresholds(event) {
  event.preventDefault();
  const low = parseInt(document.getElementById('threshold-low-input').value);
  const high = parseInt(document.getElementById('threshold-high-input').value);

  if (low >= high) {
    showToast('Low threshold must be lower than High threshold', 'warning');
    return;
  }

  try {
    const res = await fetch('/api/admin/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ threshold_low: low, threshold_high: high })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message, 'success');
      loadDashboardStats();
    } else {
      showToast(data.message || 'Failed to update thresholds', 'error');
    }
  } catch (err) {
    showToast('Error saving thresholds: ' + err.message, 'error');
  }
}

async function loadAdminModerationQueue() {
  const tbody = document.getElementById('admin-moderation-body');
  try {
    const res = await fetch('/api/reports?limit=50');
    const data = await res.json();

    if (!data.success || !data.reports || data.reports.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No reports to moderate</td></tr>';
      return;
    }

    tbody.innerHTML = data.reports.map(r => `
      <tr>
        <td><strong style="font-family:'JetBrains Mono',monospace; font-size:0.8rem; color:#818cf8;">${r.report_ref}</strong></td>
        <td><span style="color:#a5b4fc;">${r.receiver_upi_id}</span></td>
        <td><span style="font-size:0.82rem;">${r.category}</span></td>
        <td><span style="font-size:0.8rem; color:var(--text-secondary); max-width:200px; display:inline-block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${r.description}</span></td>
        <td>${getStatusBadge(r.status)}</td>
        <td>
          <div style="display:flex; gap:6px;">
            <button class="btn btn-sm btn-danger" onclick="moderateReport(${r.id}, 'verified')" title="Mark as Verified Fraudster">
              Verify
            </button>
            <button class="btn btn-sm btn-secondary" onclick="moderateReport(${r.id}, 'under_review')" title="Flag Under Review">
              Review
            </button>
            <button class="btn btn-sm btn-success" onclick="moderateReport(${r.id}, 'rejected')" title="Dismiss as False Report">
              Reject
            </button>
          </div>
        </td>
      </tr>
    `).join('');

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:#f87171;">Error loading queue: ${err.message}</td></tr>`;
  }
}

async function moderateReport(reportId, newStatus) {
  try {
    const res = await fetch(`/api/admin/reports/${reportId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    const data = await res.json();

    if (!data.success) {
      showToast(data.message || 'Moderation action failed', 'error');
      return;
    }

    const rec = data.receiver || {};
    showToast(`Report updated! Receiver ${rec.upi_id || ''} risk recalculated to: ${rec.risk_score || 0}/100 (${rec.risk_level || ''})`, 'success', 5000);

    loadAdminModerationQueue();
    loadDashboardStats();

  } catch (err) {
    showToast('Failed to update report status: ' + err.message, 'error');
  }
}

async function loadAdminAuditLogs() {
  const tbody = document.getElementById('admin-audit-body');
  try {
    const res = await fetch('/api/admin/logs');
    const data = await res.json();

    if (!data.success) return;

    let rows = [];

    (data.blocked_payments || []).forEach(b => {
      rows.push({
        type: '<span class="badge badge-high">BLOCKED</span>',
        ref: b.block_ref,
        upi: b.receiver_upi_id,
        amount: b.amount,
        info: b.block_reason,
        time: b.attempted_at,
        timestamp: new Date(b.attempted_at || 0).getTime()
      });
    });

    (data.simulated_transactions || []).forEach(t => {
      rows.push({
        type: '<span class="badge badge-low">PAID</span>',
        ref: t.transaction_ref,
        upi: t.receiver_upi_id,
        amount: t.amount,
        info: `Risk Score: ${t.risk_score}/100 (${t.risk_level})`,
        time: t.created_at,
        timestamp: new Date(t.created_at || 0).getTime()
      });
    });

    // Sort by timestamp desc
    rows.sort((a, b) => b.timestamp - a.timestamp);

    if (rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No logs recorded yet</td></tr>';
      return;
    }

    tbody.innerHTML = rows.slice(0, 30).map(r => `
      <tr>
        <td>${r.type}</td>
        <td><strong style="font-family:'JetBrains Mono',monospace; font-size:0.8rem;">${r.ref}</strong></td>
        <td><span>${r.upi}</span></td>
        <td><strong>₹${Number(r.amount || 0).toLocaleString()}</strong></td>
        <td><span style="font-size:0.8rem; color:var(--text-secondary);">${r.info}</span></td>
        <td><span style="font-size:0.75rem; color:var(--text-muted);">${r.time}</span></td>
      </tr>
    `).join('');

  } catch (err) {
    console.error('Audit logs error:', err);
  }
}
