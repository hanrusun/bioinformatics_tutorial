import type {
  BedsideData,
  ChatChoice,
  ChatSettingsData,
  ConsultData,
  Execution,
  Meta,
  MissionDetail,
  Note,
  NotebookData,
  Outcome,
  Snapshot,
} from './types';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  call<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  meta: () => call<Meta>('/api/meta'),
  state: (since: number) => call<Snapshot>(`/api/state?since=${since}`),
  start: (campaign: string, difficulty: string) => post<Snapshot>('/api/game/start', { campaign, difficulty }),
  abandon: () => post<Snapshot>('/api/game/abandon'),
  heartbeat: (visible: boolean, since: number) => post<Snapshot>('/api/heartbeat', { visible, since }),

  mission: (id: string) => call<MissionDetail>(`/api/missions/${id}`),
  startMission: (id: string) => post<{ ok: boolean; execution: Execution }>(`/api/missions/${id}/start`),
  run: (id: string, code: string, since: number) =>
    post<Snapshot & { execution: Execution; debug: string[] }>(`/api/missions/${id}/run`, { code, since }),
  submit: (id: string, code: string, since: number) =>
    post<Snapshot & { outcome: Outcome }>(`/api/missions/${id}/submit`, { code, since }),
  hint: (id: string, since: number) =>
    post<Snapshot & { tier: number; text: string }>(`/api/missions/${id}/hint?since=${since}`),
  debug: (id: string) => post<{ error: string; help: string[] }>(`/api/missions/${id}/debug`),

  answer: (quizId: string, choice: number, since: number) =>
    post<Snapshot & { correct: boolean }>(`/api/quizzes/${quizId}/answer`, { choice, since }),

  notebook: () => call<NotebookData>('/api/notebook'),
  openPage: (id: string) => post<{ token: string; min_read_seconds: number }>(`/api/notebook/pages/${id}/open`),
  readPage: (id: string, token: string, since: number) =>
    post<Snapshot>(`/api/notebook/pages/${id}/read`, { token, since }),
  createNote: (title: string, body: string, since: number) =>
    post<Snapshot & { note: Note }>('/api/notebook/notes', { title, body, since }),
  updateNote: (id: string, patch: { title?: string; body?: string }, since: number) =>
    call<Snapshot & { note: Note }>(`/api/notebook/notes/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ ...patch, since }),
    }),
  deleteNote: (id: string) => call<{ ok: boolean }>(`/api/notebook/notes/${id}`, { method: 'DELETE' }),
  exportUrl: (scope: 'all' | 'mine') => `/api/notebook/export?scope=${scope}`,
  scriptUrl: () => '/api/notebook/script',

  consultHistory: () => call<ConsultData>('/api/consult'),
  consultClear: () => post<ConsultData>('/api/consult/clear'),
  /** Save one exchange (the index of either of its messages) or, with no index, the whole conversation. */
  consultSave: (index: number | null, since: number) =>
    post<Snapshot & { note: Note }>('/api/consult/notebook', { index, since }),

  chatSettings: () => call<ChatSettingsData>('/api/chat/settings'),
  saveChatSettings: (patch: Partial<Record<'consult' | 'bedside', ChatChoice>>) =>
    call<ChatSettingsData>('/api/chat/settings', { method: 'PUT', body: JSON.stringify(patch) }),

  bedsideHistory: () => call<BedsideData>('/api/bedside'),
  bedsideClear: () => post<BedsideData>('/api/bedside/clear'),
  bedsideSave: (index: number | null, since: number) =>
    post<Snapshot & { note: Note }>('/api/bedside/notebook', { index, since }),
};

export interface ConsultQuestion {
  message: string;
  mission_id: string | null;
  code: string;
  include_code: boolean;
}

/** Ask the consulting doctor (see streamChat). */
export const consultAsk = (q: ConsultQuestion, onDelta: (text: string) => void) =>
  streamChat<ConsultData>('/api/consult', q, onDelta);

/** Say something to the patient (see streamChat). */
export const bedsideSay = (message: string, onDelta: (text: string) => void) =>
  streamChat<BedsideData>('/api/bedside', { message }, onDelta);

/**
 * POST a chat message. The answer streams back as server-sent events;
 * onDelta gets each piece, and the promise resolves with the saved
 * conversation (or rejects with the server's message).
 */
async function streamChat<T>(path: string, body: unknown, onDelta: (text: string) => void): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = typeof body.detail === 'string' ? body.detail : message;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let done: T | null = null;
  for (;;) {
    const { value, done: finished } = await reader.read();
    if (value) buffer += decoder.decode(value, { stream: true });
    let cut: number;
    while ((cut = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      let event = 'message';
      let data = '';
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) event = line.slice(7);
        else if (line.startsWith('data: ')) data += line.slice(6);
      }
      const payload = data ? JSON.parse(data) : {};
      if (event === 'delta') onDelta(payload.text ?? '');
      else if (event === 'error') throw new ApiError(502, payload.detail ?? 'The chat failed.');
      else if (event === 'done') done = payload as T;
    }
    if (finished) break;
  }
  if (!done) throw new ApiError(502, 'The chat was interrupted.');
  return done;
}
