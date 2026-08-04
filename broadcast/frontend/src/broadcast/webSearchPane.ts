export function bindWebSearchPlaceholder(button: HTMLButtonElement, onStatus: (line: string) => void) {
  button.onclick = () => onStatus('Web/search pane placeholder: disabled until a future pass.');
}
