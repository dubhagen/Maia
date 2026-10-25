import { BrowserWindow } from 'electron'

// Desktop auto-update is removed. These exports stay so the existing IPC
// handlers in index.ts keep a target. They never contact a feed.

export type UpdateStatus =
  | { state: 'checking' }
  | { state: 'available'; version: string; notes?: string; userInitiated?: boolean }
  | { state: 'not-available' }
  | { state: 'downloading'; percent: number }
  | { state: 'downloaded'; version: string }
  | { state: 'error'; message: string }

let getWindow: () => BrowserWindow | null = () => null

function emitNotAvailable(): void {
  getWindow()?.webContents.send('update-status', { state: 'not-available' })
}

export function setUpdateLanguage(_lang: string | undefined): void {}

export function setUpdateFeedQuery(_params: unknown): void {}

export function initUpdater(windowGetter: () => BrowserWindow | null): void {
  getWindow = windowGetter
}

export function checkForUpdates(_userInitiated = false): void {
  emitNotAvailable()
}

export function startDownload(): void {
  emitNotAvailable()
}

export function quitAndInstall(): void {}
