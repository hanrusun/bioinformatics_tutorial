import { useEffect, useState } from 'preact/hooks';
import { api, consultAsk } from '../api';
import { draftKey, load, save } from '../lib/storage';
import type { ConsultStatus, GameView, MissionDetail, Snapshot } from '../types';
import { ChatActions, ChatThread, useChat } from './Chat';

interface Props {
  game: GameView;
  status: ConsultStatus;
  /** the mission selected on the Missions tab, if any */
  missionId: string | null;
  cursor: () => number;
  onSnapshot: (s: Snapshot) => void;
  onNotice: (text: string, tone?: 'info' | 'bad') => void;
}

// whether to send the editor code and last error along (remembered per browser)
const SHARE_KEY = 'curelab:consult-share';
const EXAMPLES = ['What is UMAP, mathematically?', 'Why do we log-normalize counts before PCA?', 'What does this error mean?'];

/** How to switch the chats on (shown by the consult and bedside tabs). */
export function ChatSetup({ id, title, what }: { id: string; title: string; what: string }) {
  return (
    <div class="consult consult--off" data-testid={`${id}-off`}>
      <h3>{title}</h3>
      <p>{what} It's switched off because no API key is set.</p>
      <ol>
        <li>
          Next to <code>docker-compose.yml</code>, create a file called <code>.env</code> with one line:{' '}
          <code>OPENAI_API_KEY=sk-…</code> (ChatGPT) or <code>ANTHROPIC_API_KEY=sk-ant-…</code> (Claude).
        </li>
        <li>
          Restart the game: <code>docker compose up -d seurat</code> (or <code>signac</code>).
        </li>
      </ol>
      <p class="muted">
        A ChatGPT Plus subscription can't be used by other apps: you need an API key from platform.openai.com or
        console.anthropic.com, which bills per message. The key stays on the game server; this page never sees it.
        The same key runs both chats: consulting another doctor and talking to the patient.
      </p>
    </div>
  );
}

export function ConsultPanel({ game, status, missionId, cursor, onSnapshot, onNotice }: Props) {
  const [share, setShare] = useState(load(SHARE_KEY) !== '0');
  const [about, setAbout] = useState<string | null>(missionId);
  const [detail, setDetail] = useState<MissionDetail | null>(null);
  const chat = useChat(
    { cursor, onSnapshot, onNotice, history: api.consultHistory, clear: api.consultClear, save: api.consultSave },
    [game.started_at, status.enabled],
  );

  const open = game.missions.filter((m) => m.status !== 'locked');
  const titleOf = (id: string | null) => {
    const i = game.missions.findIndex((m) => m.id === id);
    return i >= 0 ? `${i + 1}. ${game.missions[i].title}` : '';
  };

  useEffect(() => setAbout(missionId), [missionId]);
  useEffect(() => save(SHARE_KEY, share ? '1' : '0'), [share]);
  useEffect(() => {
    setDetail(null);
    if (about) api.mission(about).then(setDetail).catch(() => undefined);
  }, [about]);

  if (!status.enabled)
    return (
      <ChatSetup
        id="consult"
        title="Consult another doctor"
        what="Ask a chatbot colleague anything, at any point: about the mission you're on, your error, the maths behind a method, or biology beyond the game."
      />
    );

  const send = () =>
    chat.ask((q, onDelta) => {
      // the editor's current draft for that mission (or its starter code if untouched)
      const code = about ? (load(draftKey(game.campaign, about)) ?? detail?.starter_code ?? '') : '';
      return consultAsk({ message: q, mission_id: about, code, include_code: share }, onDelta);
    });

  return (
    <div class="consult" data-testid="consult">
      <header class="consult__head">
        <div>
          <h3>Consult another doctor</h3>
          <p class="muted">
            {status.label} ({status.model}) · free, but the clock keeps running · answers can be wrong, so check them
            against the vignettes
          </p>
        </div>
        <ChatActions chat={chat} id="consult" whole="whole consultation" />
      </header>

      <div class="consult__context">
        <label>
          About{' '}
          <select value={about ?? ''} onChange={(e) => setAbout((e.target as HTMLSelectElement).value || null)} data-testid="consult-about">
            <option value="">No mission (a general question)</option>
            {open.map((m) => (
              <option value={m.id}>
                {titleOf(m.id)}
                {m.status === 'completed' ? ' ✓' : ''}
              </option>
            ))}
          </select>
        </label>
        {about && (
          <label class="consult__share">
            <input type="checkbox" checked={share} onChange={(e) => setShare((e.target as HTMLInputElement).checked)} data-testid="consult-share" />{' '}
            share my code and last error
          </label>
        )}
        <span class="muted consult__shared">
          {about
            ? `The doctor sees this mission's briefing, task and vignette section${share ? ', your code and your last error' : ''}.`
            : 'The doctor sees which missions you have finished.'}
        </span>
      </div>

      <ChatThread
        chat={chat}
        id="consult"
        tone="doctor"
        meta={(m) => `You · day ${m.day}${m.mission_id ? ` · ${titleOf(m.mission_id)}` : ''}`}
        empty="Ask anything, at any point. For example:"
        examples={EXAMPLES}
        thinking="The doctor is thinking…"
        placeholder="Ask the consulting doctor…"
        sendLabel="Ask"
        onSend={send}
      />
    </div>
  );
}
