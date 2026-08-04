export function bindUploadPlaceholder(button: HTMLButtonElement, onStatus: (line: string) => void, onUpload: () => void) {
  button.onclick = () => { onStatus('Upload hook placeholder: no file is sent in pass #9.'); onUpload(); };
}
