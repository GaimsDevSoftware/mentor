/**
 * Aegis Approval UI — handles high-risk action prompts
 *
 * When Aegis detects a risky tool call in "ask" mode, shows a prominent
 * notification with blinking window borders and approval buttons.
 */

// Track pending approvals by session
const _aegisApprovals = new Map();

/**
 * Show a prominent Aegis approval dialog with blinking borders
 */
export function showAegisApproval(toolCall, result) {
  const approvalId = `aegis-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

  // Create overlay
  const overlay = document.createElement('div');
  overlay.id = approvalId;
  overlay.className = 'aegis-approval-overlay';
  overlay.innerHTML = `
    <div class="aegis-approval-dialog">
      <div class="aegis-approval-header">
        <span class="aegis-approval-icon">⚠️</span>
        <h2>High-Risk Action Detected</h2>
        <button class="aegis-close" aria-label="Close">×</button>
      </div>

      <div class="aegis-approval-content">
        <div class="aegis-tool-info">
          <span class="aegis-tool-label">Tool:</span>
          <code class="aegis-tool-name">${escapeHtml(result.tool)}</code>
        </div>

        <div class="aegis-score-bar">
          <div class="aegis-score-label">Risk Score</div>
          <div class="aegis-score-display">
            <div class="aegis-score-meter" style="width: ${result.aegis_score}%"></div>
            <span class="aegis-score-text">${result.aegis_score}/100</span>
          </div>
        </div>

        ${result.aegis_content ? `
        <div class="aegis-command">
          <div class="aegis-command-label">What will run</div>
          <pre class="aegis-command-pre">${escapeHtml(result.aegis_content)}</pre>
        </div>` : ''}

        <div class="aegis-reasons">
          <div class="aegis-reasons-label">Why this is risky</div>
          ${renderAegisReasons(result)}
        </div>

        <div class="aegis-warning-message">
          ${escapeHtml(result.message)}
        </div>
      </div>

      <div class="aegis-approval-actions">
        <button class="aegis-btn aegis-btn-deny" data-action="deny">
          Deny & Stop
        </button>
        <button class="aegis-btn aegis-btn-approve" data-action="approve">
          Approve & Continue
        </button>
      </div>
    </div>
  `;

  // Add blinking border animation
  const style = document.createElement('style');
  style.textContent = `
    @keyframes aegis-blink {
      0%, 100% { border-color: #ff453a; box-shadow: 0 0 20px rgba(255, 69, 58, 0.6); }
      50% { border-color: transparent; box-shadow: 0 0 30px rgba(255, 69, 58, 0.3); }
    }

    .aegis-approval-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.7);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
      animation: aegis-blink 0.8s infinite;
    }

    .aegis-approval-dialog {
      background: white;
      border: 3px solid #ff453a;
      border-radius: 12px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4), 0 0 40px rgba(255, 69, 58, 0.3);
      max-width: 500px;
      width: 90%;
      max-height: 80vh;
      overflow-y: auto;
      animation: aegis-blink 0.8s infinite;
    }

    .aegis-approval-header {
      background: linear-gradient(135deg, #ff453a 0%, #ff6b5a 100%);
      color: white;
      padding: 20px;
      border-radius: 9px 9px 0 0;
      display: flex;
      align-items: center;
      gap: 12px;
      position: relative;
    }

    .aegis-approval-icon {
      font-size: 28px;
      animation: pulse 2s infinite;
    }

    .aegis-approval-header h2 {
      margin: 0;
      flex: 1;
      font-size: 20px;
      font-weight: 600;
    }

    .aegis-close {
      background: none;
      border: none;
      color: white;
      font-size: 28px;
      cursor: pointer;
      padding: 0;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      opacity: 0.8;
      transition: opacity 0.2s;
    }

    .aegis-close:hover {
      opacity: 1;
    }

    .aegis-approval-content {
      padding: 24px;
      font-family: system-ui, -apple-system, sans-serif;
    }

    .aegis-tool-info {
      margin-bottom: 16px;
      display: flex;
      gap: 8px;
      align-items: center;
    }

    .aegis-tool-label {
      font-weight: 600;
      color: #333;
    }

    .aegis-tool-name {
      background: #f5f5f5;
      padding: 4px 8px;
      border-radius: 4px;
      font-family: 'Menlo', 'Monaco', monospace;
      font-size: 13px;
      color: #d70015;
    }

    .aegis-score-bar {
      margin-bottom: 20px;
    }

    .aegis-score-label {
      font-weight: 600;
      color: #333;
      margin-bottom: 8px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .aegis-score-display {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .aegis-score-meter {
      flex: 1;
      height: 8px;
      background: #e5e5ea;
      border-radius: 4px;
      background: linear-gradient(90deg, #34c759 0%, #ff9500 50%, #ff453a 100%);
      position: relative;
      overflow: hidden;
    }

    .aegis-score-text {
      font-weight: 600;
      color: #ff453a;
      min-width: 50px;
      text-align: right;
      font-size: 14px;
    }

    .aegis-command {
      margin-bottom: 16px;
    }

    .aegis-command-label {
      font-weight: 600;
      color: #333;
      margin-bottom: 8px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .aegis-command-pre {
      margin: 0;
      background: #1e1e1e;
      color: #f5f5f5;
      padding: 12px;
      border-radius: 6px;
      font-family: 'Menlo', 'Monaco', monospace;
      font-size: 12px;
      line-height: 1.5;
      max-height: 200px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .aegis-reasons {
      margin-bottom: 16px;
    }

    .aegis-reasons-label {
      font-weight: 600;
      color: #333;
      margin-bottom: 8px;
      font-size: 13px;
    }

    .aegis-reasons-rich li {
      font-family: system-ui, -apple-system, sans-serif !important;
      line-height: 1.5;
      margin-bottom: 8px;
    }

    .aegis-reason-label {
      display: inline-block;
      font-weight: 700;
      color: #b3261e;
      margin-right: 6px;
      text-transform: capitalize;
    }

    .aegis-reason-label::after {
      content: '—';
      margin-left: 6px;
      color: #aaa;
      font-weight: 400;
    }

    .aegis-reasons-list {
      list-style: none;
      padding: 0;
      margin: 0;
      background: #fff3cd;
      border-left: 3px solid #ffc107;
      padding: 12px;
      border-radius: 4px;
    }

    .aegis-reasons-list li {
      color: #664d03;
      font-size: 13px;
      margin-bottom: 4px;
      font-family: 'Menlo', 'Monaco', monospace;
    }

    .aegis-reasons-list li:last-child {
      margin-bottom: 0;
    }

    .aegis-warning-message {
      background: #fff3cd;
      border: 1px solid #ffecb5;
      border-radius: 6px;
      padding: 12px;
      color: #664d03;
      font-size: 13px;
      line-height: 1.5;
      white-space: pre-wrap;
    }

    .aegis-approval-actions {
      display: flex;
      gap: 12px;
      padding: 16px 24px 24px;
      border-top: 1px solid #e5e5ea;
      background: #f9f9f9;
      border-radius: 0 0 9px 9px;
    }

    .aegis-btn {
      flex: 1;
      padding: 12px 16px;
      border: none;
      border-radius: 6px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      font-size: 14px;
    }

    .aegis-btn-deny {
      background: #f2f2f7;
      color: #333;
    }

    .aegis-btn-deny:hover {
      background: #e5e5ea;
    }

    .aegis-btn-approve {
      background: #ff453a;
      color: white;
    }

    .aegis-btn-approve:hover {
      background: #ff3b2d;
      box-shadow: 0 4px 12px rgba(255, 69, 58, 0.3);
    }

    @keyframes pulse {
      0%, 100% { transform: scale(1); }
      50% { transform: scale(1.2); }
    }

    @media (prefers-reduced-motion: reduce) {
      .aegis-approval-icon,
      .aegis-approval-overlay,
      .aegis-approval-dialog {
        animation: none !important;
      }
    }
  `;

  document.head.appendChild(style);
  document.body.appendChild(overlay);

  // Store approval state
  _aegisApprovals.set(approvalId, {
    toolCall,
    result,
    status: 'pending',
    timestamp: Date.now(),
  });

  // Handle buttons
  const denyBtn = overlay.querySelector('[data-action="deny"]');
  const approveBtn = overlay.querySelector('[data-action="approve"]');
  const closeBtn = overlay.querySelector('.aegis-close');

  denyBtn.addEventListener('click', () => {
    handleAegisApproval(approvalId, false);
  });

  approveBtn.addEventListener('click', () => {
    handleAegisApproval(approvalId, true);
  });

  closeBtn.addEventListener('click', () => {
    handleAegisApproval(approvalId, false);
  });

  // Focus approve button for keyboard users
  approveBtn.focus();

  // Escape key to deny
  const escapeHandler = (e) => {
    if (e.key === 'Escape') {
      handleAegisApproval(approvalId, false);
    }
  };
  document.addEventListener('keydown', escapeHandler, { once: true });

  return approvalId;
}

/**
 * Show a non-blocking Aegis warning toast.
 *
 * Used by "warn" mode (the Cowork "run it anyway, but tell me" setting): the
 * tool call has ALREADY executed, so this does not block or ask — it slides in
 * a prominent red banner that auto-dismisses, listing why the call was flagged.
 */
export function showAegisWarning(data) {
  _ensureAegisWarnStyle();

  // One stacking container, top-right, holds all active warn toasts.
  let host = document.getElementById('aegis-warn-host');
  if (!host) {
    host = document.createElement('div');
    host.id = 'aegis-warn-host';
    host.className = 'aegis-warn-host';
    document.body.appendChild(host);
  }

  const score = (data.aegis_score != null) ? data.aegis_score : '?';
  const reasons = Array.isArray(data.aegis_reasons) ? data.aegis_reasons
                : (Array.isArray(data.reasons) ? data.reasons.filter(r => String(r).startsWith('+')) : []);
  const msg = data.aegis_message || data.message ||
              `Aegis flagged this ${data.tool || 'tool'} call but ran it anyway.`;

  const toast = document.createElement('div');
  toast.className = 'aegis-warn-toast';
  toast.innerHTML = `
    <div class="aegis-warn-bar"></div>
    <div class="aegis-warn-body">
      <div class="aegis-warn-top">
        <span class="aegis-warn-icon">⚠️</span>
        <span class="aegis-warn-title">Ran anyway — flagged by Aegis</span>
        <span class="aegis-warn-score">${escapeHtml(String(score))}/100</span>
        <button class="aegis-warn-close" aria-label="Dismiss">×</button>
      </div>
      <div class="aegis-warn-tool">${escapeHtml(data.tool || '')}</div>
      ${reasons.length ? `<ul class="aegis-warn-reasons">${
        reasons.map(r => `<li>${escapeHtml(String(r))}</li>`).join('')
      }</ul>` : ''}
      <div class="aegis-warn-msg">${escapeHtml(msg)}</div>
    </div>
  `;

  const dismiss = () => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    setTimeout(() => toast.remove(), 250);
  };
  toast.querySelector('.aegis-warn-close').addEventListener('click', dismiss);
  host.appendChild(toast);

  // Auto-dismiss after a while (respect reduced-motion users: stay a bit longer)
  const prefersReduced = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  setTimeout(dismiss, prefersReduced ? 12000 : 9000);

  return toast;
}

function _ensureAegisWarnStyle() {
  if (document.getElementById('aegis-warn-style')) return;
  const style = document.createElement('style');
  style.id = 'aegis-warn-style';
  style.textContent = `
    .aegis-warn-host {
      position: fixed; top: 16px; right: 16px; z-index: 10001;
      display: flex; flex-direction: column; gap: 10px;
      max-width: 360px; pointer-events: none;
    }
    .aegis-warn-toast {
      pointer-events: auto; display: flex; overflow: hidden;
      background: #fff; border: 1px solid #ffd0c9;
      border-radius: 10px;
      box-shadow: 0 8px 28px rgba(255,69,58,0.28), 0 2px 8px rgba(0,0,0,0.15);
      font-family: system-ui, -apple-system, sans-serif;
      opacity: 1; transform: translateX(0);
      transition: opacity .25s ease, transform .25s ease;
      animation: aegis-warn-in .28s ease;
    }
    @keyframes aegis-warn-in {
      from { opacity: 0; transform: translateX(24px); }
      to   { opacity: 1; transform: translateX(0); }
    }
    .aegis-warn-bar {
      width: 5px; flex: 0 0 5px;
      background: linear-gradient(180deg,#ff453a 0%,#ff6b5a 100%);
      animation: aegis-warn-pulse 1.1s ease-in-out infinite;
    }
    @keyframes aegis-warn-pulse { 0%,100%{opacity:1;} 50%{opacity:.45;} }
    .aegis-warn-body { padding: 10px 12px; flex: 1; min-width: 0; }
    .aegis-warn-top { display: flex; align-items: center; gap: 8px; }
    .aegis-warn-icon { font-size: 16px; }
    .aegis-warn-title { font-weight: 700; color: #b3261e; font-size: 13px; flex: 1; }
    .aegis-warn-score {
      font-weight: 700; color: #ff453a; font-size: 12px;
      font-family: 'Menlo','Monaco',monospace;
    }
    .aegis-warn-close {
      background: none; border: none; color: #888; font-size: 20px;
      line-height: 1; cursor: pointer; padding: 0 2px; opacity: .7;
    }
    .aegis-warn-close:hover { opacity: 1; }
    .aegis-warn-tool {
      margin-top: 4px; font-family: 'Menlo','Monaco',monospace;
      font-size: 12px; color: #d70015;
    }
    .aegis-warn-reasons {
      list-style: none; margin: 8px 0 0; padding: 8px 10px;
      background: #fff3cd; border-left: 3px solid #ffc107; border-radius: 4px;
    }
    .aegis-warn-reasons li {
      color: #664d03; font-size: 12px; margin: 0 0 3px;
      font-family: 'Menlo','Monaco',monospace;
    }
    .aegis-warn-reasons li:last-child { margin-bottom: 0; }
    .aegis-warn-msg { margin-top: 8px; font-size: 12px; color: #444; line-height: 1.45; }
    @media (prefers-reduced-motion: reduce) {
      .aegis-warn-toast, .aegis-warn-bar { animation: none !important; }
    }
  `;
  document.head.appendChild(style);
}

/**
 * Handle approval/denial decision
 */
export function handleAegisApproval(approvalId, approved) {
  const approval = _aegisApprovals.get(approvalId);
  if (!approval) return;

  approval.status = approved ? 'approved' : 'denied';
  const dialog = document.getElementById(approvalId);

  if (dialog) {
    dialog.style.opacity = '0';
    dialog.style.transition = 'opacity 0.3s';
    setTimeout(() => dialog.remove(), 300);
  }

  // Dispatch event so chat.js can continue or stop execution
  const event = new CustomEvent('aegis-decision', {
    detail: { approvalId, approved, toolCall: approval.toolCall }
  });
  document.dispatchEvent(event);
}

/**
 * Render the "Why this is risky" list.
 *
 * Prefers the backend's context-specific `aegis_explanations` (each tied to the
 * exact text matched in THIS call); falls back to the terse `+NN reason` codes
 * for older payloads that don't carry explanations.
 */
function renderAegisReasons(result) {
  const expl = Array.isArray(result.aegis_explanations) ? result.aegis_explanations : [];
  if (expl.length) {
    return `<ul class="aegis-reasons-list aegis-reasons-rich">${
      expl.map(e => `<li><span class="aegis-reason-label">${escapeHtml(e.label || '')}</span>${escapeHtml(e.detail || '')}</li>`).join('')
    }</ul>`;
  }
  const codes = Array.isArray(result.reasons)
    ? result.reasons.filter(r => String(r).startsWith('+'))
    : [];
  return `<ul class="aegis-reasons-list">${
    codes.map(r => `<li>${escapeHtml(String(r))}</li>`).join('')
  }</ul>`;
}

/**
 * Simple HTML escaping
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Get approval status
 */
export function getApprovalStatus(approvalId) {
  return _aegisApprovals.get(approvalId)?.status || null;
}

/**
 * Check if approval was given (for async operations)
 */
export function wasApproved(approvalId) {
  return _aegisApprovals.get(approvalId)?.status === 'approved';
}
