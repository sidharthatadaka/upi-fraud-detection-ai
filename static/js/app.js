/**
 * app.js - Core UI Navigation, Real-time Dashboard Polling & Utilities
 */

// Toast Notification Manager
function showToast(message, type = 'info', duration = 4000) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  let icon = 'ℹ️';
  if (type === 'success') icon = '✅';
  else if (type === 'error') icon = '❌';
  else if (type === 'warning') icon = '⚠️';

  toast.innerHTML = `<span style="font-size:1.1rem;">${icon}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('toast-fadeout');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// Modal Helpers
function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add('active');
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.remove('active');
}

// Tab Navigation
function navigateTo(tabName) {
  // Update nav links
  document.querySelectorAll('.nav-link').forEach(link => {
    if (link.getAttribute('data-tab') === tabName) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });

  // Switch visible section
  document.querySelectorAll('.page-section').forEach(sec => {
    sec.classList.remove('active');
  });

  const target = document.getElementById(`page-${tabName}`);
  if (target) {
    target.classList.add('active');
  }

  // Hook tab-specific load actions
  if (tabName === 'dashboard') {
    loadDashboardStats();
  } else if (tabName === 'history') {
    loadReportHistory();
  } else if (tabName === 'admin') {
    checkAdminAuth();
  }

  // Update hash safely
  window.location.hash = tabName;
}

// Load Dashboard Data & Statistics
async function loadDashboardStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    if (!data.success) return;

    const stats = data.stats;
    document.getElementById('stat-total-reports').textContent = stats.total_fraud_reports || 0;
    document.getElementById('stat-suspicious-receivers').textContent = stats.suspicious_receivers || 0;
    document.getElementById('stat-high-risk').textContent = stats.high_risk_receivers || 0;
    document.getElementById('stat-payments-checked').textContent = stats.payments_checked || 0;
    document.getElementById('stat-blocked-payments').textContent = stats.blocked_payment_attempts || 0;

    // Database Engine Badge
    const engineBadge = document.getElementById('db-engine-badge');
    if (engineBadge && data.db_engine) {
      engineBadge.textContent = `DB: ${data.db_engine}`;
    }

    // Populate Recent Reports
    const recentBody = document.getElementById('dashboard-recent-reports-body');
    if (recentBody) {
      if (!data.recent_reports || data.recent_reports.length === 0) {
        recentBody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No reports registered yet</td></tr>';
      } else {
        recentBody.innerHTML = data.recent_reports.map(r => `
          <tr>
            <td><strong style="font-family:'JetBrains Mono',monospace; font-size:0.8rem;">${r.report_ref}</strong></td>
            <td><span style="color:#a5b4fc;">${r.receiver_upi_id}</span></td>
            <td><span style="font-size:0.82rem;">${r.category}</span></td>
            <td><strong>₹${Number(r.amount_lost || 0).toLocaleString()}</strong></td>
            <td>${getStatusBadge(r.status)}</td>
          </tr>
        `).join('');
      }
    }

    // Populate Recent Blocked Payments
    const blockedBody = document.getElementById('dashboard-recent-blocked-body');
    if (blockedBody) {
      if (!data.recent_blocked || data.recent_blocked.length === 0) {
        blockedBody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-muted);">No payments blocked yet</td></tr>';
      } else {
        blockedBody.innerHTML = data.recent_blocked.map(b => `
          <tr>
            <td><strong style="font-family:'JetBrains Mono',monospace; font-size:0.8rem; color:#f87171;">${b.block_ref}</strong></td>
            <td><span>${b.receiver_upi_id}</span></td>
            <td><strong style="color:#f87171;">₹${Number(b.amount || 0).toLocaleString()}</strong></td>
            <td><span style="font-size:0.78rem; color:var(--text-secondary);">${b.block_reason || 'High Risk'}</span></td>
          </tr>
        `).join('');
      }
    }

    // Populate Category Distribution
    const catList = document.getElementById('category-distribution-list');
    if (catList && data.categories) {
      const total = stats.total_fraud_reports || 1;
      catList.innerHTML = data.categories.map(c => {
        const pct = Math.round((c.count / total) * 100);
        return `
          <div>
            <div style="display:flex; justify-content:space-between; font-size:0.82rem; margin-bottom:4px;">
              <span>${c.category}</span>
              <span style="font-weight:600;">${c.count} (${pct}%)</span>
            </div>
            <div style="height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
              <div style="width:${pct}%; height:100%; background:var(--primary-gradient); border-radius:3px;"></div>
            </div>
          </div>
        `;
      }).join('');
    }

  } catch (err) {
    console.error('Error fetching dashboard stats:', err);
  }
}

// Badge Generators
function getStatusBadge(status) {
  if (status === 'verified') {
    return '<span class="badge badge-high">Verified Fraud</span>';
  } else if (status === 'under_review') {
    return '<span class="badge badge-med">Under Review</span>';
  } else if (status === 'rejected') {
    return '<span class="badge badge-low">Rejected</span>';
  }
  return '<span class="badge badge-info">Pending</span>';
}

function getRiskBadge(level) {
  if (level === 'HIGH RISK') {
    return '<span class="badge badge-high">HIGH RISK</span>';
  } else if (level === 'MEDIUM RISK') {
    return '<span class="badge badge-med">MEDIUM RISK</span>';
  }
  return '<span class="badge badge-low">LOW RISK</span>';
}

// Test Scenario Presets
function loadTestScenario(type) {
  navigateTo('check-payment');
  if (type === 'high_kyc') {
    fillRiskForm('sbi.kyc.verification@okhdfcbank', 'SBI Helpdesk Official', '+91 98231 44521', 25000, 'Urgent KYC verification fee download AnyDesk app to unfreeze account');
  } else if (type === 'high_elec') {
    fillRiskForm('electricity.bill.desk@paytm', 'Power Recovery Officer', '+91 87654 32190', 1450, 'Electricity bill unpaid power cut at 9:30 PM pay bill now');
  } else if (type === 'medium_crypto') {
    fillRiskForm('crypto.gainz@okicici', 'Binance P2P Rapid', '+91 95432 10987', 5000, 'Crypto arbitrage task deposit');
  } else if (type === 'low_safe') {
    fillRiskForm('rahul.sharma@okaxis', 'Rahul Sharma', '+91 98765 43210', 500, 'Dinner bill split with friend');
  }
  setTimeout(() => {
    document.getElementById('risk-check-form').dispatchEvent(new Event('submit'));
  }, 100);
}

// Global Auto-Refresh Polling (Runs every 5 seconds)
let refreshInterval = null;
function startAutoRefresh() {
  if (refreshInterval) clearInterval(refreshInterval);
  refreshInterval = setInterval(() => {
    const activeSection = document.querySelector('.page-section.active');
    if (activeSection && activeSection.id === 'page-dashboard') {
      loadDashboardStats();
    }
  }, 5000);
}

// Initialization on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  // Read hash or default to dashboard
  const hash = window.location.hash.replace('#', '') || 'dashboard';
  navigateTo(hash);
  loadDashboardStats();
  startAutoRefresh();
});
