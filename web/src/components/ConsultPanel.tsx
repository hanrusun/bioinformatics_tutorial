import { useEffect, useRef, useState } from 'preact/hooks';
import { api, consultAsk } from '../api';
import { draftKey, load, save } from '../lib/storage';
import type { ConsultMessage, ConsultStatus, GameView, MissionDetail, Snapshot } from '../types';
import { Markdown } from './Markdown';

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

function Setup() {
  return (
    <div class="consult consult--off" data-testid="consult-off">
      <h3>Consult another doctor</h3>
      <p>
        Ask a chatbot colleague anything, at any point: about the mission you're on, your error, the maths behind a
        method, or biology beyond the game. It's switched off because no API key is set.
      </p>
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
        console.anthropic.com, which bills per question. The key stays on the game server; this page never sees it.
      </p>
    </div>
  );
}

export function ConsultPanel({ game, status, missionId, cursor, onSnapshot, onNotice }: Props) {
  const [messages, setMessages] = useState<ConsultMessage[]>([]);
  const [question, setQuestion] = useState('');
  const [pending, setPending] = useState<{ question: string; answer: string } | null>(null);
  const [share, setShare] = useState(load(SHARE_KEY) !== '0');
  const [about, setAbout] = useState<string | null>(missionId);
  const [detail, setDetail] = useState<MissionDetail | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const open = game.missions.filter((m) => m.status !== 'locked');
  const titleOf = (id: string | null) => {
    const i = game.missions.findIndex((m) => m.id === id);
    return i >= 0 ? `${i + 1}. ${game.missions[i].title}` : '';
  };

  useEffect(() => setAbout(missionId), [missionId]);
  useEffect(() => save(SHARE_KEY, share ? '1' : '0'), [share]);
  useEffect(() => {
    if (!status.enabled) return;
    api
      .consultHistory()
      .then((d) => setMessages(d.messages))
      .catch((e) => onNotice(String(e), 'bad'));
  }, [game.started_at, status.enabled]);
  useEffect(() => {
    setDetail(null);
    if (about) api.mission(about).then(setDetail).catch(() => undefined);
  }, [about]);
  useEffect(() => endRef.current?.scrollIntoView?.({ block: 'end' }), [messages.length, pending?.answer]);

  if (!status.enabled) return <Setup />;

  const ask = async (text?: string) => {
    const q = (text ?? question).trim();
    if (!q || pending) return;
    // the editor's current draft for that mission (or its starter code if untouched)
    const code = about ? (load(draftKey(game.campaign, about)) ?? detail?.starter_code ?? '') : '';
    setPending({ question: q, answer: '' });
    setQuestion('');
    try {
      const data = await consultAsk({ message: q, mission_id: about, code, include_code: share }, (piece) =>
        setPending((p) => (p ? { ...p, answer: p.answer + piece } : p)),
      );
      setMessages(data.messages);
    } catch (err) {
      setQuestion(q); // give the question back so it can be asked again
      onNotice((err as Error).message, 'bad');
    } finally {
      setPending(null);
    }
  };

  const addToNotebook = async (index: number | null) => {
    try {
      const res = await api.consultSave(index, cursor());
      onSnapshot(res);
      onNotice(`Added “${res.note.title}” to the lab notebook (consultations earn no RP).`, 'info');
    } catch (err) {
      onNotice((err as Error).message, 'bad');
    }
  };

  const clear = async () => {
    if (!confirmClear) {
      setConfirmClear(true);
      setTimeout(() => setConfirmClear(false), 4000);
      return;
    }
    setConfirmClear(false);
    try {
      setMessages((await api.consultClear()).messages);
    } catch (err) {
      onNotice((err as Error).message, 'bad');
    }
  };

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
        <div class="consult__actions">
          <button class="btn btn--ghost" onClick={() => addToNotebook(null)} disabled={!messages.length || !!pending} data-testid="consult-save-all">
            📓 Add whole consultation to notebook
          </button>
          <button class="btn btn--ghost" onClick={clear} disabled={!messages.length || !!pending} data-testid="consult-clear">
            {confirmClear ? 'Really clear?' : 'Clear'}
          </button>
        </div>
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

      <div class="consult__log" data-testid="consult-log">
        {!messages.length && !pending && (
          <div class="consult__empty">
            <p class="muted">Ask anything, at any point. For example:</p>
            {EXAMPLES.map((ex) => (
              <button class="btn btn--ghost" onClick={() => setQuestion(ex)}>
                {ex}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div class="bubble bubble--me" key={i}>
              <div class="bubble__meta">
                You · day {m.day}
                {m.mission_id ? ` · ${titleOf(m.mission_id)}` : ''}
              </div>
              <p>{m.text}</p>
            </div>
          ) : (
            <div class="bubble bubble--doctor" key={i} data-testid="consult-answer">
              <Markdown src={m.text} />
              <button class="btn btn--ghost btn--tiny" onClick={() => addToNotebook(i)} disabled={!!pending} data-testid="consult-save">
                📓 Add to notebook
              </button>
            </div>
          ),
        )}
        {pending && (
          <>
            <div class="bubble bubble--me">
              <div class="bubble__meta">You</div>
              <p>{pending.question}</p>
            </div>
            <div class="bubble bubble--doctor bubble--pending" data-testid="consult-pending">
              {pending.answer ? <Markdown src={pending.answer} /> : <p class="muted">The doctor is thinking…</p>}
            </div>
          </>
        )}
        <div ref={endRef} />
      </div>

      <div class="consult__ask">
        <textarea
          value={question}
          placeholder="Ask the consulting doctor… (Ctrl/⌘+Enter to send)"
          onInput={(e) => setQuestion((e.target as HTMLTextAreaElement).value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              ask();
            }
          }}
          rows={3}
          data-testid="consult-input"
        />
        <button class="btn btn--primary" onClick={() => ask()} disabled={!question.trim() || !!pending} data-testid="consult-ask">
          {pending ? 'Waiting…' : 'Ask'}
        </button>
      </div>
    </div>
  );
}
