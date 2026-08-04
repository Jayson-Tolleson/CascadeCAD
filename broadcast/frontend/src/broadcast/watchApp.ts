import '../styles/broadcast.css';
import { BroadcastChat } from './chat';
import { JsonSocket, type BroadcastMessage } from './signaling';
import { bindUploadPlaceholder } from './uploads';
import { bindWebSearchPlaceholder } from './webSearchPane';

const root = document.querySelector<HTMLElement>('#broadcast-app') ?? document.body;
root.innerHTML = `
<main class="watch-shell">
  <header class="studio-top">
    <span class="badge">PUBLIC ACCESS</span>
    <span class="badge">MODE <b id="mode">standby</b></span>
    <span class="badge">ROOM <b id="roomName">default</b></span>
    <span class="badge">CONN <b id="conn">offline</b></span>
    <span class="badge">STREAM <b id="streamState">waiting</b></span>
    <span class="badge">SIZE <b id="streamSize">pending</b></span>
    <span class="badge">PROFILE <b id="streamProfile">pending</b></span>
  </header>
  <section class="watch-main">
    <div class="glass videoWrap watchVideo">
      <video id="viewer" autoplay playsinline muted controls></video>
      <div class="statusOverlay" id="standby">Waiting for live stream… leave this page open.</div>
    </div>
    <aside id="chatDock" class="glass chatDock">
      <div class="chatHead"><strong>Room Chat HUD</strong><button id="chatCollapseBtn" class="btn small" type="button">Collapse</button></div>
      <div class="chatTools">
        <button id="attachBtn" class="btn small" type="button">Attach</button>
        <button id="webBtn" class="btn small" type="button">Web Search</button>
        <button id="aiEnableBtn" class="btn small" type="button">AI: off</button>
      </div>
      <div id="chat" class="chatList"></div>
      <form class="input" id="form"><textarea id="chatInput" placeholder="Message room…"></textarea><button id="sendBtn" class="btn" type="submit">Send</button></form>
    </aside>
  </section>
</main>`;

const room = new URLSearchParams(location.search).get('room') ?? 'default';
const viewerId = `viewer-${crypto.randomUUID?.() ?? Math.random().toString(36).slice(2)}`;
document.querySelector('#roomName')!.textContent = room;
const video = document.querySelector<HTMLVideoElement>('#viewer')!;
const chat = new BroadcastChat(document.querySelector<HTMLElement>('#chat')!, () => undefined);
chat.connect(room);

let pc: RTCPeerConnection | undefined;
let aiEnabled = false;
let readyTimer: number | undefined;
let connectedStream = false;
let broadcasterPresent = false;
let liveAnnounced = false;
const rtcConfig: RTCConfiguration = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

function setText(id: string, value: string) { const node = document.querySelector(id); if (node) node.textContent = value; }
function showStandby(line: string) {
  const standby = document.querySelector<HTMLElement>('#standby');
  if (standby) { standby.style.display = 'block'; standby.textContent = line; }
}
function hideStandby() {
  const standby = document.querySelector<HTMLElement>('#standby');
  if (standby) standby.style.display = 'none';
}
function updateVideoSizeLabel() {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (!width || !height) return;
  video.style.setProperty('--stream-aspect', String(width / height));
  video.classList.toggle('portraitStream', height > width);
  video.classList.toggle('landscapeStream', width >= height);
  setText('#streamSize', `${width}×${height}`);
}

function resetPeer() {
  try { pc?.close(); } catch { /* noop */ }
  pc = undefined;
  connectedStream = false;
  video.srcObject = null;
}

function sendReady(reason = 'ready') {
  signal.send({ type: 'watcher-ready', viewer_id: viewerId, reason });
}

function startStandbyReadyLoop() {
  if (readyTimer) return;
  readyTimer = window.setInterval(() => {
    if (!connectedStream) sendReady('standby-poll');
  }, 2500);
}

function peer(): RTCPeerConnection {
  if (pc) return pc;
  pc = new RTCPeerConnection(rtcConfig);
  pc.ontrack = (event) => {
    const [stream] = event.streams;
    if (stream) {
      video.srcObject = stream;
      video.muted = true;
      video.play().catch(() => undefined);
      video.onloadedmetadata = updateVideoSizeLabel;
      video.onresize = updateVideoSizeLabel;
      updateVideoSizeLabel();
      connectedStream = true;
      setText('#mode', 'live');
      setText('#streamState', 'live');
      hideStandby();
    }
  };
  pc.onicecandidate = (event) => {
    if (event.candidate) signal.send({ type: 'ice', viewer_id: viewerId, candidate: event.candidate.toJSON() });
  };
  pc.onconnectionstatechange = () => {
    const state = pc?.connectionState ?? 'new';
    if (state === 'failed' || state === 'disconnected' || state === 'closed') {
      setText('#streamState', 'reconnecting');
      showStandby('Stream changed or dropped. Waiting for the next broadcaster…');
      resetPeer();
      sendReady('peer-reconnect');
    }
  };
  return pc;
}

async function onSignal(message: BroadcastMessage) {
  if (message.family === 'presence') {
    const mediaState = (message.media_state && typeof message.media_state === 'object' ? message.media_state : {}) as any;
    broadcasterPresent = Boolean(message.broadcaster_present);
    liveAnnounced = Boolean(mediaState.live || mediaState.video || mediaState.audio);
    const settings = mediaState.stream_settings && typeof mediaState.stream_settings === 'object' ? mediaState.stream_settings : undefined;
    if (settings && typeof settings.width === 'number' && typeof settings.height === 'number') {
      const bitrate = typeof mediaState.target_bitrate_bps === 'number' ? ` | ${Math.round(mediaState.target_bitrate_bps / 1_000_000)}Mbps target` : '';
      setText('#streamSize', `${settings.width}×${settings.height}${typeof settings.frameRate === 'number' ? ` @ ${Math.round(settings.frameRate)}fps` : ''}${bitrate}`);
    }
    if (typeof mediaState.granted_profile === 'string' || typeof mediaState.requested_profile === 'string') {
      const requested = typeof mediaState.requested_profile === 'string' ? mediaState.requested_profile : 'requested';
      const granted = typeof mediaState.granted_profile === 'string' ? mediaState.granted_profile : requested;
      setText('#streamProfile', requested === granted ? granted : `${requested} → ${granted}`);
    }
    setText('#streamState', connectedStream ? 'live' : liveAnnounced ? 'stream ready' : broadcasterPresent ? 'broadcaster online' : 'waiting');
    if (!connectedStream) {
      showStandby(liveAnnounced ? 'Broadcaster is live. Connecting…' : broadcasterPresent ? 'Broadcaster is online. Waiting for camera…' : 'Waiting for live stream… leave this page open.');
      if (broadcasterPresent || liveAnnounced) sendReady('presence-update');
    }
    return;
  }
  const payload = (message.payload && typeof message.payload === 'object' ? message.payload : message) as any;
  if (payload.viewer_id && payload.viewer_id !== viewerId) return;
  if (payload.type === 'offer' && payload.sdp) {
    const p = peer();
    await p.setRemoteDescription({ type: 'offer', sdp: String(payload.sdp) });
    const answer = await p.createAnswer();
    await p.setLocalDescription(answer);
    signal.send({ type: 'answer', viewer_id: viewerId, sdp: answer.sdp });
  } else if (payload.type === 'ice' && payload.candidate) {
    await peer().addIceCandidate(payload.candidate).catch(() => undefined);
  } else if (payload.type === 'media-state') {
    if (!connectedStream) sendReady('media-state');
  } else if (payload.type === 'broadcaster-ready') {
    if (!connectedStream) sendReady('broadcaster-ready');
  }
}

const signal = new JsonSocket('/ws/watch', (message) => void onSignal(message), (status) => {
  setText('#conn', status);
  if (status === 'connected') {
    setText('#mode', 'standby');
    startStandbyReadyLoop();
  }
}, () => {
  sendReady('socket-open');
  startStandbyReadyLoop();
});
signal.connect(room);

window.addEventListener('focus', () => sendReady('focus'));
document.addEventListener('visibilitychange', () => { if (!document.hidden) sendReady('visible'); });

setText('#streamState', 'waiting');
showStandby('Waiting for live stream… leave this page open.');
startStandbyReadyLoop();

document.querySelector<HTMLButtonElement>('#chatCollapseBtn')!.onclick = () => document.querySelector('#chatDock')!.classList.toggle('collapsed');
document.querySelector<HTMLButtonElement>('#aiEnableBtn')!.onclick = () => { aiEnabled = !aiEnabled; document.querySelector('#aiEnableBtn')!.textContent = aiEnabled ? 'AI: on' : 'AI: off'; if (aiEnabled) chat.requestAi(); };
bindUploadPlaceholder(document.querySelector<HTMLButtonElement>('#attachBtn')!, () => undefined, () => chat.sendUploadPlaceholder());
bindWebSearchPlaceholder(document.querySelector<HTMLButtonElement>('#webBtn')!, () => undefined);
document.querySelector<HTMLFormElement>('#form')!.onsubmit = (event) => { event.preventDefault(); const input = document.querySelector<HTMLTextAreaElement>('#chatInput')!; chat.send(input.value, 'Viewer'); input.value = ''; };
