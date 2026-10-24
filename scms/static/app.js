let csrfToken = null;
let currentUser = null;
let registering = false;
let currentTrackingPage = 1;
let currentStaffPage = 1;
let sessionEpoch = 0;
const listRequests = {student: 0, staff: 0};
const PAGE_SIZE = 10;

const $ = id => document.getElementById(id);

function showMessage(target, message, kind) {
  const el = $(target);
  if (!el) return;
  el.className = message ? `banner ${kind || ''}` : '';
  el.textContent = message || '';
}

function clearErrors(prefix='error-') {
  document.querySelectorAll(`[id^="${prefix}"]`).forEach(node => {
    node.textContent = '';
  });
  document.querySelectorAll('.has-error').forEach(input => {
    input.classList.remove('has-error');
    input.removeAttribute('aria-invalid');
  });
}

function displayFieldErrors(fields, prefix='error-') {
  if (!fields) return;
  let firstFailedInput = null;
  Object.entries(fields).forEach(([field, message]) => {
    const errorNode = $(`${prefix}${field}`);
    if (errorNode) errorNode.textContent = message;
    const inputNode = $(field);
    if (inputNode) {
      inputNode.classList.add('has-error');
      inputNode.setAttribute('aria-invalid', 'true');
      if (!firstFailedInput) firstFailedInput = inputNode;
    }
  });
  if (firstFailedInput) {
    firstFailedInput.focus();
  }
}

// Clear individual error as user interacts with an input
['university_id', 'password', 'name', 'email', 'category', 'description', 'severity'].forEach(id => {
  const el = $(id);
  if (!el) return;
  const clearCurrent = () => {
    if (el.classList.contains('has-error')) {
      el.classList.remove('has-error');
      el.removeAttribute('aria-invalid');
      const err = $(`error-${id}`);
      if (err) err.textContent = '';
    }
  };
  el.addEventListener('input', clearCurrent);
  el.addEventListener('change', clearCurrent);
});

// Character counter for description
const descInput = $('description');
const charCount = $('char-count');
function updateCharCounter() {
  if (!descInput || !charCount) return;
  const remaining = 1000 - descInput.value.length;
  charCount.textContent = `${remaining.toLocaleString()} characters remaining`;
  charCount.classList.remove('warning', 'danger');
  if (remaining < 50) {
    charCount.classList.add('danger');
  } else if (remaining < 200) {
    charCount.classList.add('warning');
  }
}
if (descInput) {
  descInput.addEventListener('input', updateCharCounter);
}

// Preserve complaint form in sessionStorage so refresh doesn't lose data
function saveComplaintDraft() {
  if (currentUser?.role !== 'Student') return;
  try {
    const draft = {
      category: $('category').value,
      description: $('description').value,
      severity: $('severity').value
    };
    sessionStorage.setItem(`scms_complaint_draft_${currentUser.university_id}`, JSON.stringify(draft));
  } catch (_) {}
}
function loadComplaintDraft() {
  try {
    const raw = sessionStorage.getItem(`scms_complaint_draft_${currentUser.university_id}`);
    if (!raw) return;
    const draft = JSON.parse(raw);
    if (draft.category && !$('category').value) $('category').value = draft.category;
    if (draft.description && !$('description').value) {
      $('description').value = draft.description;
      updateCharCounter();
    }
    if (draft.severity && !$('severity').value) $('severity').value = draft.severity;
  } catch (_) {}
}
function clearComplaintDraft() {
  try { sessionStorage.removeItem(`scms_complaint_draft_${currentUser?.university_id}`); } catch (_) {}
}
['category', 'description', 'severity'].forEach(id => {
  const el = $(id);
  if (el) el.addEventListener('input', saveComplaintDraft);
});

// Password visibility toggle
const togglePwdBtn = $('toggle-pwd');
if (togglePwdBtn) {
  togglePwdBtn.addEventListener('click', () => {
    const pwd = $('password');
    if (pwd.type === 'password') {
      pwd.type = 'text';
      togglePwdBtn.textContent = 'Hide';
      togglePwdBtn.setAttribute('aria-label', 'Hide password');
    } else {
      pwd.type = 'password';
      togglePwdBtn.textContent = 'Show';
      togglePwdBtn.setAttribute('aria-label', 'Show password');
    }
  });
}

async function apiResponse(path, method='GET', data=undefined) {
  const epoch = sessionEpoch;
  const headers = {};
  if (data !== undefined) headers['Content-Type'] = 'application/json';
  if (csrfToken && !['GET','HEAD'].includes(method)) headers['X-CSRF-Token'] = csrfToken;
  const response = await fetch(`/api/v1${path}`, {
    method,
    headers,
    body: data === undefined ? undefined : JSON.stringify(data),
    credentials: 'same-origin'
  });
  const payload = response.status === 204 ? {} : await response.json();
  if (!response.ok) {
    const error = payload.error || {};
    const e = new Error(error.message || 'The request could not be completed.');
    e.fields = error.fields || {};
    e.code = error.code || 'UNKNOWN_ERROR';
    e.status = response.status;
    if (response.status === 401 && path !== '/session' && epoch === sessionEpoch) {
      currentUser = null;
      setAuthenticated(false);
      showMessage('global-message', 'Your session has expired. Please sign in again.', 'failure');
      refreshSession();
    }
    throw e;
  }
  return payload;
}

async function api(path, method='GET', data=undefined) {
  return (await apiResponse(path, method, data)).data;
}

function setAuthenticated(authenticated, role='Student', universityId='') {
  sessionEpoch += 1;
  currentTrackingPage = currentStaffPage = 1;
  $('complaints-list').replaceChildren();
  $('staff-queue-list').replaceChildren();
  $('sla-results').replaceChildren();
  $('tracking-pagination').hidden = $('staff-pagination').hidden = true;
  $('tracking-loading').hidden = $('staff-loading').hidden = true;
  $('status-filter').value = $('staff-status-filter').value = '';
  $('sla-card').hidden = !(authenticated && currentUser?.can_review_sla);
  $('sla-summary').textContent = 'Run a check to see the current threshold and overdue complaints.';
  $('check-overdue').disabled = false;
  showMessage('sla-message', '');
  $('auth-card').hidden = authenticated;
  $('app-nav').hidden = !authenticated;
  $('complaint-submit').disabled = false;
  $('complaint-submit').textContent = 'Submit complaint';

  if (authenticated) {
    $('user-display').textContent = universityId || 'User';
    $('role-display').textContent = role;

    if (role === 'Student') {
      $('staff-card').hidden = true;
      $('nav-tabs').hidden = false;
      showTab('submit');
      loadComplaintDraft();
      loadStudentComplaints(1);
    } else {
      $('complaint-card').hidden = true;
      $('tracking-card').hidden = true;
      $('nav-tabs').hidden = true;
      $('staff-card').hidden = false;
      $('staff-role-label').textContent = role;
      loadStaffQueue();
    }
  } else {
    $('nav-tabs').hidden = true;
    $('complaint-form').reset();
    updateCharCounter();
    showMessage('submit-message', '');
    $('complaint-card').hidden = true;
    $('tracking-card').hidden = true;
    $('staff-card').hidden = true;
  }
}

function showTab(tab) {
  const isSubmit = tab === 'submit';
  $('tab-submit').classList.toggle('active', isSubmit);
  $('tab-submit').setAttribute('aria-selected', isSubmit);
  $('tab-track').classList.toggle('active', !isSubmit);
  $('tab-track').setAttribute('aria-selected', !isSubmit);

  $('complaint-card').hidden = !isSubmit;
  $('tracking-card').hidden = isSubmit;

  if (!isSubmit) {
    loadStudentComplaints(currentTrackingPage);
  }
}

$('tab-submit').addEventListener('click', () => showTab('submit'));
$('tab-track').addEventListener('click', () => showTab('track'));

function setAuthMode() {
  $('auth-title').textContent = registering ? 'Create student account' : 'Sign in';
  $('auth-help').textContent = registering
    ? 'Register with your University ID, name, email, and password.'
    : 'Use your University ID and password.';
  $('name-wrap').hidden = !registering;
  $('email-wrap').hidden = !registering;
  $('auth-submit').textContent = registering ? 'Register and sign in' : 'Sign in';
  $('toggle-auth').textContent = registering ? 'Back to sign in' : 'Create student account';
  $('password').autocomplete = registering ? 'new-password' : 'current-password';
  clearErrors();
}

async function refreshSession() {
  const epoch = sessionEpoch;
  try {
    const session = await api('/session');
    if (epoch !== sessionEpoch) return;
    csrfToken = session.csrf_token;
    if (session.authenticated) {
      currentUser = session;
      setAuthenticated(true, session.role, session.university_id || `User #${session.user_id}`);
    } else {
      currentUser = null;
      setAuthenticated(false);
    }
  } catch (_) {
    if (epoch === sessionEpoch) showMessage('global-message', 'Unable to connect to the service. Please refresh the page.', 'failure');
  }
}

$('toggle-auth').addEventListener('click', () => {
  registering = !registering;
  setAuthMode();
});

$('auth-form').addEventListener('submit', async event => {
  event.preventDefault();
  clearErrors();
  showMessage('global-message', '');

  const data = {
    university_id: $('university_id').value.trim(),
    password: $('password').value
  };

  const submitBtn = $('auth-submit');
  const originalText = submitBtn.textContent;
  submitBtn.disabled = true;
  submitBtn.textContent = registering ? 'Creating account...' : 'Signing in...';

  try {
    if (registering) {
      data.name = $('name').value.trim();
      data.email = $('email').value.trim();
      await api('/users', 'POST', data);
    }
    const session = await api('/session', 'POST', {
      university_id: data.university_id,
      password: data.password
    });
    csrfToken = session.csrf_token;
    currentUser = session;
    $('auth-form').reset();
    registering = false;
    setAuthMode();

    if (session.role !== 'Student') {
      showMessage('global-message', `Signed in as ${session.role}. Staff interface activated.`, 'info');
      setAuthenticated(true, session.role, data.university_id);
      return;
    }

    setAuthenticated(true, 'Student', data.university_id);
    showMessage('global-message', 'Signed in successfully. Welcome to SCMS!', 'success');
  } catch (error) {
    displayFieldErrors(error.fields);
    showMessage('global-message', error.message, 'failure');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = registering ? originalText : 'Sign in';
  }
});

$('complaint-form').addEventListener('submit', async event => {
  event.preventDefault();
  const epoch = sessionEpoch;
  clearErrors();
  showMessage('submit-message', '');

  const data = {
    category: $('category').value,
    description: $('description').value.trim(),
    severity: $('severity').value
  };

  const button = $('complaint-submit');
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = 'Submitting complaint...';
  const started = performance.now();

  try {
    const result = await api('/complaints', 'POST', data);
    if (epoch !== sessionEpoch) return;
    const elapsed = (performance.now() - started) / 1000;
    showMessage(
      'submit-message',
      `Complaint submitted successfully! Reference ID: #${result.complaint_id}. Confirmation received in ${elapsed.toFixed(3)} seconds.`,
      'success'
    );
    $('complaint-form').reset();
    updateCharCounter();
    clearComplaintDraft();
    loadStudentComplaints(1);
  } catch (error) {
    if (epoch !== sessionEpoch) return;
    displayFieldErrors(error.fields);
    showMessage('submit-message', error.message || 'Please correct the highlighted fields.', 'failure');
  } finally {
    if (epoch === sessionEpoch) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
});

$('clear-complaint').addEventListener('click', () => {
  $('complaint-form').reset();
  clearErrors();
  clearComplaintDraft();
  updateCharCounter();
  showMessage('submit-message', '');
});

$('logout').addEventListener('click', async () => {
  try {
    await api('/session', 'DELETE');
  } catch (error) {
    if (error.status !== 401) {
      showMessage('global-message', 'Could not sign out. Please try again.', 'failure');
      return;
    }
  }
  clearComplaintDraft();
  csrfToken = null;
  currentUser = null;
  $('complaint-form').reset();
  updateCharCounter();
  setAuthenticated(false);
  await refreshSession();
  showMessage('global-message', 'You have been signed out safely.', 'success');
});

// Both dashboards use the same paged, server-scoped endpoint.
const views = {
  student: {list: 'complaints-list', filter: 'status-filter', loading: 'tracking-loading',
    pagination: 'tracking-pagination', previous: 'prev-page', next: 'next-page', indicator: 'page-indicator'},
  staff: {list: 'staff-queue-list', filter: 'staff-status-filter', loading: 'staff-loading',
    pagination: 'staff-pagination', previous: 'staff-prev-page', next: 'staff-next-page', indicator: 'staff-page-indicator'}
};
const loadStudentComplaints = (page=1) => loadQueue('student', page);
const loadStaffQueue = (page=1) => loadQueue('staff', page);

async function loadQueue(view, page) {
  if (!currentUser || (view === 'student') !== (currentUser.role === 'Student')) return;
  const ui = views[view];
  const epoch = sessionEpoch;
  const request = ++listRequests[view];
  const status = $(ui.filter).value;
  $(ui.loading).hidden = false;
  $(ui.previous).disabled = $(ui.next).disabled = true;
  $(ui.list).replaceChildren();
  $(ui.list).setAttribute('aria-busy', 'true');
  try {
    const result = await apiResponse(`/complaints?page=${page}&page_size=${PAGE_SIZE}&status=${encodeURIComponent(status)}`.replace(/&status=$/, ''));
    if (epoch !== sessionEpoch || request !== listRequests[view]) return;
    // A filter or action can remove the last item on the last page.
    const lastPage = Math.max(1, Math.ceil(result.total / PAGE_SIZE));
    if (page > lastPage) return loadQueue(view, lastPage);
    if (view === 'student') {
      currentTrackingPage = page;
      $('complaints-count').textContent = result.total;
      $('complaints-count').hidden = result.total === 0;
    } else currentStaffPage = page;
    $(ui.list).innerHTML = result.data.length ? result.data.map(c => complaintCard(c, view)).join('')
      : '<div class="empty-state"><p>No complaints match this queue and status filter.</p></div>';
    $(ui.pagination).hidden = lastPage <= 1;
    $(ui.previous).disabled = page <= 1;
    $(ui.next).disabled = page >= lastPage;
    $(ui.indicator).textContent = `Page ${page} of ${lastPage} (${result.total} total)`;
  } catch (error) {
    if (epoch !== sessionEpoch || request !== listRequests[view]) return;
    $(ui.pagination).hidden = true;
    $(ui.list).textContent = `Could not load complaints: ${error.message} Use Refresh to try again.`;
  } finally {
    if (epoch === sessionEpoch && request === listRequests[view]) {
      $(ui.loading).hidden = true;
      $(ui.list).setAttribute('aria-busy', 'false');
    }
  }
}

function complaintCard(c, view) {
  const id = `${view}-${c.complaint_id}`;
  return `<article class="complaint-item" id="item-${id}">
    <div class="complaint-item-header">
      <span class="complaint-ref">#${c.complaint_id} — ${escapeHtml(c.category)}</span>
      <div class="complaint-meta">
        <span class="badge badge-sev-${escapeHtml(c.severity)}">Severity: ${escapeHtml(c.severity)}</span>
        <span class="badge badge-status-${escapeHtml(c.status.replace(/\s+/g, ''))}">${escapeHtml(c.status)}</span>
      </div>
    </div>
    <p class="complaint-assigned"><strong>Assigned Handler:</strong> ${escapeHtml(c.assigned_role)}
      &bull; <strong>Submitted:</strong> ${escapeHtml(new Date(c.submitted_at).toLocaleString())}</p>
    <button type="button" class="secondary btn-sm" data-action="details" data-id="${c.complaint_id}"
      data-view="${view}" aria-expanded="false" aria-controls="details-${id}">View Details &amp; Actions</button>
    <div id="details-${id}" hidden style="margin-top:0.65rem;"></div>
  </article>`;
}

for (const [view, ui] of Object.entries(views)) {
  $(ui.previous).addEventListener('click', () => loadQueue(view, (view === 'student' ? currentTrackingPage : currentStaffPage) - 1));
  $(ui.next).addEventListener('click', () => loadQueue(view, (view === 'student' ? currentTrackingPage : currentStaffPage) + 1));
  $(ui.filter).addEventListener('change', () => loadQueue(view, 1));
}
$('refresh-complaints').addEventListener('click', () => loadStudentComplaints(currentTrackingPage));
$('refresh-staff-queue').addEventListener('click', () => loadStaffQueue(currentStaffPage));

async function showDetails(complaintId, view, toggle=true) {
  const box = $(`details-${view}-${complaintId}`);
  if (!box) return;
  const button = box.previousElementSibling;
  if (toggle && !box.hidden) {
    box.hidden = true;
    button.setAttribute('aria-expanded', 'false');
    return;
  }
  box.hidden = false;
  button.setAttribute('aria-expanded', 'true');
  box.textContent = 'Loading details...';
  const epoch = sessionEpoch;
  try {
    const c = await api(`/complaints/${complaintId}`);
    if (epoch !== sessionEpoch || !box.isConnected) return;
    const actions = c.allowed_actions;
    let content = `<div class="complaint-details-box"><strong>Description:</strong>
      <p class="complaint-desc">${escapeHtml(c.description)}</p></div>`;
    for (const [value, label] of [[c.resolution_remarks, 'Resolution Remarks'], [c.rejection_reason, 'Rejection Reason']]) {
      if (value) content += `<div class="complaint-details-box"><strong>${label}:</strong><p>${escapeHtml(value)}</p></div>`;
    }
    if (c.final_review) content += '<p class="hint">Final appeal review at Dean level. No further escalation is available.</p>';
    if (view === 'student' && c.appealed) content += '<p class="hint">Your one permitted appeal has been used.</p>';
    if (actions.includes('appeal')) {
      const guidance = c.current_level === 3
        ? 'This is your one permitted appeal. It remains with the Dean for final review.'
        : 'You may appeal once. The complaint will reopen at the next review level.';
      content += `<p class="hint">${guidance}</p>
        <label for="appeal-just-${complaintId}">Appeal justification (required)</label>
        <textarea id="appeal-just-${complaintId}" maxlength="1000" aria-required="true"></textarea>
        ${actionButton('appeal', 'Submit Appeal', c, view)}`;
    }
    if (actions.includes('resolve') || actions.includes('reject')) {
      content += `<div class="field"><label for="remarks-${complaintId}">Resolution remarks / rejection reason (required for those actions)</label>
        <textarea id="remarks-${complaintId}" maxlength="500"></textarea></div>`;
      for (const [action, label] of [['resolve', 'Resolve'], ['reject', 'Reject'], ['escalate', 'Escalate to next level']]) {
        if (actions.includes(action)) content += actionButton(action, label, c, view);
      }
    }
    if (view === 'student' && c.status === 'Resolved') {
      if (actions.includes('feedback')) {
        content += `<div class="field"><label for="fb-rating-${complaintId}">Feedback rating</label>
          <select id="fb-rating-${complaintId}"><option value="5">5 — Excellent</option><option value="4">4 — Good</option>
          <option value="3">3 — Satisfactory</option><option value="2">2 — Poor</option><option value="1">1 — Very Poor</option></select>
          <label for="fb-comment-${complaintId}">Feedback comments (optional)</label><input id="fb-comment-${complaintId}" maxlength="500"></div>
          ${actionButton('feedback', 'Submit Feedback', c, view)}`;
      } else {
        const feedback = await api(`/complaints/${complaintId}/feedback`);
        content += `<p><strong>Your feedback:</strong> ${feedback.rating}/5 ${escapeHtml(feedback.comment || '')}</p>`;
      }
    }
    if (epoch !== sessionEpoch || !box.isConnected) return;
    box.innerHTML = `${content}<div id="action-msg-${view}-${complaintId}" role="status" aria-live="polite"></div>`;
  } catch (error) {
    if (epoch === sessionEpoch && box.isConnected) box.textContent = error.message;
  }
}

function actionButton(action, label, c, view) {
  return `<button type="button" class="btn-sm" style="margin:0.4rem 0.4rem 0 0;" data-action="${action}"
    data-id="${c.complaint_id}" data-version="${c.version}" data-view="${view}">${label}</button>`;
}

document.addEventListener('click', event => {
  const button = event.target.closest('button[data-action]');
  if (!button || button.disabled) return;
  const id = Number(button.dataset.id);
  if (button.dataset.action === 'details') showDetails(id, button.dataset.view);
  else if (button.dataset.action === 'sla-escalate') escalateOverdue(button, id);
  else submitAction(button, id);
});

async function submitAction(button, id) {
  const {action, view} = button.dataset;
  const message = `action-msg-${view}-${id}`;
  const epoch = sessionEpoch;
  const input = $(action === 'appeal' ? `appeal-just-${id}` : `remarks-${id}`);
  const entered = input?.value || '';
  let data = {expected_version: Number(button.dataset.version)};
  let endpoint = action;
  if (action === 'appeal') { data.justification = entered.trim(); endpoint = 'appeals'; }
  if (action === 'resolve') data.remarks = entered.trim();
  if (action === 'reject') data.reason = entered.trim();
  if (['appeal', 'resolve', 'reject'].includes(action) && !entered.trim()) {
    showMessage(message, action === 'appeal' ? 'Please provide an appeal justification.' : 'Please provide resolution remarks or a rejection reason.', 'failure');
    input.focus();
    return;
  }
  if (action === 'feedback') data = {rating: Number($(`fb-rating-${id}`).value), comment: $(`fb-comment-${id}`).value.trim() || null};
  const box = $(`details-${view}-${id}`);
  const buttons = [...box.querySelectorAll('button')];
  buttons.forEach(b => { b.disabled = true; });
  try {
    const result = await api(`/complaints/${id}/${endpoint}`, 'POST', data);
    if (epoch !== sessionEpoch) return;
    let notice = `Complaint #${id} updated successfully.`;
    if (action === 'appeal') notice = `Appeal for #${id} submitted. Under Appeal Review with ${result.assigned_role}${result.final_review ? ' (final review)' : ''}.`;
    else if (action === 'feedback') notice = `Feedback for #${id} recorded. Thank you.`;
    showMessage('global-message', notice, 'success');
    await loadQueue(view, view === 'student' ? currentTrackingPage : currentStaffPage);
  } catch (error) {
    if (epoch !== sessionEpoch || !box.isConnected) return;
    if (error.status === 409) {
      await showDetails(id, view, false);
      if (epoch !== sessionEpoch) return;
      // Preserve the user's wording while requiring an explicit retry on the new state.
      const replacement = $(action === 'appeal' ? `appeal-just-${id}` : `remarks-${id}`);
      if (replacement) replacement.value = entered;
      showMessage(message, `${error.message} Details refreshed; review the current state before retrying.`, 'failure');
    } else showMessage(message, error.message, 'failure');
  } finally {
    buttons.forEach(b => { b.disabled = false; });
  }
}

async function checkOverdue(clearMessage=true) {
  if (!currentUser?.can_review_sla) return;
  const epoch = sessionEpoch;
  const button = $('check-overdue');
  button.disabled = true;
  $('sla-results').replaceChildren();
  if (clearMessage) showMessage('sla-message', '');
  $('sla-summary').textContent = 'Checking overdue complaints...';
  try {
    const result = await api('/sla/check', 'POST', {});
    if (epoch !== sessionEpoch) return;
    $('sla-summary').textContent = `Checked ${new Date(result.checked_at).toLocaleString()}. SLA threshold: ${result.threshold_days} days. ${result.items.length} overdue complaint(s).`;
    $('sla-results').innerHTML = result.items.map(c => `<article class="complaint-item">
      <strong>Complaint #${c.complaint_id}</strong> — ${escapeHtml(c.status)}
      <p>Current handler: ${escapeHtml(c.current_handler)}<br>Days overdue: ${c.days_overdue}${c.days_overdue === 0 ? ' (less than one full day)' : ''}</p>
      ${c.can_escalate ? actionButton('sla-escalate', 'Escalate to next level', c, 'sla') : '<p class="hint">Dean is the final escalation level.</p>'}
      </article>`).join('') || '<p>No active complaints exceed the current SLA threshold.</p>';
  } catch (error) {
    if (epoch !== sessionEpoch) return;
    $('sla-summary').textContent = 'Check unavailable. Use the check button to try again.';
    showMessage('sla-message', error.message, 'failure');
  } finally {
    if (epoch === sessionEpoch) button.disabled = false;
  }
}

async function escalateOverdue(button, id) {
  const epoch = sessionEpoch;
  $('sla-results').querySelectorAll('button').forEach(b => { b.disabled = true; });
  $('check-overdue').disabled = true;
  try {
    const result = await api(`/sla/complaints/${id}/escalate`, 'POST', {expected_version: Number(button.dataset.version)});
    if (epoch !== sessionEpoch) return;
    showMessage('sla-message', `Complaint #${id} escalated to ${result.assigned_role}.`, 'success');
    await checkOverdue(false);
    await loadStaffQueue(currentStaffPage);
  } catch (error) {
    if (epoch !== sessionEpoch) return;
    showMessage('sla-message', `${error.message} Run a fresh check before trying again.`, 'failure');
    // Never retry an action with a stale version automatically.
    $('sla-results').replaceChildren();
    $('sla-summary').textContent = 'The previous results are out of date. Run another check.';
  } finally {
    if (epoch === sessionEpoch) $('check-overdue').disabled = false;
  }
}
$('check-overdue').addEventListener('click', () => checkOverdue());

function escapeHtml(str) {
  return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

refreshSession();
