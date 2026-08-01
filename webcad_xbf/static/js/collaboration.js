const SESSION_KEY = 'cascadecad-collaboration-session-v1';
const ACTIVE_TAB_KEY = 'cascadecad-collaboration-side-tab';
const PRESENCE_INTERVAL_MS = 25000;
const RECONNECT_DELAY_MS = 2500;

function byId(id) { return document.getElementById(id); }
function asArray(value) { return Array.isArray(value) ? value : []; }
function formatTime(timestamp) {
  const value = new Date(Number(timestamp || 0) * 1000);
  return Number.isNaN(value.getTime()) ? '' : value.toLocaleString([], {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'});
}

export function initCollaboration({
  projectId,
  appPath,
  notify,
  getProjectName,
  getSelectedComponentIds,
  focusComponentIds,
  openSidePanel,
}) {
  const state = {
    sessionToken: '',
    user: null,
    membership: null,
    members: [],
    activeUsers: [],
    activeTab: localStorage.getItem(ACTIVE_TAB_KEY) || 'selection',
    sockets: new Map(),
    reconnectTimers: new Map(),
    directUser: null,
    unread: {project: 0, global: 0, direct: 0},
    initialized: false,
  };

  const profileDialog = byId('collaboration-profile-dialog');
  const profileForm = byId('collaboration-profile-form');
  const usernameField = byId('collaboration-username');
  const statusField = byId('collaboration-status');
  const visibilityField = byId('collaboration-project-visibility');
  const categoryField = byId('collaboration-project-category');
  const currentUserCard = byId('current-user-card');
  const membersStatus = byId('project-members-status');
  const membersList = byId('project-members-list');
  const activeUserList = byId('global-user-list');
  const projectChatAccess = byId('project-chat-access');
  const projectChatMessages = byId('project-chat-messages');
  const globalMessages = byId('global-board-messages');
  const directMessages = byId('direct-message-list');
  const globalActiveCount = byId('global-active-count');
  const projectChatCount = byId('project-chat-count');
  const unreadBadge = byId('collaboration-unread');
  const inviteForm = byId('project-invite-form');
  const projectChatForm = byId('project-chat-form');
  const globalBoardForm = byId('global-board-form');
  const directMessageForm = byId('direct-message-form');
  const directTabButton = byId('direct-tab-button');

  function readStoredSession() {
    try {
      const stored = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null');
      if (stored?.sessionToken && stored?.username) return stored;
    } catch { /* start a fresh session */ }
    return null;
  }

  function saveStoredSession() {
    if (!state.user || !state.sessionToken) return;
    localStorage.setItem(SESSION_KEY, JSON.stringify({
      sessionToken: state.sessionToken,
      userId: state.user.id,
      username: state.user.username,
      status: state.user.status,
      projectVisibility: state.user.project_visibility,
      projectCategory: state.user.project_category || 'CAD project',
    }));
  }

  async function jsonRequest(path, options = {}, authenticated = true) {
    const headers = new Headers(options.headers || {});
    if (authenticated && state.sessionToken) headers.set('Authorization', `Bearer ${state.sessionToken}`);
    if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    const response = await fetch(appPath(path), {...options, headers});
    let payload = {};
    try { payload = await response.json(); } catch { /* preserve status error */ }
    if (!response.ok) throw new Error(payload.error || `Collaboration request failed (${response.status})`);
    return payload;
  }

  function websocketUrl(path) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const fullPath = appPath(path);
    return `${protocol}//${location.host}${fullPath}?token=${encodeURIComponent(state.sessionToken)}`;
  }

  function disconnectSocket(key) {
    const socket = state.sockets.get(key);
    state.sockets.delete(key);
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close();
    const timer = state.reconnectTimers.get(key);
    if (timer) clearTimeout(timer);
    state.reconnectTimers.delete(key);
  }

  function connectSocket(key, path, onEvent) {
    disconnectSocket(key);
    if (!state.sessionToken) return;
    const socket = new WebSocket(websocketUrl(path));
    state.sockets.set(key, socket);
    socket.addEventListener('message', event => {
      try { onEvent(JSON.parse(event.data)); } catch { /* ignore damaged event */ }
    });
    socket.addEventListener('close', () => {
      if (!state.sessionToken || state.sockets.get(key) !== socket) return;
      const timer = setTimeout(() => connectSocket(key, path, onEvent), RECONNECT_DELAY_MS);
      state.reconnectTimers.set(key, timer);
    });
  }

  function setUnread(channel, delta) {
    if (state.activeTab === channel || (channel === 'project' && state.activeTab === 'project-chat') || (channel === 'global' && state.activeTab === 'community')) {
      state.unread[channel] = 0;
    } else {
      state.unread[channel] = Math.max(0, Number(state.unread[channel] || 0) + delta);
    }
    const total = Object.values(state.unread).reduce((sum, value) => sum + Number(value || 0), 0);
    if (unreadBadge) {
      unreadBadge.hidden = total === 0;
      unreadBadge.textContent = String(total);
    }
  }

  function showTab(name, {open = true} = {}) {
    const allowed = new Set(['selection', 'users', 'project-chat', 'community', 'direct']);
    const requested = allowed.has(name) ? name : 'selection';
    if (requested === 'direct' && !state.directUser) return;
    state.activeTab = requested;
    localStorage.setItem(ACTIVE_TAB_KEY, requested);
    document.querySelectorAll('[data-side-panel]').forEach(panel => { panel.hidden = panel.dataset.sidePanel !== requested; });
    document.querySelectorAll('[data-side-tab]').forEach(button => button.classList.toggle('active', button.dataset.sideTab === requested));
    const titleMap = {selection: 'Selection / Info', users: 'CascadeCAD Users', 'project-chat': 'Project Chat', community: 'Global Community', direct: 'Direct Message'};
    const title = byId('side-panel-title');
    if (title) title.textContent = titleMap[requested] || 'CascadeCAD';
    if (requested === 'project-chat') setUnread('project', 0);
    if (requested === 'community') setUnread('global', 0);
    if (requested === 'direct') setUnread('direct', 0);
    if (open) openSidePanel?.();
  }

  function showProfileDialog(force = false) {
    const stored = readStoredSession();
    usernameField.value = state.user?.username || stored?.username || '';
    statusField.value = state.user?.status || stored?.status || 'available';
    visibilityField.value = state.user?.project_visibility || stored?.projectVisibility || 'hidden';
    categoryField.value = state.user?.project_category || stored?.projectCategory || 'CAD project';
    if (!profileDialog.open) profileDialog.showModal();
  }

  function renderCurrentUser() {
    if (!currentUserCard) return;
    currentUserCard.replaceChildren();
    if (!state.user) {
      const paragraph = document.createElement('p');
      paragraph.className = 'small-copy';
      paragraph.textContent = 'Choose a CascadeCAD username to join collaboration.';
      currentUserCard.append(paragraph);
      return;
    }
    const header = document.createElement('div');
    header.className = 'user-row-main';
    const identity = document.createElement('strong');
    identity.textContent = state.user.username;
    const badge = document.createElement('span');
    badge.className = `presence-badge status-${state.user.status}`;
    badge.textContent = state.user.status;
    header.append(identity, badge);
    const detail = document.createElement('p');
    detail.className = 'small-copy';
    detail.textContent = `UUID ${state.user.id} · ${state.user.project_label || 'Private project'}`;
    currentUserCard.append(header, detail);
  }

  function createUserRow(user, {member = false} = {}) {
    const row = document.createElement('article');
    row.className = 'user-row';
    const main = document.createElement('div');
    main.className = 'user-row-main';
    const identity = document.createElement('div');
    const name = document.createElement('strong');
    name.textContent = user.username || 'CascadeCAD user';
    const detail = document.createElement('span');
    detail.className = 'small-copy';
    detail.textContent = member ? `${user.role || 'viewer'} · ${user.active ? 'online' : 'offline'}` : `${user.project_label || 'Private project'} · ${user.status || 'available'}`;
    identity.append(name, detail);
    const actions = document.createElement('div');
    actions.className = 'user-row-actions';
    if (state.user && user.id !== state.user.id) {
      const messageButton = document.createElement('button');
      messageButton.type = 'button';
      messageButton.textContent = 'Message';
      messageButton.addEventListener('click', () => openDirectConversation(user));
      actions.append(messageButton);
    }
    main.append(identity, actions);
    row.append(main);
    return row;
  }

  function renderMembers() {
    if (!membersList) return;
    membersList.replaceChildren();
    if (!state.members.length) {
      const empty = document.createElement('p');
      empty.className = 'small-copy';
      empty.textContent = state.membership ? 'No other project members yet.' : 'Project chat access is not active for this username.';
      membersList.append(empty);
    } else {
      state.members.forEach(user => membersList.append(createUserRow(user, {member: true})));
    }
    if (projectChatCount) projectChatCount.textContent = state.membership ? `${state.members.length} member${state.members.length === 1 ? '' : 's'}` : '';
    const canInvite = ['owner', 'admin'].includes(state.membership?.role);
    if (inviteForm) inviteForm.hidden = !canInvite;
    if (membersStatus) membersStatus.textContent = state.membership
      ? `Your role: ${state.membership.role}. Messages are private to this project membership.`
      : 'Private project chat. Ask an Owner or Admin to invite your exact username.';
  }

  function renderActiveUsers() {
    if (!activeUserList) return;
    activeUserList.replaceChildren();
    const others = state.activeUsers.filter(user => user.id !== state.user?.id);
    if (!others.length) {
      const empty = document.createElement('p');
      empty.className = 'small-copy';
      empty.textContent = 'No other visible users are active right now.';
      activeUserList.append(empty);
    } else {
      others.forEach(user => activeUserList.append(createUserRow(user)));
    }
    if (globalActiveCount) globalActiveCount.textContent = `${state.activeUsers.length} active`;
  }

  function messageArticle(message, channel) {
    const article = document.createElement('article');
    article.className = 'chat-message';
    article.dataset.messageId = message.id || '';
    const header = document.createElement('header');
    const author = document.createElement('strong');
    author.textContent = message.username || 'CascadeCAD user';
    const when = document.createElement('time');
    when.textContent = formatTime(message.created_at);
    header.append(author, when);
    const body = document.createElement('p');
    body.textContent = message.text || '';
    article.append(header, body);
    if (asArray(message.component_ids).length) {
      const partButton = document.createElement('button');
      partButton.type = 'button';
      partButton.className = 'linked-parts-button';
      partButton.textContent = `Highlight ${message.component_ids.length} linked part${message.component_ids.length === 1 ? '' : 's'}`;
      partButton.addEventListener('click', () => focusComponentIds?.(message.component_ids));
      article.append(partButton);
    }
    if (channel === 'global' && message.user_id !== state.user?.id) {
      const actions = document.createElement('div');
      actions.className = 'message-actions';
      const report = document.createElement('button');
      report.type = 'button';
      report.textContent = 'Report';
      report.addEventListener('click', () => reportMessage(message));
      const mute = document.createElement('button');
      mute.type = 'button';
      mute.textContent = 'Mute user';
      mute.addEventListener('click', () => blockUser(message.user_id, true));
      actions.append(report, mute);
      article.append(actions);
    }
    return article;
  }

  function renderMessages(container, messages, channel) {
    if (!container) return;
    const wasNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 80;
    container.replaceChildren();
    if (!messages.length) {
      const empty = document.createElement('p');
      empty.className = 'small-copy message-empty';
      empty.textContent = channel === 'global' ? 'The global board is quiet.' : 'No messages yet.';
      container.append(empty);
    } else {
      messages.forEach(message => container.append(messageArticle(message, channel)));
    }
    if (wasNearBottom || !state.initialized) container.scrollTop = container.scrollHeight;
  }

  function appendMessage(container, message, channel) {
    if (!container) return;
    container.querySelector('.message-empty')?.remove();
    if (message.id && container.querySelector(`[data-message-id="${CSS.escape(message.id)}"]`)) return;
    const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
    container.append(messageArticle(message, channel));
    while (container.children.length > 250) container.firstElementChild?.remove();
    if (nearBottom) container.scrollTop = container.scrollHeight;
  }

  async function establishSession(payload) {
    const response = await jsonRequest('/api/collaboration/session', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, false);
    state.sessionToken = response.session_token;
    state.user = response.user;
    saveStoredSession();
    renderCurrentUser();
    await joinProject();
    await Promise.all([loadActiveUsers(), loadGlobalMessages()]);
    connectGlobalSocket();
    startPresenceLoop();
    state.initialized = true;
  }

  async function resumeOrPrompt() {
    const stored = readStoredSession();
    if (!stored) {
      showProfileDialog(true);
      return;
    }
    try {
      await establishSession({
        username: stored.username,
        session_token: stored.sessionToken,
        status: stored.status || 'available',
        project_visibility: stored.projectVisibility || 'hidden',
        project_category: stored.projectCategory || 'CAD project',
      });
    } catch (error) {
      localStorage.removeItem(SESSION_KEY);
      notify(`Collaboration sign-in needs attention: ${error.message}`);
      showProfileDialog(true);
    }
  }

  async function joinProject() {
    try {
      const result = await jsonRequest(`/api/projects/${projectId}/collaboration/join`, {method: 'POST', body: '{}'});
      state.membership = result.membership;
      state.members = asArray(result.members);
      projectChatAccess.textContent = `Private to ${state.members.length} project member${state.members.length === 1 ? '' : 's'} · your role: ${state.membership.role}`;
      projectChatForm.querySelectorAll('textarea,button,input').forEach(element => { element.disabled = false; });
      renderMembers();
      await loadProjectMessages();
      connectProjectSocket();
    } catch (error) {
      state.membership = null;
      state.members = [];
      renderMembers();
      projectChatAccess.textContent = error.message;
      projectChatForm.querySelectorAll('textarea,button,input').forEach(element => { element.disabled = true; });
      renderMessages(projectChatMessages, [], 'project');
    }
  }

  async function loadProjectMessages() {
    if (!state.membership) return;
    const result = await jsonRequest(`/api/projects/${projectId}/collaboration/messages?limit=150`);
    renderMessages(projectChatMessages, asArray(result.messages), 'project');
  }

  async function loadGlobalMessages() {
    if (!state.user) return;
    const result = await jsonRequest('/api/collaboration/global/messages?limit=150');
    renderMessages(globalMessages, asArray(result.messages), 'global');
  }

  async function loadActiveUsers() {
    if (!state.user) return;
    const result = await jsonRequest('/api/collaboration/users');
    state.activeUsers = asArray(result.users);
    renderActiveUsers();
  }

  async function loadMembers() {
    if (!state.membership) return;
    const result = await jsonRequest(`/api/projects/${projectId}/collaboration/users`);
    state.membership = result.membership;
    state.members = asArray(result.members);
    renderMembers();
  }

  function connectGlobalSocket() {
    connectSocket('global', '/ws/collaboration/global', event => {
      if (event.type === 'message' && event.message) {
        appendMessage(globalMessages, event.message, 'global');
        if (event.message.user_id !== state.user?.id) setUnread('global', 1);
      }
      if (event.type === 'presence') loadActiveUsers().catch(() => {});
    });
  }

  function connectProjectSocket() {
    if (!state.membership) return;
    connectSocket('project', `/ws/projects/${projectId}/collaboration`, event => {
      if (event.type === 'message' && event.message) {
        appendMessage(projectChatMessages, event.message, 'project');
        if (event.message.user_id !== state.user?.id) setUnread('project', 1);
      }
      if (event.type === 'members') loadMembers().catch(() => {});
    });
  }

  function connectDirectSocket(user) {
    connectSocket('direct', `/ws/collaboration/direct/${encodeURIComponent(user.id)}`, event => {
      if (event.type === 'message' && event.message) {
        appendMessage(directMessages, event.message, 'direct');
        if (event.message.user_id !== state.user?.id) setUnread('direct', 1);
      }
    });
  }

  let presenceTimer = null;
  function startPresenceLoop() {
    if (presenceTimer) clearInterval(presenceTimer);
    const update = async () => {
      if (!state.user) return;
      try {
        const result = await jsonRequest('/api/collaboration/presence', {
          method: 'POST',
          body: JSON.stringify({project_id: projectId}),
        });
        state.user = result.user;
        saveStoredSession();
        renderCurrentUser();
      } catch { /* reconnect/resume will surface persistent failures */ }
    };
    update();
    presenceTimer = setInterval(update, PRESENCE_INTERVAL_MS);
  }

  async function postProjectMessage() {
    const input = byId('project-chat-input');
    const text = input.value.trim();
    if (!text) return;
    const componentIds = byId('project-chat-link-selection')?.checked ? asArray(getSelectedComponentIds?.()) : [];
    const result = await jsonRequest(`/api/projects/${projectId}/collaboration/messages`, {
      method: 'POST',
      body: JSON.stringify({text, component_ids: componentIds}),
    });
    input.value = '';
    appendMessage(projectChatMessages, result.message, 'project');
  }

  async function postGlobalMessage() {
    const input = byId('global-board-input');
    const text = input.value.trim();
    if (!text) return;
    const result = await jsonRequest('/api/collaboration/global/messages', {
      method: 'POST',
      body: JSON.stringify({text}),
    });
    input.value = '';
    appendMessage(globalMessages, result.message, 'global');
  }

  async function openDirectConversation(user) {
    state.directUser = user;
    directTabButton.hidden = false;
    byId('direct-message-title').textContent = `Direct · ${user.username}`;
    showTab('direct');
    const result = await jsonRequest(`/api/collaboration/direct/${encodeURIComponent(user.id)}/messages?limit=150`);
    renderMessages(directMessages, asArray(result.messages), 'direct');
    connectDirectSocket(user);
  }

  async function postDirectMessage() {
    if (!state.directUser) return;
    const input = byId('direct-message-input');
    const text = input.value.trim();
    if (!text) return;
    const result = await jsonRequest(`/api/collaboration/direct/${encodeURIComponent(state.directUser.id)}/messages`, {
      method: 'POST', body: JSON.stringify({text}),
    });
    input.value = '';
    appendMessage(directMessages, result.message, 'direct');
  }

  async function blockUser(userId, blocked) {
    if (!userId || !confirm(`${blocked ? 'Mute and block' : 'Unblock'} this CascadeCAD user?`)) return;
    await jsonRequest(`/api/collaboration/users/${encodeURIComponent(userId)}/block`, {
      method: 'POST', body: JSON.stringify({blocked}),
    });
    if (state.directUser?.id === userId) {
      state.directUser = null;
      disconnectSocket('direct');
      directTabButton.hidden = true;
      showTab('users');
    }
    await Promise.all([loadActiveUsers(), loadGlobalMessages()]);
    notify(blocked ? 'User muted and blocked.' : 'User unblocked.');
  }

  async function reportMessage(message) {
    const reason = prompt('Briefly describe why this global message should be reviewed:', 'Inappropriate or unsafe global-board message');
    if (!reason) return;
    const result = await jsonRequest(`/api/collaboration/messages/${encodeURIComponent(message.id)}/report`, {
      method: 'POST', body: JSON.stringify({reason}),
    });
    notify(`Report submitted (${result.report_id}).`);
  }

  document.querySelectorAll('[data-side-tab]').forEach(button => button.addEventListener('click', () => showTab(button.dataset.sideTab)));
  byId('collaboration-users-button')?.addEventListener('click', () => showTab('users'));
  byId('project-chat-button')?.addEventListener('click', () => showTab('project-chat'));
  byId('community-button')?.addEventListener('click', () => showTab('community'));
  byId('edit-collaboration-profile')?.addEventListener('click', () => showProfileDialog(true));
  byId('cancel-collaboration-profile')?.addEventListener('click', () => profileDialog.close());

  profileForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const stored = readStoredSession();
    try {
      await establishSession({
        username: usernameField.value,
        session_token: state.sessionToken || stored?.sessionToken || undefined,
        status: statusField.value,
        project_visibility: visibilityField.value,
        project_category: categoryField.value,
      });
      profileDialog.close();
      notify(`Signed in to CascadeCAD collaboration as ${state.user.username}.`);
    } catch (error) {
      notify(error.message, 9000);
    }
  });

  inviteForm?.addEventListener('submit', async event => {
    event.preventDefault();
    try {
      const result = await jsonRequest(`/api/projects/${projectId}/collaboration/invite`, {
        method: 'POST',
        body: JSON.stringify({
          username: byId('project-invite-username').value,
          role: byId('project-invite-role').value,
        }),
      });
      state.members = asArray(result.members);
      byId('project-invite-username').value = '';
      renderMembers();
      notify('Project invitation applied.');
    } catch (error) { notify(error.message, 9000); }
  });

  projectChatForm?.addEventListener('submit', event => {
    event.preventDefault();
    postProjectMessage().catch(error => notify(error.message, 9000));
  });
  globalBoardForm?.addEventListener('submit', event => {
    event.preventDefault();
    postGlobalMessage().catch(error => notify(error.message, 9000));
  });
  directMessageForm?.addEventListener('submit', event => {
    event.preventDefault();
    postDirectMessage().catch(error => notify(error.message, 9000));
  });
  byId('block-direct-user')?.addEventListener('click', () => {
    if (state.directUser) blockUser(state.directUser.id, true).catch(error => notify(error.message));
  });

  window.addEventListener('beforeunload', () => {
    for (const key of [...state.sockets.keys()]) disconnectSocket(key);
    if (presenceTimer) clearInterval(presenceTimer);
  });

  showTab(state.activeTab === 'direct' ? 'selection' : state.activeTab, {open: false});
  resumeOrPrompt().catch(error => {
    notify(error.message, 9000);
    showProfileDialog(true);
  });
}
