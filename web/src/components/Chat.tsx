import type { ComponentChildren } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import type { ConsultMessage, Note, Snapshot } from '../types';
import { Markdown } from './Markdown';

// Shared by "consult another doctor" and the bedside chat with the patient:
// the conversation, the streaming answer, and the notebook / clear buttons.

type Pending = { question: string; answer: string };
type Saved = { messages: ConsultMessage[] };

interface ChatOptions {
  cursor: () => number;
  onSnapshot: (s: Snapshot) => void;
  onNotice: (text: string, tone?: 'info' | 'bad') => void;
  /** load the saved conversation */
  history: () => Promise<Saved>;
  clear: () => Promise<Saved>;
  /** save one exchange (a message index) or, with null, the whole chat */
  save: (index: number | null, since: number) => Promise<Snapshot & { note: Note }>;
}

export function useChat({ cursor, onSnapshot, onNotice, history, clear, save }: ChatOptions, reloadOn: unknown[]) {
  const [messages, setMessages] = useState<ConsultMessage[]>([]);
  const [question, setQuestion] = useState('');
  const [pending, setPending] = useState<Pending | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    history()
      .then((d) => setMessages(d.messages))
      .catch((e) => onNotice(String(e), 'bad'));
  }, reloadOn);

  /** send the typed question (or `text`) and stream the answer in */
  const ask = async (send: (q: string, onDelta: (piece: string) => void) => Promise<Saved>, text?: string) => {
    const q = (text ?? question).trim();
    if (!q || pending) return;
    setPending({ question: q, answer: '' });
    setQuestion('');
    try {
      const data = await send(q, (piece) => setPending((p) => (p ? { ...p, answer: p.answer + piece } : p)));
      setMessages(data.messages);
    } catch (err) {
      setQuestion(q); // give it back so it can be sent again
      onNotice((err as Error).message, 'bad');
    } finally {
      setPending(null);
    }
  };

  const addToNotebook = async (index: number | null) => {
    try {
      const res = await save(index, cursor());
      onSnapshot(res);
      onNotice(`Added “${res.note.title}” to the lab notebook (chats earn no RP).`, 'info');
    } catch (err) {
      onNotice((err as Error).message, 'bad');
    }
  };

  const clearAll = async () => {
    if (!confirmClear) {
      setConfirmClear(true);
      setTimeout(() => setConfirmClear(false), 4000);
      return;
    }
    setConfirmClear(false);
    try {
      setMessages((await clear()).messages);
    } catch (err) {
      onNotice((err as Error).message, 'bad');
    }
  };

  return { messages, question, setQuestion, pending, ask, addToNotebook, clearAll, confirmClear };
}

export type Chat = ReturnType<typeof useChat>;

/** "Add whole … to notebook" and "Clear" for a chat's header. */
export function ChatActions({ chat, id, whole }: { chat: Chat; id: string; whole: string }) {
  const busy = !chat.messages.length || !!chat.pending;
  return (
    <div class="consult__actions">
      <button class="btn btn--ghost" onClick={() => chat.addToNotebook(null)} disabled={busy} data-testid={`${id}-save-all`}>
        📓 Add {whole} to notebook
      </button>
      <button class="btn btn--ghost" onClick={chat.clearAll} disabled={busy} data-testid={`${id}-clear`}>
        {chat.confirmClear ? 'Really clear?' : 'Clear'}
      </button>
    </div>
  );
}

interface ThreadProps {
  chat: Chat;
  /** test-id prefix: "consult" or "bedside" */
  id: string;
  /** the answering bubble's style and (optional) name line */
  tone: 'doctor' | 'patient';
  who?: string;
  meta: (m: ConsultMessage) => string;
  empty: ComponentChildren;
  examples: string[];
  thinking: string;
  placeholder: string;
  sendLabel: string;
  onSend: () => void;
  /** set when nobody can answer any more: replaces the input */
  closed?: ComponentChildren;
}

/** The conversation, the streaming answer and the input box. */
export function ChatThread(props: ThreadProps) {
  const { chat, id, tone, who, meta, empty, examples, thinking, placeholder, sendLabel, onSend, closed } = props;
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => endRef.current?.scrollIntoView?.({ block: 'end' }), [chat.messages.length, chat.pending?.answer]);
  const { messages, pending } = chat;
  return (
    <>
      <div class="consult__log" data-testid={`${id}-log`}>
        {!messages.length && !pending && (
          <div class="consult__empty">
            <p class="muted">{empty}</p>
            {!closed &&
              examples.map((ex) => (
                <button class="btn btn--ghost" onClick={() => chat.setQuestion(ex)}>
                  {ex}
                </button>
              ))}
          </div>
        )}
        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div class="bubble bubble--me" key={i}>
              <div class="bubble__meta">{meta(m)}</div>
              <p>{m.text}</p>
            </div>
          ) : (
            <div class={`bubble bubble--${tone}`} key={i} data-testid={`${id}-answer`}>
              {who && <div class="bubble__meta">{who}</div>}
              <Markdown src={m.text} />
              <button class="btn btn--ghost btn--tiny" onClick={() => chat.addToNotebook(i)} disabled={!!pending} data-testid={`${id}-save`}>
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
            <div class={`bubble bubble--${tone} bubble--pending`} data-testid={`${id}-pending`}>
              {who && <div class="bubble__meta">{who}</div>}
              {pending.answer ? <Markdown src={pending.answer} /> : <p class="muted">{thinking}</p>}
            </div>
          </>
        )}
        <div ref={endRef} />
      </div>

      {closed ? (
        <p class="consult__closed muted" data-testid={`${id}-closed`}>
          {closed}
        </p>
      ) : (
        <div class="consult__ask">
          <textarea
            value={chat.question}
            placeholder={`${placeholder} (Ctrl/⌘+Enter to send)`}
            onInput={(e) => chat.setQuestion((e.target as HTMLTextAreaElement).value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                onSend();
              }
            }}
            rows={3}
            data-testid={`${id}-input`}
          />
          <button class="btn btn--primary" onClick={onSend} disabled={!chat.question.trim() || !!pending} data-testid={`${id}-ask`}>
            {pending ? 'Waiting…' : sendLabel}
          </button>
        </div>
      )}
    </>
  );
}
