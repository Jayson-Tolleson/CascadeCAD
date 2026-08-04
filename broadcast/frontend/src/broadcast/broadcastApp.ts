import '../styles/broadcast.css';
import { BroadcastChat } from './chat';
import { BroadcastMedia, CAMERA_PROFILES, type CameraProfileKey } from './media';
import { JsonSocket, type BroadcastMessage } from './signaling';
import { SttHook } from './stt';
import { BroadcastWakeLock } from './wakeLock';
import { bindUploadPlaceholder } from './uploads';
import { bindWebSearchPlaceholder } from './webSearchPane';

const root = document.querySelector<HTMLElement>('#broadcast-app') ?? document.body;
root.innerHTML = `
<main class="studio-shell broadcast-simple">
  <header class="studio-top">
    <span class="badge"><span id="ledServer" class="led r"></span> SERVER <b id="stServer">offline</b></span>
    <span class="badge"><span id="ledRoom" class="led r"></span> ROOM <b id="stRoomConn">offline</b></span>
    <span class="badge"><span id="ledLive" class="led r"></span> BROADCAST <b id="stLive">starting</b></span>
    <span class="badge"><span id="ledWake" class="led r"></span> WAKE <b id="stWake">starting</b></span>
    <span class="badge">Watchers <b id="stWatchers">0</b></span>
    <span class="badge">Room <b id="stRoom">default</b></span>
    <a class="btn small watchLink" href="/watch" target="_blank" rel="noopener">Go /watch</a>
  </header>
  <section class="studio-main">
    <div class="glass videoWrap">
      <div class="stage compositorStage">
        <video id="preview" autoplay playsinline muted></video>
        <div class="cameraPermission" id="cameraPermission">Camera will auto-start. Allow camera/mic when prompted.</div>
      </div>
      <div class="controlBar broadcastPills">
        <button id="facingBtn" class="btn pill"><span id="facingLed" class="led b"></span><span id="facingTxt">Facing: back</span></button>
        <label class="resolutionPick" title="Camera stream request. The status line shows what the browser actually grants."><span>Stream size</span><select id="profileSelect"></select></label>
        <button id="screenBtn" class="btn pill"><span id="screenLed" class="led r"></span><span id="screenTxt">SCREEN compositor: off</span></button>
        <button id="sttBtn" class="btn pill"><span id="sttLed" class="led r"></span><span id="sttTxt">STT: off</span></button>
        <button id="aiEnableBtn" class="btn pill"><span id="aiEnableLed" class="led r"></span><span id="aiEnableTxt">AI bridge: missing</span></button>
        <button id="ttsMonBtn" class="btn pill"><span id="ttsMonLed" class="led r"></span><span id="ttsMonTxt">AI voice: off</span></button>
        <button id="recordBtn" class="btn pill recordPill"><span id="recordLed" class="led r"></span><span id="recordTxt">Record: start</span></button>
        <button id="rtmpBtn" class="btn pill"><span id="rtmpLed" class="led r"></span><span id="rtmpTxt">RTMP: staged</span></button>
      </div>
      <div class="inlineTools">
        <input id="rtmpKeyInput" placeholder="YouTube stream key (optional)">
        <span id="recordingStatus">Camera auto-starting…</span>
        <span id="streamSizeStatus" class="streamSizeStatus">Stream: pending</span>
      </div>
    </div>

    <aside class="glass chatDock">
      <div class="chatHead"><strong>Studio Chat</strong><button id="chatCollapseBtn" class="btn small" type="button">Collapse</button></div>
      <div class="chatTools">
        <button id="webBtn" class="btn small" type="button">Web Search</button>
        <button id="attachBtn" class="btn small" type="button">Attach</button>
      </div>
      <div id="chat" class="chatList"></div>
      <form class="input" id="form"><textarea id="chatInput" placeholder="Message"></textarea><button id="sendBtn" class="btn" type="submit">Send</button></form>
    </aside>
  </section>
</main>`;

const room = new URLSearchParams(location.search).get('room') ?? 'default';
document.querySelector('#stRoom')!.textContent = room;

function led(id: string, on: boolean) {
  const node = document.querySelector<HTMLElement>(id);
  if (!node) return;
  node.classList.toggle('g', on);
  node.classList.toggle('r', !on);
}
function setText(id: string, value: string) { const node = document.querySelector(id); if (node) node.textContent = value; }
function setLive(on: boolean) { led('#ledLive', on); setText('#stLive', on ? 'live' : 'offline'); }
function setWake(on: boolean, text: string) { led('#ledWake', on); setText('#stWake', text); }
function active(id: string, on: boolean) { document.querySelector<HTMLElement>(id)?.classList.toggle('active', on); }
function status(line: string) { setText('#recordingStatus', line); }

const media = new BroadcastMedia(document.querySelector<HTMLVideoElement>('#preview')!, status);
const profileSelect = document.querySelector<HTMLSelectElement>('#profileSelect')!;
profileSelect.innerHTML = CAMERA_PROFILES.map((profile) => `<option value="${profile.key}">${profile.label}</option>`).join('');
profileSelect.value = media.profileKey();

function refreshStreamSizeStatus() {
  const settings = media.videoSettings();
  const width = typeof settings?.width === 'number' ? settings.width : undefined;
  const height = typeof settings?.height === 'number' ? settings.height : undefined;
  const frameRate = typeof settings?.frameRate === 'number' ? Math.round(settings.frameRate) : undefined;
  const camera = media.cameraSettings();
  const cameraWidth = typeof camera?.width === 'number' ? camera.width : undefined;
  const cameraHeight = typeof camera?.height === 'number' ? camera.height : undefined;
  const cameraFrameRate = typeof camera?.frameRate === 'number' ? Math.round(camera.frameRate) : undefined;
  const outputLabel = width && height ? `${width}×${height}${frameRate ? ` @ ${frameRate}fps` : ''}` : 'pending';
  const cameraLabel = cameraWidth && cameraHeight ? `${cameraWidth}×${cameraHeight}${cameraFrameRate ? ` @ ${cameraFrameRate}fps` : ''}` : 'pending';
  setText('#streamSizeStatus', `Output: ${outputLabel} | Camera: ${cameraLabel} | ${media.sensorMaxSummary()} | send≈${Math.round(media.recommendedVideoBitrate() / 1_000_000)}Mbps`);
}
const wakeLock = new BroadcastWakeLock((line, on) => { setWake(on, on ? 'on' : 'fallback'); status(line); });
const chat = new BroadcastChat(document.querySelector<HTMLElement>('#chat')!, () => undefined);
chat.connect(room);

const peers = new Map<string, RTCPeerConnection>();
const rtcConfig: RTCConfiguration = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };
let aiEnabled = false;
let ttsEnabled = false;
let autoStarted = false;

function currentStream(): MediaStream | undefined { return media.currentStream(); }

function preferHighResolutionSender(sender: RTCRtpSender) {
  if (sender.track?.kind !== 'video') return;
  try {
    const params = sender.getParameters();
    (params as RTCRtpSendParameters & { degradationPreference?: string }).degradationPreference = 'maintain-resolution';
    params.encodings = params.encodings?.length ? params.encodings : [{}];
    params.encodings[0].maxBitrate = media.recommendedVideoBitrate();
    params.encodings[0].maxFramerate = Math.round(media.videoSettings()?.frameRate ?? 30);
    (params.encodings[0] as RTCRtpEncodingParameters & { scaleResolutionDownBy?: number }).scaleResolutionDownBy = 1;
    void sender.setParameters(params).catch(() => undefined);
  } catch {
    // Older browsers may reject sender parameters; the raw track still keeps its capture size.
  }
}

function addStreamTracks(pc: RTCPeerConnection, stream: MediaStream) {
  stream.getTracks().forEach((track) => {
    const sender = pc.addTrack(track, stream);
    preferHighResolutionSender(sender);
  });
}

function peerFor(viewerId: string): RTCPeerConnection {
  const existing = peers.get(viewerId);
  if (existing) return existing;
  const pc = new RTCPeerConnection(rtcConfig);
  pc.onicecandidate = (event) => {
    if (event.candidate) signal.send({ type: 'ice', viewer_id: viewerId, candidate: event.candidate.toJSON() });
  };
  const stream = currentStream();
  if (stream) addStreamTracks(pc, stream);
  peers.set(viewerId, pc);
  return pc;
}

async function offerTo(viewerId: string) {
  if (!currentStream()) return;
  const pc = peerFor(viewerId);
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  signal.send({ type: 'offer', viewer_id: viewerId, sdp: offer.sdp });
}

async function replaceTracks() {
  const stream = currentStream();
  if (!stream) return;
  for (const [viewerId, pc] of peers) {
    pc.getSenders().forEach((sender) => pc.removeTrack(sender));
    addStreamTracks(pc, stream);
    await offerTo(viewerId);
  }
}

function sendMediaState(extra: Record<string, unknown> = {}) {
  const stream = currentStream();
  signal.send({
    type: 'media-state',
    state: {
      live: Boolean(stream),
      video: Boolean(stream?.getVideoTracks().length),
      audio: Boolean(stream?.getAudioTracks().length),
      facing: media.facingModeValue(),
      screen: media.hasScreen(),
      profile: media.profileKey(),
      profile_label: media.profileLabel(),
      stream_settings: media.videoSettings(),
      camera_settings: media.cameraSettings(),
      sensor_max: media.sensorMaxSummary(),
      requested_profile: media.profileLabel(),
      granted_profile: media.grantedProfileLabel(),
      target_bitrate_bps: media.recommendedVideoBitrate(),
      ...extra,
    },
  });
}

async function onSignal(message: BroadcastMessage) {
  if (message.family === 'presence') {
    const count = Number(message.watcher_count ?? 0);
    setText('#stWatchers', String(count));
    led('#ledRoom', true); setText('#stRoomConn', 'connected');
    return;
  }
  const payload = (message.payload && typeof message.payload === 'object' ? message.payload : message) as any;
  const viewerId = String(payload.viewer_id ?? message.viewer_id ?? 'viewer');
  if (payload.type === 'watcher-ready') {
    await offerTo(viewerId);
  } else if (payload.type === 'answer' && payload.sdp) {
    await peerFor(viewerId).setRemoteDescription({ type: 'answer', sdp: String(payload.sdp) });
  } else if (payload.type === 'ice' && payload.candidate) {
    await peerFor(viewerId).addIceCandidate(payload.candidate).catch(() => undefined);
  }
}

const signal = new JsonSocket('/ws/broadcast', (message) => void onSignal(message), (socketStatus) => {
  led('#ledServer', socketStatus === 'connected');
  setText('#stServer', socketStatus);
}, () => {
  signal.send({ type: 'broadcaster-ready' });
  sendMediaState();
});
signal.connect(room);

async function cameraOnAuto() {
  if (autoStarted) return;
  autoStarted = true;
  try {
    await media.autoStartCamera();
    document.querySelector<HTMLElement>('#cameraPermission')?.remove();
    led('#facingLed', true); setText('#facingTxt', `Facing: ${media.facingLabel()}`);
    refreshStreamSizeStatus();
    setLive(true);
    await wakeLock.start();
    sendMediaState({ auto_started: true, wake_lock: true });
    await replaceTracks();
  } catch {
    autoStarted = false;
    setLive(false);
    status('Camera permission blocked. Click Facing to retry camera permission.');
  }
}

async function switchFacing() {
  try {
    await media.switchCamera();
    led('#facingLed', true); setText('#facingTxt', `Facing: ${media.facingLabel()}`);
    refreshStreamSizeStatus();
    setLive(true);
    await wakeLock.start();
    sendMediaState({ wake_lock: true });
    await replaceTracks();
  } catch {
    status('Facing switch failed or permission blocked.');
  }
}

async function startScreenCompositor() {
  await media.startScreenCompositor();
  led('#screenLed', media.hasScreen());
  active('#screenBtn', media.hasScreen());
  setText('#screenTxt', media.hasScreen() ? 'SCREEN compositor: on' : 'SCREEN compositor: off');
  setLive(Boolean(currentStream()));
  refreshStreamSizeStatus();
  await wakeLock.start();
  sendMediaState({ screen: media.hasScreen(), compositor: media.hasScreen(), wake_lock: true });
  await replaceTracks();
}


profileSelect.onchange = async () => {
  try {
    await media.setCameraProfile(profileSelect.value as CameraProfileKey);
    document.querySelector<HTMLElement>('#cameraPermission')?.remove();
    led('#facingLed', true);
    setText('#facingTxt', `Facing: ${media.facingLabel()}`);
    setLive(true);
    refreshStreamSizeStatus();
    sendMediaState({ profile_changed: true });
    await replaceTracks();
  } catch {
    status('Camera profile failed. Try 2K/QHD or SAFE 1280×720, or allow camera permission again.');
  }
};

document.querySelector<HTMLButtonElement>('#facingBtn')!.onclick = () => void switchFacing();
document.querySelector<HTMLButtonElement>('#screenBtn')!.onclick = () => void startScreenCompositor();
document.querySelector<HTMLButtonElement>('#sttBtn')!.onclick = () => void stt.toggle();
document.querySelector<HTMLButtonElement>('#aiEnableBtn')!.onclick = () => {
  aiEnabled = !aiEnabled;
  led('#aiEnableLed', aiEnabled);
  active('#aiEnableBtn', aiEnabled);
  setText('#aiEnableTxt', aiEnabled ? 'AI bridge: requested' : 'AI bridge: missing');
  chat.requestAi();
  status('AI bridge placeholder: Vertex route not connected yet.');
};
document.querySelector<HTMLButtonElement>('#ttsMonBtn')!.onclick = () => {
  ttsEnabled = !ttsEnabled;
  led('#ttsMonLed', ttsEnabled);
  active('#ttsMonBtn', ttsEnabled);
  setText('#ttsMonTxt', ttsEnabled ? 'AI voice: on' : 'AI voice: off');
  status(ttsEnabled ? 'AI voice monitor option enabled.' : 'AI voice monitor option off.');
};
document.querySelector<HTMLButtonElement>('#recordBtn')!.onclick = async () => {
  const recording = await media.toggleRecording((url, filename) => {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    led('#recordLed', false);
    active('#recordBtn', false);
    setText('#recordTxt', 'Record: start');
  });
  led('#recordLed', recording);
  active('#recordBtn', recording);
  setText('#recordTxt', recording ? 'Record: stop/download' : 'Record: start');
};
document.querySelector<HTMLButtonElement>('#rtmpBtn')!.onclick = () => {
  led('#rtmpLed', true);
  active('#rtmpBtn', true);
  setText('#rtmpTxt', 'RTMP: staged');
  status('RTMP hook staged. Local WebM recording and watch stream are active.');
};

document.querySelector<HTMLButtonElement>('#chatCollapseBtn')!.onclick = () => document.querySelector('.chatDock')!.classList.toggle('collapsed');
bindUploadPlaceholder(document.querySelector<HTMLButtonElement>('#attachBtn')!, status, () => chat.sendUploadPlaceholder());
bindWebSearchPlaceholder(document.querySelector<HTMLButtonElement>('#webBtn')!, status);
document.querySelector<HTMLFormElement>('#form')!.onsubmit = (event) => { event.preventDefault(); const input = document.querySelector<HTMLTextAreaElement>('#chatInput')!; chat.send(input.value, 'Broadcaster'); input.value = ''; };

const stt = new SttHook((text) => { chat.sendTranscript(text); if (aiEnabled) chat.requestAi(); }, (line) => {
  const isOn = /listening|native|server/.test(line) && !/stopped|unsupported|error|unavailable/.test(line);
  setText('#sttTxt', isOn ? 'STT: on' : line);
  led('#sttLed', isOn);
  active('#sttBtn', isOn);
  status(line);
}, room, () => currentStream());

setTimeout(() => void cameraOnAuto(), 250);
