export type BroadcastMessage = {
  family?: string;
  type: string;
  room?: string;
  text?: string;
  name?: string;
  payload?: any;
  viewer_id?: string;
  [key: string]: unknown;
};

export class JsonSocket {
  private socket?: WebSocket;
  private queue: BroadcastMessage[] = [];
  private room = 'default';
  private reconnectTimer?: number;
  private closedByUser = false;

  constructor(
    private readonly path: string,
    private readonly onMessage: (message: BroadcastMessage) => void,
    private readonly onStatus: (status: string) => void,
    private readonly onOpen?: () => void,
  ) {}

  connect(room = 'default') {
    this.room = room;
    this.closedByUser = false;
    this.openSocket();
  }

  private openSocket() {
    window.clearTimeout(this.reconnectTimer);
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    this.socket = new WebSocket(`${proto}://${window.location.host}${this.path}?room=${encodeURIComponent(this.room)}`);
    this.socket.onopen = () => {
      this.onStatus('connected');
      this.queue.splice(0).forEach((message) => this.send(message));
      this.onOpen?.();
    };
    this.socket.onclose = () => {
      this.onStatus('offline');
      if (!this.closedByUser) this.reconnectTimer = window.setTimeout(() => this.openSocket(), 1500);
    };
    this.socket.onerror = () => this.onStatus('connection error');
    this.socket.onmessage = (event) => {
      try { this.onMessage(JSON.parse(event.data)); }
      catch { this.onStatus('message error'); }
    };
  }

  send(message: BroadcastMessage) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
      return;
    }
    this.queue.push(message);
  }

  close() {
    this.closedByUser = true;
    window.clearTimeout(this.reconnectTimer);
    this.socket?.close();
  }
}
