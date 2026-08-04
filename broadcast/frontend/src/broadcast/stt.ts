type SpeechRecognitionCtor = new () => {
  continuous: boolean;
  interimResults: boolean;
  lang?: string;
  onresult: ((event: { results: ArrayLike<{ 0: { transcript: string }; isFinal: boolean }> }) => void) | null;
  onerror: ((event?: unknown) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
};

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  }
}

type SttMode = 'idle' | 'native' | 'server';

type ServerSttMessage = {
  type?: string;
  text?: string;
  final?: boolean;
  status?: string;
  error?: string;
  provider?: string;
};

function wsUrl(path: string, room: string): string {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${location.host}${path}?room=${encodeURIComponent(room)}`;
}

function pickAudioMime(): string {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/ogg;codecs=opus',
    'audio/webm',
    'audio/ogg',
  ];
  return candidates.find((type) => typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(type)) ?? '';
}

export class SttHook {
  private recognition?: InstanceType<SpeechRecognitionCtor>;
  private recorder?: MediaRecorder;
  private socket?: WebSocket;
  private fallbackMic?: MediaStream;
  private mode: SttMode = 'idle';
  private shouldListen = false;

  constructor(
    private readonly onFinal: (text: string) => void,
    private readonly status: (line: string) => void,
    private readonly room: string,
    private readonly getAudioSource?: () => MediaStream | undefined,
  ) {}

  available() {
    return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition || (navigator.mediaDevices && typeof MediaRecorder !== 'undefined'));
  }

  listening() { return this.mode !== 'idle'; }

  async toggle() {
    if (this.listening()) {
      this.stop();
      return;
    }
    await this.start();
  }

  async start() {
    if (this.listening()) return;
    this.shouldListen = true;
    const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (Ctor) {
      this.startNative(Ctor);
      return;
    }
    await this.startServerFallback();
  }

  private startNative(Ctor: SpeechRecognitionCtor) {
    try {
      this.mode = 'native';
      this.recognition = new Ctor();
      this.recognition.continuous = true;
      this.recognition.interimResults = true;
      this.recognition.lang = 'en-US';
      this.recognition.onresult = (event) => {
        const latest = event.results[event.results.length - 1];
        const text = latest?.[0]?.transcript?.trim();
        if (latest?.isFinal && text) this.onFinal(text);
      };
      this.recognition.onerror = () => {
        this.status('STT native error; trying server fallback');
        this.stopNativeOnly();
        void this.startServerFallback();
      };
      this.recognition.onend = () => {
        if (this.shouldListen && this.mode === 'native') {
          try { this.recognition?.start(); } catch { /* Chrome can throw if restart is too soon. */ }
        }
      };
      this.recognition.start();
      this.status('STT listening native');
    } catch {
      this.stopNativeOnly();
      void this.startServerFallback();
    }
  }

  private async startServerFallback() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      this.mode = 'idle';
      this.shouldListen = false;
      this.status('STT unsupported in this browser');
      return;
    }
    try {
      this.mode = 'server';
      const source = this.getAudioSource?.();
      const liveAudio = source?.getAudioTracks().find((track) => track.readyState === 'live');
      let audioStream: MediaStream;
      if (liveAudio) {
        audioStream = new MediaStream([liveAudio]);
      } else {
        this.fallbackMic = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
          video: false,
        });
        audioStream = this.fallbackMic;
      }
      const mimeType = pickAudioMime();
      this.socket = new WebSocket(wsUrl('/ws/stt', this.room));
      this.socket.binaryType = 'arraybuffer';
      this.socket.onopen = () => {
        this.socket?.send(JSON.stringify({ type: 'config', mime_type: mimeType, language_code: 'en-US', chunk_ms: 3500 }));
        this.status('STT listening server');
        this.recorder = mimeType ? new MediaRecorder(audioStream, { mimeType }) : new MediaRecorder(audioStream);
        this.recorder.ondataavailable = async (event) => {
          if (!event.data.size || this.socket?.readyState !== WebSocket.OPEN) return;
          const buffer = await event.data.arrayBuffer();
          if (buffer.byteLength > 600) this.socket.send(buffer);
        };
        this.recorder.onerror = () => this.status('STT recorder error');
        this.recorder.start(3500);
      };
      this.socket.onmessage = (event) => {
        try {
          const message = JSON.parse(String(event.data)) as ServerSttMessage;
          if (message.type === 'transcript' && message.text?.trim()) this.onFinal(message.text.trim());
          else if (message.type === 'status' && message.status) this.status(`STT ${message.status}`);
          else if (message.type === 'error') this.status(`STT ${message.error ?? 'server error'}`);
        } catch {
          // Ignore non-JSON status frames.
        }
      };
      this.socket.onerror = () => this.status('STT server socket error');
      this.socket.onclose = () => {
        if (this.mode === 'server') this.status('STT server stopped');
      };
    } catch {
      this.mode = 'idle';
      this.shouldListen = false;
      this.status('STT server unavailable');
    }
  }

  private stopNativeOnly() {
    this.recognition?.stop();
    this.recognition = undefined;
  }

  stop() {
    this.shouldListen = false;
    this.stopNativeOnly();
    if (this.recorder?.state === 'recording') this.recorder.stop();
    this.recorder = undefined;
    this.socket?.close();
    this.socket = undefined;
    this.fallbackMic?.getTracks().forEach((track) => track.stop());
    this.fallbackMic = undefined;
    this.mode = 'idle';
    this.status('STT stopped');
  }
}
