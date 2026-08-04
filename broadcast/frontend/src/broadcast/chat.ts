import { JsonSocket, type BroadcastMessage } from './signaling';

function textOf(message: BroadcastMessage): string {
  const payload = message.payload && typeof message.payload === 'object' ? message.payload as Record<string, unknown> : {};
  return String(message.text ?? payload.text ?? message.type ?? 'message');
}

export class BroadcastChat {
  readonly socket: JsonSocket;
  constructor(private readonly log: HTMLElement, status: (line: string) => void) {
    this.socket = new JsonSocket('/ws/chat', (message) => this.add(message), status);
  }
  connect(room: string) { this.socket.connect(room); }
  send(text: string, name = 'Guest') { this.socket.send({ type: 'chat', text, name }); }
  sendTranscript(text: string) { this.socket.send({ type: 'stt', text, name: 'STT', final: true }); }
  requestAi() { this.socket.send({ type: 'ai' }); }
  sendUploadPlaceholder() { this.socket.send({ type: 'upload', metadata: { placeholder: true } }); }
  private add(message: BroadcastMessage) {
    if (message.family === 'presence') return;
    const line = document.createElement('div');
    line.className = 'chat-line';
    const name = message.name ? `${message.name}: ` : '';
    line.textContent = `${name}${textOf(message)}`;
    this.log.appendChild(line);
    this.log.scrollTop = this.log.scrollHeight;
  }
}
