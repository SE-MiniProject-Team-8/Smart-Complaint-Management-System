```javascript
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

    for (const [value, label] of [
      [c.resolution_remarks, 'Resolution Remarks'],
      [c.rejection_reason, 'Rejection Reason']
    ]) {
      if (value) {
        content += `<div class="complaint-details-box"><strong>${label}:</strong><p>${escapeHtml(value)}</p></div>`;
      }
    }

    if (c.final_review) {
      content += '<p class="hint">Final appeal review at Dean level. No further escalation is available.</p>';
    }

    if (view === 'student' && c.appealed) {
      content += '<p class="hint">Your one permitted appeal has been used.</p>';
    }

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

      for (const [action, label] of [
        ['resolve', 'Resolve'],
        ['reject', 'Reject'],
        ['escalate', 'Escalate to next level']
      ]) {
        if (actions.includes(action)) {
          content += actionButton(action, label, c, view);
        }
      }
    }

    if (view === 'student' && c.status === 'Resolved') {
      if (actions.includes('feedback')) {
        content += `<div class="field"><label for="fb-rating-${complaintId}">Feedback rating</label>
          <select id="fb-rating-${complaintId}">
            <option value="5">5 — Excellent</option>
            <option value="4">4 — Good</option>
            <option value="3">3 — Satisfactory</option>
            <option value="2">2 — Poor</option>
            <option value="1">1 — Very Poor</option>
          </select>
          <label for="fb-comment-${complaintId}">Feedback comments (optional)</label>
          <input id="fb-comment-${complaintId}" maxlength="500"></div>
          ${actionButton('feedback', 'Submit Feedback', c, view)}`;
      } else {
        const feedback = await api(`/complaints/${complaintId}/feedback`);

        content += `<p><strong>Your feedback:</strong> ${feedback.rating}/5 ${escapeHtml(feedback.comment || '')}</p>`;
      }
    }

    if (epoch !== sessionEpoch || !box.isConnected) return;

    // Display the complaint audit history.
    try {
      const auditEntries = await api(
        `/complaints/${complaintId}/audit?page=1&page_size=20`
      );

      content += `<div class="complaint-details-box">
        <h3>Audit History</h3>`;

      if (auditEntries.length === 0) {
        content += '<p class="hint">No audit history available.</p>';
      } else {
        content += '<ol>';

        for (const entry of auditEntries) {
          content += `<li>
            <p><strong>${escapeHtml(entry.action)}</strong></p>
            <p>Actor ID: ${escapeHtml(entry.actor_id)}</p>
            <p>Previous status: ${escapeHtml(entry.previous_status)}</p>
            <p>New status: ${escapeHtml(entry.new_status)}</p>
            <p>Timestamp: ${escapeHtml(new Date(entry.timestamp).toLocaleString())}</p>
          </li>`;
        }

        content += '</ol>';
      }

      content += '</div>';
    } catch (auditError) {
      content += '<p class="hint">Audit history could not be loaded.</p>';
    }

    if (epoch !== sessionEpoch || !box.isConnected) return;

    box.innerHTML = `${content}<div id="action-msg-${view}-${complaintId}" role="status" aria-live="polite"></div>`;
  } catch (error) {
    if (epoch === sessionEpoch && box.isConnected) {
      box.textContent = error.message;
    }
  }
}
```