// localStorage is only used for per-viewer conveniences (editor drafts, the
// last tab). It can be unavailable (private windows, blocked storage), so
// every access is guarded and the app works without it.

export function load(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function save(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

export function remove(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

export const draftKey = (campaign: string, mission: string) => `curelab:draft:${campaign}:${mission}`;
