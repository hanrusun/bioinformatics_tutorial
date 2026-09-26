import type {
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
};
