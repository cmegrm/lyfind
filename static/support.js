/* The CSA conversation lives outside the workspace so dashboard refreshes preserve drafts. */
(() => {
  'use strict';

  const icons = {
    chat: '<path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.6 8.6 0 0 1-7.7 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.6a8.4 8.4 0 0 1-.9-3.8 8.6 8.6 0 0 1 4.7-7.7 8.4 8.4 0 0 1 3.8-.9h.5a8.6 8.6 0 0 1 8 8v.5Z"/><path d="M8.5 11.5h7"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    back: '<path d="M19 12H5m7-7-7 7 7 7"/>',
    refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 11-1l3 6M4 12l3 6a7 7 0 0 0 11-1"/>',
  };
  const timeFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' });

  function icon(name) {
    return `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">${icons[name]}</svg>`;
  }

  function node(tag, className = '', text = '') {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text) element.textContent = text;
    return element;
  }

  function iconButton(name, label) {
    const button = node('button', 'reunite-support-icon');
    button.type = 'button';
    button.setAttribute('aria-label', label);
    button.title = label;
    button.innerHTML = icon(name);
    return button;
  }

  const launcher = node('button', 'reunite-support-launcher');
  launcher.type = 'button';
  launcher.hidden = true;
  launcher.innerHTML = `${icon('chat')}<span>Contact CSA</span>`;
  launcher.setAttribute('aria-haspopup', 'dialog');
  launcher.setAttribute('aria-controls', 'reunite-support');

  const dialog = node('dialog', 'reunite-support-dialog');
  dialog.id = 'reunite-support';
  dialog.setAttribute('aria-labelledby', 'reunite-support-title');
  const layout = node('div', 'reunite-support-layout');
  const header = node('header', 'reunite-support-header');
  const headingGroup = node('div', 'reunite-support-heading');
  const kicker = node('span', 'reunite-support-kicker', 'LYFIND / SUPPORT');
  const heading = node('h2', '', 'Contact CSA');
  heading.id = 'reunite-support-title';
  heading.tabIndex = -1;
  headingGroup.append(kicker, heading);
  const close = iconButton('close', 'Close CSA support');
  const refresh = iconButton('refresh', 'Refresh CSA messages');
  const headerActions = node('div', 'reunite-support-header-actions');
  headerActions.append(refresh, close);
  header.append(headingGroup, headerActions);
  const content = node('div', 'reunite-support-content');
  layout.append(header, content);
  dialog.append(layout);
  document.body.append(launcher, dialog);

  let viewer = null;
  let csrf = '';
  let selectedThread = null;
  let activeRequest = null;
  let nextRefresh = null;
  let currentList = null;
  let currentStatus = null;
  let lastListKey = null;

  function staff() {
    return viewer?.role === 'admin';
  }

  function label() {
    return staff() ? 'CSA inbox' : 'Contact CSA';
  }

  function cancelRequest() {
    activeRequest?.controller.abort();
    activeRequest = null;
  }

  function timeLabel(value) {
    if (!value) return '';
    const iso = value.replace(' ', 'T');
    const time = new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(iso) ? iso : `${iso}Z`);
    return Number.isNaN(time.valueOf()) ? '' : timeFormat.format(time);
  }

  function setStatus(text = '', error = false) {
    if (!currentStatus) return;
    currentStatus.setAttribute('role', error ? 'alert' : 'status');
    currentStatus.setAttribute('aria-live', error ? 'assertive' : 'polite');
    currentStatus.setAttribute('aria-atomic', 'true');
    currentStatus.textContent = text;
    currentStatus.classList.toggle('has-error', error);
  }

  async function request(path, controller, data) {
    const options = { signal: controller.signal, credentials: 'same-origin' };
    if (data) {
      options.method = 'POST';
      options.headers = { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf };
      options.body = JSON.stringify(data);
    }
    let response;
    try {
      response = await fetch(path, options);
    } catch (error) {
      if (error.name === 'AbortError') throw error;
      throw new Error('Could not reach CSA. Check your connection and try again.');
    }
    if (response.status === 401) throw new Error('Your session ended. Sign in again to continue.');
    const result = await response.json().catch(() => null);
    if (!response.ok || !result?.ok) throw new Error(result?.error || 'Could not complete this request. Try again.');
    return result.data;
  }

  function makeComposer() {
    const form = node('form', 'reunite-support-compose');
    const fieldLabel = node('label', 'reunite-support-compose-label', staff() ? 'Write a reply' : 'Your message');
    fieldLabel.htmlFor = 'reunite-support-message';
    const field = node('textarea', 'reunite-support-input');
    field.id = fieldLabel.htmlFor;
    field.required = true;
    field.maxLength = 2000;
    field.rows = 2;
    field.placeholder = staff() ? 'Write your response…' : 'How can CSA help?';
    field.setAttribute('aria-describedby', 'reunite-support-privacy');
    const footer = node('div', 'reunite-support-compose-footer');
    const privacy = node('small', 'reunite-support-note', 'Keep passwords and ID photos out of messages.');
    privacy.id = 'reunite-support-privacy';
    const send = node('button', 'reunite-support-primary', staff() ? 'Send reply' : 'Send');
    send.type = 'submit';
    footer.append(privacy, send);
    form.append(fieldLabel, field, footer);
    form.addEventListener('submit', event => {
      event.preventDefault();
      sendMessage(field, send);
    });
    return form;
  }

  function buildView() {
    cancelRequest();
    content.replaceChildren();
    currentStatus = null;
    currentList = null;
    lastListKey = null;
    const queue = staff() && !selectedThread;
    if (selectedThread) {
      const person = node('div', 'reunite-support-person');
      const back = iconButton('back', 'Back to CSA inbox');
      back.addEventListener('click', () => {
        selectedThread = null;
        buildView();
        heading.focus();
      });
      const identity = node('div', 'reunite-support-person-name');
      const contact = selectedThread.guest_contact_email;
      identity.append(node('strong', '', selectedThread.name), node('small', '', contact ? `${contact} (unverified)` : selectedThread.email || 'Guest visit'));
      person.append(back, identity);
      content.append(person);
    } else {
      content.append(node('p', 'reunite-support-intro', queue
        ? 'Open a conversation to read and reply.'
        : 'Send a private message to CSA. Replies appear here.'));
    }

    currentStatus = node('div', 'reunite-support-status');
    currentStatus.setAttribute('role', 'status');
    currentList = node('div', 'reunite-support-list');
    currentList.tabIndex = 0;
    currentList.setAttribute('role', 'region');
    currentList.setAttribute('aria-label', queue ? 'Support conversations' : 'Conversation messages');
    content.append(currentList, currentStatus);
    if (!queue) content.append(makeComposer());
    refreshMessages();
  }

  function renderQueue(threads) {
    const focusId = document.activeElement?.dataset.supportThread;
    const fragment = document.createDocumentFragment();
    if (!threads.length) fragment.append(node('p', 'reunite-support-empty', 'No messages yet. New conversations will appear here.'));
    for (const thread of threads) {
      const button = node('button', 'reunite-support-thread');
      button.type = 'button';
      button.dataset.supportThread = thread.user_id;
      const row = node('div', 'reunite-support-thread-heading');
      row.append(node('strong', '', thread.name), node('small', '', thread.needs_reply ? 'Needs reply' : 'Replied'));
      const preview = node('p', 'reunite-support-preview', thread.last_message);
      const when = timeLabel(thread.last_at);
      button.append(row, preview, node('small', 'reunite-support-note', when));
      if (thread.needs_reply) button.classList.add('needs-reply');
      button.addEventListener('click', () => {
        selectedThread = thread;
        buildView();
        heading.focus();
      });
      fragment.append(button);
    }
    currentList.replaceChildren(fragment);
    if (focusId) {
      const focused = Array.from(currentList.children).find(button => button.dataset.supportThread === focusId);
      (focused || currentList).focus({ preventScroll: true });
    }
  }

  function renderThread(messages, forceBottom = false) {
    const distanceFromBottom = currentList.scrollHeight - currentList.scrollTop - currentList.clientHeight;
    const fragment = document.createDocumentFragment();
    if (!messages.length) fragment.append(node('p', 'reunite-support-empty', 'No messages yet. Send a message to start the conversation.'));
    for (const message of messages) {
      const fromCsa = message.author_role === 'admin';
      const own = fromCsa === staff();
      const messageElement = node('article', `reunite-support-message${own ? ' is-own' : ''}`);
      const sender = own ? (staff() ? 'CSA team' : 'You') : (staff() ? selectedThread?.name || 'Account holder' : 'CSA team');
      messageElement.append(
        node('strong', 'reunite-support-sender', sender),
        node('p', 'reunite-support-bubble', message.body),
        node('small', 'reunite-support-note', timeLabel(message.created_at)),
      );
      fragment.append(messageElement);
    }
    currentList.replaceChildren(fragment);
    if (forceBottom || distanceFromBottom < 72) currentList.scrollTop = currentList.scrollHeight;
  }

  async function refreshMessages(quiet = false) {
    if (!viewer || !dialog.open || activeRequest) return;
    const queue = staff() && !selectedThread;
    const path = selectedThread ? `/api/support/threads/${encodeURIComponent(selectedThread.user_id)}` : '/api/support';
    const task = { kind: 'refresh', controller: new AbortController() };
    activeRequest = task;
    if (!quiet) setStatus('Loading messages…');
    try {
      const result = await request(path, task.controller);
      if (activeRequest !== task) return;
      const items = queue ? result.threads : result.messages;
      const key = JSON.stringify(items);
      if (key !== lastListKey) {
        if (queue) renderQueue(items);
        else renderThread(items);
        if (quiet && lastListKey !== null) setStatus(queue ? 'Inbox updated.' : 'Conversation updated.');
        lastListKey = key;
      }
      if (!quiet) setStatus('');
    } catch (error) {
      if (activeRequest === task && error.name !== 'AbortError' && !quiet) setStatus(error.message, true);
    } finally {
      if (activeRequest === task) activeRequest = null;
    }
  }

  async function sendMessage(field, button) {
    if (!viewer || activeRequest?.kind === 'send') return;
    const message = field.value.trim();
    if (!message) {
      setStatus('Enter a message before sending.', true);
      field.focus();
      return;
    }
    cancelRequest();
    const task = { kind: 'send', controller: new AbortController() };
    activeRequest = task;
    const data = selectedThread ? { user_id: selectedThread.user_id, message } : { message };
    button.disabled = true;
    field.readOnly = true;
    setStatus('Sending…');
    try {
      const result = await request('/api/support/send', task.controller, data);
      if (activeRequest !== task) return;
      field.value = '';
      renderThread(result.messages, true);
      lastListKey = JSON.stringify(result.messages);
      setStatus(staff() ? 'Reply sent.' : 'Message sent to CSA.');
      field.focus({ preventScroll: true });
    } catch (error) {
      if (activeRequest === task && error.name !== 'AbortError') setStatus(error.message, true);
    } finally {
      if (activeRequest === task) activeRequest = null;
      button.disabled = false;
      field.readOnly = false;
    }
  }

  launcher.addEventListener('click', () => {
    if (!viewer || dialog.open) return;
    heading.textContent = label();
    selectedThread = null;
    dialog.showModal();
    buildView();
    heading.focus();
    nextRefresh = setInterval(() => {
      if (!document.hidden) refreshMessages(true);
    }, 18000);
  });
  close.addEventListener('click', () => dialog.close());
  refresh.addEventListener('click', () => refreshMessages());
  dialog.addEventListener('close', () => {
    clearInterval(nextRefresh);
    cancelRequest();
    selectedThread = null;
    content.replaceChildren();
    if (viewer) launcher.focus({ preventScroll: true });
  });

  window.ReuniteSupport = {
    update(user, token) {
      if (user?.id !== viewer?.id || user?.role !== viewer?.role) {
        if (dialog.open) dialog.close();
        cancelRequest();
      }
      viewer = user || null;
      csrf = token || '';
      launcher.querySelector('span').textContent = label();
      launcher.hidden = !viewer;
    },
  };
})();
