// Browser-controller regression checks using a small DOM and API stand-in.
// Backend authorization and persistence are tested against Flask/SQLite separately.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');

test('portal boots, registers, submits, loads full audit and staff notifications', async () => {
  const elements = new Map();
  class Element {
    constructor() {
      this.hidden = false;
      this.value = '';
      this.textContent = '';
      this.listeners = {};
      this.attributes = {};
      this.isConnected = true;
      this.classList = {add() {}, remove() {}, toggle() {}, contains() {return false;}};
      this.previousElementSibling = {setAttribute() {}};
    }
    addEventListener(name, fn) {this.listeners[name] = fn;}
    setAttribute(name, value) {this.attributes[name] = value;}
    removeAttribute(name) {delete this.attributes[name];}
    replaceChildren() {this.innerHTML = '';}
    querySelectorAll() {return [];}
    reset() {}
    focus() {}
  }
  const template = fs.readFileSync('scms/templates/index.html', 'utf8');
  for (const match of template.matchAll(/id="([^"]+)"/g)) elements.set(match[1], new Element());
  const el = id => {
    assert.ok(elements.has(id), `controller requested missing template element: ${id}`);
    return elements.get(id);
  };
  const requests = [];
  let role = 'Student';
  let expired = false;
  const complaint = {complaint_id: 1, category: 'Facilities', description: '<script>unsafe</script>',
    severity: 'Low', status: 'Submitted', current_level: 1, assigned_role: 'Faculty-in-Charge',
    submitted_at: '2026-11-02T10:00:00Z', version: 1, allowed_actions: []};
  const context = vm.createContext({
    document: {getElementById: el, querySelectorAll() {return [];}, addEventListener() {}},
    sessionStorage: {getItem() {return null;}, setItem() {}, removeItem() {}},
    performance, console,
    fetch: async (url, options) => {
      requests.push({url, options});
      let payload;
      if (expired && url.includes('/complaints')) return {
        ok: false, status: 401, json: async () => ({error: {message: 'Please sign in.', code: 'AUTHENTICATION_REQUIRED'}})};
      if (url.endsWith('/session')) payload = {data: options.method === 'POST'
        ? {role, university_id: 'STU001', csrf_token: 'rotated'}
        : {authenticated: false, csrf_token: 'initial'}};
      else if (url.endsWith('/users')) payload = {data: {role: 'Student', user_id: 1}};
      else if (url.endsWith('/complaints') && options.method === 'POST') payload = {data: complaint};
      else if (url.includes('/complaints?')) payload = {data: [complaint], total: 1};
      else if (url.includes('/audit?')) {
        const page = Number(new URL(url, 'http://test').searchParams.get('page'));
        payload = {data: Array.from({length: page === 1 ? 100 : 1}, (_, i) => ({
          action: page === 2 ? 'LAST_EVENT' : 'SUBMIT', actor_id: i + 1,
          previous_status: 'Submitted', new_status: 'Escalated', timestamp: complaint.submitted_at})), total: 101};
      } else if (url.endsWith('/complaints/1')) payload = {data: complaint};
      else if (url.includes('/notifications?')) payload = {data: [{complaint_id: 1,
        event: '<b>SUBMITTED</b>', created_at: complaint.submitted_at}], total: 1};
      else throw new Error(`Unexpected API request ${url}`);
      return {ok: true, status: 200, json: async () => payload};
    }
  });
  const flush = () => new Promise(resolve => setImmediate(resolve));
  vm.runInContext(fs.readFileSync('scms/static/app.js', 'utf8'), context);
  await flush();
  assert.equal(el('auth-card').hidden, false);
  await el('toggle-auth').listeners.click();
  el('university_id').value = 'STU001';
  el('password').value = 'secret';
  el('name').value = 'Student';
  el('email').value = 'student@example.edu';
  await el('auth-form').listeners.submit({preventDefault() {}});
  await flush();
  assert.ok(requests.some(r => r.url.endsWith('/users')));
  assert.equal(el('auth-card').hidden, true);
  assert.equal(el('complaint-card').hidden, false);
  el('category').value = 'Facilities';
  el('description').value = 'Broken fan';
  el('severity').value = 'Low';
  await el('complaint-form').listeners.submit({preventDefault() {}});
  await flush();
  assert.match(el('submit-message').textContent, /Reference ID: #1/);
  const submission = requests.find(r => r.url.endsWith('/complaints') && r.options.method === 'POST');
  assert.equal(submission.options.headers['X-CSRF-Token'], 'rotated');
  elements.set('details-student-1', new Element());
  el('details-student-1').hidden = true;
  await context.showDetails(1, 'student');
  assert.match(el('details-student-1').innerHTML, /LAST_EVENT/);
  assert.match(el('details-student-1').innerHTML, /&lt;script&gt;/);
  assert.doesNotMatch(el('details-student-1').innerHTML, /<script>/);
  // Reuse the same page as a staff account; old private views must clear.
  role = 'Faculty';
  el('university_id').value = 'FAC001';
  await el('auth-form').listeners.submit({preventDefault() {}});
  await flush();
  assert.equal(el('complaint-card').hidden, true);
  assert.equal(el('staff-card').hidden, false);
  assert.match(el('notifications-list').innerHTML, /&lt;b&gt;SUBMITTED&lt;\/b&gt;/);
  expired = true;
  await context.loadQueue('staff', 1);
  await flush();
  assert.equal(el('auth-card').hidden, false);
  assert.equal(el('staff-card').hidden, true);
  assert.equal(el('notifications-list').innerHTML, '');
});
