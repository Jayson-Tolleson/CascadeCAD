export type RecordCallback = (url: string, filename: string) => void;

export type CameraProfileKey =
  | 'uhd-8k-landscape'
  | 'uhd-8k-portrait'
  | 'true-4x3-landscape'
  | 'true-4x3-portrait'
  | 'uhd-4k-landscape'
  | 'uhd-4k-portrait'
  | 'qhd-2k-landscape'
  | 'qhd-2k-portrait'
  | 'auto-sensor'
  | 'safe-1080p'
  | 'safe-720p';

type CameraProfile = {
  key: CameraProfileKey;
  label: string;
  width?: number;
  height?: number;
  fps: number;
  bitrate: number;
  description: string;
};

export const CAMERA_PROFILES: CameraProfile[] = [
  { key: 'auto-sensor', label: 'AUTO max sensor', width: 7680, height: 4320, fps: 30, bitrate: 60_000_000, description: 'starts camera on the largest live sensor mode the browser exposes' },
  { key: 'uhd-8k-landscape', label: '8K 16:9 7680×4320', width: 7680, height: 4320, fps: 30, bitrate: 120_000_000, description: 'maximum UHD 8K landscape request; falls back if unsupported' },
  { key: 'uhd-8k-portrait', label: '8K portrait 4320×7680', width: 4320, height: 7680, fps: 30, bitrate: 120_000_000, description: 'maximum UHD 8K portrait request; falls back if unsupported' },
  { key: 'true-4x3-landscape', label: 'TRUE 4:3 4032×3040', width: 4032, height: 3040, fps: 30, bitrate: 48_000_000, description: 'high-res landscape 4:3 sensor request' },
  { key: 'true-4x3-portrait', label: 'TRUE portrait 3040×4032', width: 3040, height: 4032, fps: 30, bitrate: 48_000_000, description: 'high-res portrait 3:4 sensor request' },
  { key: 'uhd-4k-landscape', label: '4K 16:9 3840×2160', width: 3840, height: 2160, fps: 30, bitrate: 45_000_000, description: 'UHD landscape request' },
  { key: 'uhd-4k-portrait', label: '4K portrait 2160×3840', width: 2160, height: 3840, fps: 30, bitrate: 45_000_000, description: 'UHD portrait request' },
  { key: 'qhd-2k-landscape', label: '2K/QHD 16:9 2560×1440', width: 2560, height: 1440, fps: 30, bitrate: 24_000_000, description: '2K/QHD landscape request' },
  { key: 'qhd-2k-portrait', label: '2K/QHD portrait 1440×2560', width: 1440, height: 2560, fps: 30, bitrate: 24_000_000, description: '2K/QHD portrait request' },
  { key: 'safe-1080p', label: 'SAFE 1920×1080', width: 1920, height: 1080, fps: 30, bitrate: 12_000_000, description: 'standard HD fallback mode' },
  { key: 'safe-720p', label: 'SAFE 1280×720', width: 1280, height: 720, fps: 30, bitrate: 6_000_000, description: 'fallback 720p mode' },
];

const FALLBACK_LADDER: Record<CameraProfileKey, CameraProfileKey[]> = {
  'uhd-8k-landscape': ['uhd-8k-landscape', 'true-4x3-landscape', 'uhd-4k-landscape', 'qhd-2k-landscape', 'safe-1080p', 'safe-720p'],
  'uhd-8k-portrait': ['uhd-8k-portrait', 'true-4x3-portrait', 'uhd-4k-portrait', 'qhd-2k-portrait', 'safe-1080p', 'safe-720p'],
  'true-4x3-landscape': ['true-4x3-landscape', 'uhd-4k-landscape', 'qhd-2k-landscape', 'safe-1080p', 'safe-720p'],
  'true-4x3-portrait': ['true-4x3-portrait', 'uhd-4k-portrait', 'qhd-2k-portrait', 'safe-1080p', 'safe-720p'],
  'uhd-4k-landscape': ['uhd-4k-landscape', 'qhd-2k-landscape', 'safe-1080p', 'safe-720p'],
  'uhd-4k-portrait': ['uhd-4k-portrait', 'qhd-2k-portrait', 'safe-1080p', 'safe-720p'],
  'qhd-2k-landscape': ['qhd-2k-landscape', 'safe-1080p', 'safe-720p'],
  'qhd-2k-portrait': ['qhd-2k-portrait', 'safe-1080p', 'safe-720p'],
  'auto-sensor': ['auto-sensor', 'uhd-8k-landscape', 'true-4x3-landscape', 'uhd-4k-landscape', 'qhd-2k-landscape', 'safe-1080p', 'safe-720p'],
  'safe-1080p': ['safe-1080p', 'safe-720p'],
  'safe-720p': ['safe-720p'],
};

type NumericCapability = { min?: number; max?: number; step?: number };

function waitForVideo(video: HTMLVideoElement): Promise<void> {
  if (video.readyState >= 2) return Promise.resolve();
  return new Promise((resolve) => {
    video.onloadedmetadata = () => resolve();
    video.oncanplay = () => resolve();
  });
}

function stopStream(stream?: MediaStream) {
  stream?.getTracks().forEach((track) => track.stop());
}

function profileFor(key: CameraProfileKey): CameraProfile {
  return CAMERA_PROFILES.find((profile) => profile.key === key) ?? CAMERA_PROFILES[0];
}

function num(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function trackSettings(stream?: MediaStream): MediaTrackSettings | undefined {
  return stream?.getVideoTracks()[0]?.getSettings();
}

function cameraTrack(stream?: MediaStream): MediaStreamTrack | undefined {
  return stream?.getVideoTracks()[0];
}

function trackCapabilities(stream?: MediaStream): MediaTrackCapabilities | undefined {
  const track = cameraTrack(stream) as (MediaStreamTrack & { getCapabilities?: () => MediaTrackCapabilities }) | undefined;
  try { return track?.getCapabilities?.(); } catch { return undefined; }
}

function capRange(value: unknown): NumericCapability | undefined {
  if (!value || typeof value !== 'object') return undefined;
  const range = value as NumericCapability;
  return typeof range.max === 'number' || typeof range.min === 'number' ? range : undefined;
}

function sensorMaxLabel(stream?: MediaStream): string {
  const caps = trackCapabilities(stream) as (MediaTrackCapabilities & { width?: unknown; height?: unknown; frameRate?: unknown }) | undefined;
  const widthMax = num(capRange(caps?.width)?.max);
  const heightMax = num(capRange(caps?.height)?.max);
  const fpsMax = num(capRange(caps?.frameRate)?.max);
  if (!widthMax || !heightMax) return 'sensor max: unavailable';
  return `sensor max: ${Math.round(widthMax)}×${Math.round(heightMax)}${fpsMax ? ` @ ≤${Math.round(fpsMax)}fps` : ''}`;
}

function mediaSettingsLabel(settings?: MediaTrackSettings): string {
  const width = num(settings?.width);
  const height = num(settings?.height);
  const fps = num(settings?.frameRate);
  if (!width || !height) return 'pending';
  return `${width}×${height}${fps ? ` @ ${Math.round(fps)}fps` : ''}`;
}

function streamSizeLabel(stream?: MediaStream): string {
  const settings = trackSettings(stream);
  const width = num(settings?.width);
  const height = num(settings?.height);
  const fps = num(settings?.frameRate);
  if (!width || !height) return 'granted: unknown size';
  return `granted: ${width}×${height}${fps ? ` @ ${Math.round(fps)}fps` : ''}`;
}


function resolutionClassLabel(width?: number, height?: number): string {
  if (!width || !height) return 'actual: unknown';
  const pixels = width * height;
  if (pixels >= 30_000_000) return `actual: 8K class ${width}×${height}`;
  if (pixels >= 12_000_000) return `actual: 12MP/true-sensor class ${width}×${height}`;
  if (pixels >= 8_000_000) return `actual: 4K class ${width}×${height}`;
  if (pixels >= 3_500_000) return `actual: 2K/QHD class ${width}×${height}`;
  if (pixels >= 2_000_000) return `actual: 1080p class ${width}×${height}`;
  return `actual: fallback class ${width}×${height}`;
}

function estimateVideoBitrate(width?: number, height?: number, fallback = 28_000_000): number {
  if (!width || !height) return fallback;
  const pixels = width * height;
  if (pixels >= 30_000_000) return 120_000_000; // 8K class
  if (pixels >= 12_000_000) return 60_000_000; // 4032x3040 / 12MP class
  if (pixels >= 8_000_000) return 45_000_000;  // 4K class
  if (pixels >= 3_500_000) return 24_000_000;  // 2K/QHD class
  if (pixels >= 2_000_000) return 12_000_000;  // 1080p class
  return 6_000_000;
}

function streamPixels(stream?: MediaStream): number {
  const settings = trackSettings(stream);
  return (num(settings?.width) ?? 0) * (num(settings?.height) ?? 0);
}

async function tryApplyCameraConstraints(track: MediaStreamTrack, constraints: MediaTrackConstraints): Promise<boolean> {
  try {
    await track.applyConstraints(constraints);
    return true;
  } catch {
    return false;
  }
}

async function pushCameraToSensorMax(stream: MediaStream, profile: CameraProfile): Promise<void> {
  const track = cameraTrack(stream);
  const caps = trackCapabilities(stream) as (MediaTrackCapabilities & { width?: unknown; height?: unknown; frameRate?: unknown }) | undefined;
  if (!track || !caps) return;

  const widthMax = num(capRange(caps.width)?.max);
  const heightMax = num(capRange(caps.height)?.max);
  const fpsMax = num(capRange(caps.frameRate)?.max);
  if (!widthMax || !heightMax) return;

  const desiredFps = Math.min(profile.fps, fpsMax ?? profile.fps);
  const attempts: MediaTrackConstraints[] = [
    {
      width: { exact: Math.round(widthMax) },
      height: { exact: Math.round(heightMax) },
      frameRate: { ideal: desiredFps },
      aspectRatio: { ideal: widthMax / heightMax },
    },
    {
      width: { ideal: Math.round(widthMax) },
      height: { ideal: Math.round(heightMax) },
      frameRate: { ideal: desiredFps },
      aspectRatio: { ideal: widthMax / heightMax },
    },
    {
      width: { min: Math.min(1920, Math.round(widthMax)), ideal: Math.round(widthMax) },
      height: { min: Math.min(1080, Math.round(heightMax)), ideal: Math.round(heightMax) },
      frameRate: { ideal: desiredFps },
    },
  ];
  attempts.forEach((constraints) => ((constraints as MediaTrackConstraints & { resizeMode?: string }).resizeMode = 'none'));

  const beforePixels = streamPixels(stream);
  for (const constraints of attempts) {
    if (await tryApplyCameraConstraints(track, constraints) && streamPixels(stream) >= beforePixels) return;
  }
}

function updateVideoAspect(video: HTMLVideoElement, stream?: MediaStream) {
  const settings = trackSettings(stream);
  const width = num(settings?.width) ?? video.videoWidth;
  const height = num(settings?.height) ?? video.videoHeight;
  if (!width || !height) return;
  video.dataset.streamWidth = String(width);
  video.dataset.streamHeight = String(height);
  video.style.setProperty('--stream-aspect', String(width / height));
  video.classList.toggle('portraitStream', height > width);
  video.classList.toggle('landscapeStream', width >= height);
}

function chooseCompositeOutputSize(profile: CameraProfile, screenW?: number, screenH?: number, cameraW?: number, cameraH?: number): { width: number; height: number } {
  const fallbackW = cameraW ?? screenW ?? profile.width ?? 1920;
  const fallbackH = cameraH ?? screenH ?? profile.height ?? 1080;
  const cameraPixels = (cameraW ?? 0) * (cameraH ?? 0);
  const screenPixels = (screenW ?? 0) * (screenH ?? 0);

  // The compositor stream must not be capped by a 1080p monitor. If the camera
  // has a larger live sensor mode than the display capture, keep the output at
  // the camera/sensor size and draw the screen as one input inside that canvas.
  if (cameraPixels > screenPixels && cameraW && cameraH) return { width: cameraW, height: cameraH };
  if (screenW && screenH) return { width: screenW, height: screenH };
  return { width: fallbackW, height: fallbackH };
}

function buildVideoConstraints(profile: CameraProfile, facingMode: 'user' | 'environment', strictSize = false): MediaTrackConstraints {
  const constraints: MediaTrackConstraints = {
    facingMode: { ideal: facingMode },
    // Do not hard-cap frameRate here. Many cameras expose their largest live mode at
    // 15-24fps; resolution is more important for this broadcast page than refusing
    // the sensor-max mode because 30fps is unavailable.
    frameRate: { ideal: profile.fps },
  };

  if (profile.width && profile.height) {
    constraints.width = strictSize ? { exact: profile.width } : { ideal: profile.width };
    constraints.height = strictSize ? { exact: profile.height } : { ideal: profile.height };
    constraints.aspectRatio = { ideal: profile.width / profile.height };
  }

  // resizeMode:none asks Chrome/Android not to crop/scale the camera feed before it reaches us.
  // Browsers that do not support it simply ignore it.
  (constraints as MediaTrackConstraints & { resizeMode?: string }).resizeMode = 'none';
  return constraints;
}

async function getCameraStream(profile: CameraProfile, facingMode: 'user' | 'environment'): Promise<{ stream: MediaStream; grantedProfile: CameraProfile }> {
  const audio: MediaTrackConstraints = { echoCancellation: true, noiseSuppression: true, autoGainControl: true };
  let lastError: unknown;
  for (const key of FALLBACK_LADDER[profile.key]) {
    const candidate = profileFor(key);
    try {
      const strictSize = key !== 'auto-sensor' && key !== 'safe-720p';
      const stream = await navigator.mediaDevices.getUserMedia({ video: buildVideoConstraints(candidate, facingMode, strictSize), audio });
      if (profile.key === 'auto-sensor' || key === 'auto-sensor') await pushCameraToSensorMax(stream, candidate);
      return { stream, grantedProfile: candidate };
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

type DrawMode = 'contain' | 'cover';

function drawVideoFit(
  ctx: CanvasRenderingContext2D,
  video: HTMLVideoElement,
  x: number,
  y: number,
  w: number,
  h: number,
  mode: DrawMode = 'contain',
) {
  const sourceW = video.videoWidth || num(trackSettings(video.srcObject instanceof MediaStream ? video.srcObject : undefined)?.width) || w;
  const sourceH = video.videoHeight || num(trackSettings(video.srcObject instanceof MediaStream ? video.srcObject : undefined)?.height) || h;
  if (!sourceW || !sourceH || !w || !h) return;
  const scale = mode === 'cover' ? Math.max(w / sourceW, h / sourceH) : Math.min(w / sourceW, h / sourceH);
  const drawW = Math.round(sourceW * scale);
  const drawH = Math.round(sourceH * scale);
  const drawX = Math.round(x + (w - drawW) / 2);
  const drawY = Math.round(y + (h - drawH) / 2);
  ctx.drawImage(video, drawX, drawY, drawW, drawH);
}

export class BroadcastMedia {
  private stream?: MediaStream;
  private cameraStream?: MediaStream;
  private screenStream?: MediaStream;
  private canvas?: HTMLCanvasElement;
  private canvasContext?: CanvasRenderingContext2D | null;
  private cameraVideo?: HTMLVideoElement;
  private screenVideo?: HTMLVideoElement;
  private drawHandle?: number;
  private recorder?: MediaRecorder;
  private recorded: Blob[] = [];
  private facingMode: 'user' | 'environment' = 'environment';
  private activeProfileKey: CameraProfileKey = 'auto-sensor';
  private requestedProfile?: CameraProfile;
  private grantedProfile?: CameraProfile;
  private downloadUrl?: string;
  private usingCompositor = false;

  constructor(private readonly video: HTMLVideoElement, private readonly status: (line: string) => void) {}

  currentStream(): MediaStream | undefined { return this.stream; }
  facingModeValue(): 'user' | 'environment' { return this.facingMode; }
  facingLabel(): 'front' | 'back' { return this.facingMode === 'user' ? 'front' : 'back'; }
  isRecording(): boolean { return this.recorder?.state === 'recording'; }
  hasScreen(): boolean { return Boolean(this.screenStream?.getVideoTracks().some((track) => track.readyState === 'live')); }
  profileKey(): CameraProfileKey { return this.activeProfileKey; }
  profileLabel(): string { return profileFor(this.activeProfileKey).label; }
  grantedProfileLabel(): string {
    const settings = this.videoSettings();
    return resolutionClassLabel(num(settings?.width), num(settings?.height));
  }
  streamSummary(): string { return streamSizeLabel(this.stream); }
  videoSettings(): MediaTrackSettings | undefined { return trackSettings(this.stream); }
  cameraSettings(): MediaTrackSettings | undefined { return trackSettings(this.cameraStream); }
  cameraSummary(): string { return mediaSettingsLabel(this.cameraSettings()); }
  sensorMaxSummary(): string { return sensorMaxLabel(this.cameraStream); }
  recommendedVideoBitrate(): number {
    const settings = this.videoSettings();
    return estimateVideoBitrate(num(settings?.width), num(settings?.height), this.grantedProfile?.bitrate ?? profileFor(this.activeProfileKey).bitrate);
  }

  async autoStartCamera() {
    if (this.stream) return this.stream;
    return this.startCamera();
  }

  async setCameraProfile(key: CameraProfileKey) {
    this.activeProfileKey = key;
    return this.startCamera();
  }

  private grantedOrFallbackLabel(requested: CameraProfile): string {
    if (!this.grantedProfile || this.grantedProfile.key === requested.key) return requested.label;
    return `${requested.label} requested → ${this.grantedProfile.label} fallback`;
  }

  async startCamera() {
    try {
      this.stopCompositorLoop();
      stopStream(this.cameraStream);
      stopStream(this.screenStream);
      this.screenStream = undefined;
      this.usingCompositor = false;
      const profile = profileFor(this.activeProfileKey);
      this.requestedProfile = profile;
      const result = await getCameraStream(profile, this.facingMode);
      this.cameraStream = result.stream;
      this.grantedProfile = result.grantedProfile;
      this.stream = this.cameraStream;
      this.video.srcObject = this.stream;
      this.video.muted = true;
      await this.video.play().catch(() => undefined);
      updateVideoAspect(this.video, this.stream);
      this.status(`CAM: ${this.facingLabel()} | ${profile.label} requested | camera ${this.cameraSummary()} | ${this.sensorMaxSummary()} | output ${streamSizeLabel(this.stream)} | send≈${Math.round(this.recommendedVideoBitrate() / 1_000_000)}Mbps`);
      return this.stream;
    } catch (error) {
      this.status('CAM permission needed or requested high-res mode was refused');
      throw error;
    }
  }

  async startScreenCompositor() {
    const nav = navigator.mediaDevices as MediaDevices & { getDisplayMedia?: (constraints?: MediaStreamConstraints) => Promise<MediaStream> };
    if (!nav.getDisplayMedia) { this.status('SCREEN unsupported'); return this.stream; }
    try {
      if (!this.cameraStream) await this.startCamera();
      this.screenStream = await nav.getDisplayMedia({
        video: { frameRate: { ideal: 30, max: 30 } } as MediaTrackConstraints,
        audio: true,
      });
      await this.buildCompositeStream();
      this.screenStream.getVideoTracks()[0]?.addEventListener('ended', () => void this.startCamera());
      this.status(`SCREEN compositor: on | ${streamSizeLabel(this.stream)} | send≈${Math.round(this.recommendedVideoBitrate() / 1_000_000)}Mbps`);
      return this.stream;
    } catch {
      this.status('SCREEN canceled');
      return this.stream;
    }
  }

  async switchCamera() {
    this.facingMode = this.facingMode === 'user' ? 'environment' : 'user';
    stopStream(this.cameraStream);
    const profile = profileFor(this.activeProfileKey);
    this.requestedProfile = profile;
    const result = await getCameraStream(profile, this.facingMode);
    this.cameraStream = result.stream;
    this.grantedProfile = result.grantedProfile;
    if (this.usingCompositor && this.screenStream) {
      await this.buildCompositeStream();
    } else {
      this.stream = this.cameraStream;
      this.video.srcObject = this.stream;
      await this.video.play().catch(() => undefined);
      updateVideoAspect(this.video, this.stream);
    }
    this.status(`CAM: ${this.facingLabel()} | ${profile.label} requested | camera ${this.cameraSummary()} | ${this.sensorMaxSummary()} | output ${streamSizeLabel(this.stream)} | send≈${Math.round(this.recommendedVideoBitrate() / 1_000_000)}Mbps`);
    return this.stream;
  }

  private async buildCompositeStream() {
    if (!this.cameraStream || !this.screenStream) return;
    this.usingCompositor = true;
    this.stopCompositorLoop();
    this.canvas = this.canvas ?? document.createElement('canvas');

    const screenSettings = this.screenStream.getVideoTracks()[0]?.getSettings();
    const cameraSettings = this.cameraStream.getVideoTracks()[0]?.getSettings();
    const screenW = num(screenSettings?.width);
    const screenH = num(screenSettings?.height);
    const cameraW = num(cameraSettings?.width);
    const cameraH = num(cameraSettings?.height);
    const outputSize = chooseCompositeOutputSize(profileFor(this.activeProfileKey), screenW, screenH, cameraW, cameraH);
    this.canvas.width = outputSize.width;
    this.canvas.height = outputSize.height;
    this.canvasContext = this.canvas.getContext('2d', { alpha: false });

    this.screenVideo = document.createElement('video');
    this.screenVideo.srcObject = this.screenStream;
    this.screenVideo.muted = true;
    this.screenVideo.playsInline = true;
    await waitForVideo(this.screenVideo);
    await this.screenVideo.play().catch(() => undefined);

    this.cameraVideo = document.createElement('video');
    this.cameraVideo.srcObject = this.cameraStream;
    this.cameraVideo.muted = true;
    this.cameraVideo.playsInline = true;
    await waitForVideo(this.cameraVideo);
    await this.cameraVideo.play().catch(() => undefined);

    const fps = num(screenSettings?.frameRate) ?? num(cameraSettings?.frameRate) ?? profileFor(this.activeProfileKey).fps;
    const canvasStream = this.canvas.captureStream(Math.min(30, Math.max(1, Math.round(fps))));
    const audioTracks = [
      ...this.cameraStream.getAudioTracks(),
      ...this.screenStream.getAudioTracks(),
    ];
    this.stream = new MediaStream([...canvasStream.getVideoTracks(), ...audioTracks]);
    this.video.srcObject = this.stream;
    this.video.muted = true;
    await this.video.play().catch(() => undefined);
    updateVideoAspect(this.video, this.stream);
    this.drawComposite();
  }

  private drawComposite = () => {
    if (!this.canvas || !this.canvasContext || !this.screenVideo || !this.cameraVideo) return;
    const ctx = this.canvasContext;
    const w = this.canvas.width;
    const h = this.canvas.height;
    ctx.fillStyle = '#001012';
    ctx.fillRect(0, 0, w, h);
    drawVideoFit(ctx, this.screenVideo, 0, 0, w, h, 'contain');

    const cameraAspect = (this.cameraVideo.videoWidth || 16) / (this.cameraVideo.videoHeight || 9);
    const insetW = Math.round(Math.min(w * 0.32, 960));
    const insetH = Math.round(insetW / cameraAspect);
    const pad = Math.max(18, Math.round(Math.min(w, h) * 0.024));
    const x = w - insetW - pad;
    const y = h - insetH - pad;
    ctx.save();
    ctx.shadowColor = '#22c55e';
    ctx.shadowBlur = 22;
    ctx.fillStyle = '#032018';
    ctx.fillRect(x - 9, y - 9, insetW + 18, insetH + 18);
    ctx.lineWidth = 5;
    ctx.strokeStyle = '#22c55e';
    ctx.strokeRect(x - 9, y - 9, insetW + 18, insetH + 18);
    ctx.lineWidth = 3;
    ctx.strokeStyle = '#38bdf8';
    ctx.strokeRect(x - 4, y - 4, insetW + 8, insetH + 8);
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#f97316';
    ctx.strokeRect(x + 2, y + 2, insetW - 4, insetH - 4);
    drawVideoFit(ctx, this.cameraVideo, x, y, insetW, insetH, 'contain');
    ctx.restore();
    this.drawHandle = requestAnimationFrame(this.drawComposite);
  };

  private stopCompositorLoop() {
    if (this.drawHandle) cancelAnimationFrame(this.drawHandle);
    this.drawHandle = undefined;
  }

  async toggleRecording(onDownloadReady: RecordCallback) {
    if (this.recorder?.state === 'recording') {
      this.stopRecording();
      return false;
    }
    await this.startRecording(onDownloadReady);
    return true;
  }

  private async startRecording(onDownloadReady: RecordCallback) {
    if (!this.stream) await this.startCamera();
    if (!this.stream) return;
    if (this.downloadUrl) URL.revokeObjectURL(this.downloadUrl);
    this.recorded = [];
    const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus') ? 'video/webm;codecs=vp9,opus' : 'video/webm';
    const videoBitsPerSecond = this.recommendedVideoBitrate();
    this.recorder = new MediaRecorder(this.stream, { mimeType, videoBitsPerSecond, audioBitsPerSecond: 192_000 });
    this.recorder.ondataavailable = (event) => { if (event.data.size > 0) this.recorded.push(event.data); };
    this.recorder.onstop = () => {
      const blob = new Blob(this.recorded, { type: mimeType });
      this.downloadUrl = URL.createObjectURL(blob);
      const filename = `lftr-broadcast-${new Date().toISOString().replace(/[:.]/g, '-')}.webm`;
      onDownloadReady(this.downloadUrl, filename);
      this.status('Record: downloaded');
    };
    this.recorder.start(1000);
    this.status(`Record: on | ${streamSizeLabel(this.stream)} | ${Math.round(videoBitsPerSecond / 1_000_000)}Mbps target`);
  }

  stopRecording() {
    if (this.recorder?.state === 'recording') this.recorder.stop();
  }

  stopAll() {
    this.stopRecording();
    this.stopCompositorLoop();
    stopStream(this.stream);
    stopStream(this.cameraStream);
    stopStream(this.screenStream);
    this.stream = undefined;
    this.cameraStream = undefined;
    this.screenStream = undefined;
    this.video.srcObject = null;
  }
}
