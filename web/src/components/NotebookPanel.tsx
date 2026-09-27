import { useEffect, useRef, useState } from 'preact/hooks';
import { api, ApiError } from '../api';
import type { GameView, Meta, NotebookData, NotebookPage, Snapshot } from '../types';
import { copyText, downloadFrom, fetchText } from '../lib/files';
import { wordCount } from '../lib/format';
import { Markdown } from './Markdown';

interface Props {
  game: GameView;
  rules: Meta['rules'];
  cursor: () => number;
  focus: string | null;
  onSnapshot: (s: Snapshot) => void;
  onNotice: (text: string, tone?: 'info' | 'bad') => void;
}

type Selection = { kind: 'page'; id: string } | { kind: 'note'; id: string } | null;

export function ExportButtons({ onNotice, compact }: { onNotice: Props['onNotice']; compact?: boolean }) {
  const copyMine = async () => {
    try {
      const text = await fetchText(api.exportUrl('mine'));
      onNotice((await copyText(text)) ? 'Your notes are on the clipboard.' : 'Copy failed. Use the download instead.', 'info');
    } catch (err) {
      onNotice(String(err), 'bad');
    }
  };
  const download = (scope: 'all' | 'mine') => async () => {
    try {
      await downloadFrom(api.exportUrl(scope), scope === 'all' ? 'curelab-notebook.md' : 'curelab-my-notes.md');
    } catch (err) {
      onNotice(String(err), 'bad');
    }
  };
  return (
    <div class={`export${compact ? ' export--compact' : ''}`}>
      <button class="btn" onClick={copyMine} data-testid="copy-notes">
        📋 Copy my notes
      </button>
      <button class="btn" onClick={download('mine')} data-testid="download-mine">
        ⬇ My notes (.md)
      </button>
      <button class="btn" onClick={download('all')} data-testid="download-all">
        ⬇ Whole notebook (.md)
      </button>
    </div>
  );
}

function PageView({
  page,
  game,
  rules,
  cursor,
  onSnapshot,
  onNotice,
  onRead,
}: {
  page: NotebookPage;
  game: GameView;
  rules: Meta['rules'];
  cursor: () => number;
  onSnapshot: Props['onSnapshot'];
  onNotice: Props['onNotice'];
  onRead: () => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const [token, setToken] = useState<string | null>(null);
  const [openedAt, setOpenedAt] = useState(0);
  const [atBottom, setAtBottom] = useState(false);
  const [now, setNow] = useState(Date.now());
  const read = game.pages_read.includes(page.id);

  useEffect(() => {
    setAtBottom(false);
    setToken(null);
    scroller.current?.scrollTo({ top: 0 });
    if (read || game.status !== 'playing') return;
    api.openPage(page.id).then((r) => {
      setToken(r.token);
      setOpenedAt(Date.now());
    });
    // a short page is "scrolled to the bottom" as soon as it renders
    requestAnimationFrame(() => checkBottom());
  }, [page.id]);

  useEffect(() => {
    if (read) return;
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, [read]);

  const checkBottom = () => {
    const el = scroller.current;
    if (el && el.scrollTop + el.clientHeight >= el.scrollHeight - 12) setAtBottom(true);
  };

  const waitLeft = Math.max(0, Math.ceil(rules.min_read_seconds - (now - openedAt) / 1000));
  const canRead = !read && token && atBottom && waitLeft === 0 && game.status === 'playing';

  const markRead = async () => {
    if (!canRead || !token) return;
    try {
      onSnapshot(await api.readPage(page.id, token, cursor()));
      onRead();
    } catch (err) {
      onNotice(err instanceof ApiError ? err.message : String(err), 'bad');
    }
  };

  return (
    <div class="page" ref={scroller} onScroll={checkBottom} data-page={page.id}>
      <h2>{page.title}</h2>
      {page.blocks.map((b, i) => (
        <div key={i} class={`block block--${b.kind}`}>
          {b.kind === 'text' && <Markdown src={b.text} />}
          {b.kind === 'quote' && (
            <blockquote>
              <Markdown src={b.text} />
            </blockquote>
          )}
          {b.kind === 'code' && (
            <div class="codeblock">
              <pre>
                <code>{b.text}</code>
              </pre>
              <button class="copy" onClick={async () => onNotice((await copyText(b.text)) ? 'Code copied.' : 'Copy failed.', 'info')}>
                Copy
              </button>
            </div>
          )}
          {b.source && (
            <cite class="block__src">
              <a href={b.source.site_url} target="_blank" rel="noopener noreferrer">
                {b.source.vignette.replace(/\.Rmd$/, '')} › {b.source.section}
              </a>{' '}
              ·{' '}
              <a href={b.source.pinned_url} target="_blank" rel="noopener noreferrer">
                pinned {b.source.repo ? `${b.source.repo}@` : ''}{b.source.ref}
              </a>
            </cite>
          )}
        </div>
      ))}
      <div class="read-row">
        {read ? (
          <span class="read-done" data-testid="page-read">✓ Read</span>
        ) : (
          <button class="btn btn--read" disabled={!canRead} onClick={markRead} data-testid="mark-read">
            ✓ Read <span class="cost cost--plus">+{page.rp} RP</span>
          </button>
        )}
        {!read && !atBottom && <span class="muted">Scroll to the end of the page to finish reading.</span>}
        {!read && atBottom && waitLeft > 0 && <span class="muted">{waitLeft}s…</span>}
      </div>
    </div>
  );
}

export function NotebookPanel({ game, rules, cursor, focus, onSnapshot, onNotice }: Props) {
  const [data, setData] = useState<NotebookData | null>(null);
  const [sel, setSel] = useState<Selection>(null);
  const [draft, setDraft] = useState<{ title: string; body: string }>({ title: '', body: '' });
  const [preview, setPreview] = useState(false);
  const saveTimer = useRef<number | undefined>(undefined);

  const refresh = async () => {
    const d = await api.notebook();
    setData(d);
    return d;
  };

  useEffect(() => {
    refresh().then((d) => {
      if (focus && d.pages.some((p) => p.id === focus)) setSel({ kind: 'page', id: focus });
      else if (!sel && d.pages.length) setSel({ kind: 'page', id: d.pages[0].id });
    });
  }, [focus]);

  const note = sel?.kind === 'note' ? data?.notes.find((n) => n.id === sel.id) : undefined;
  useEffect(() => {
    if (note) setDraft({ title: note.title, body: note.body });
  }, [sel?.kind === 'note' ? sel.id : null]);

  const newNote = async () => {
    try {
      const res = await api.createNote('', '', cursor());
      onSnapshot(res);
      await refresh();
      setSel({ kind: 'note', id: res.note.id });
      setPreview(false);
    } catch (err) {
      onNotice(String(err), 'bad');
    }
  };

  const scheduleSave = (next: { title: string; body: string }) => {
    setDraft(next);
    if (sel?.kind !== 'note') return;
    const id = sel.id;
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(async () => {
      try {
        const res = await api.updateNote(id, next, cursor());
        onSnapshot(res);
        setData((d) => (d ? { ...d, notes: d.notes.map((n) => (n.id === id ? res.note : n)) } : d));
      } catch (err) {
        onNotice(String(err), 'bad');
      }
    }, 700);
  };

  const deleteNote = async () => {
    if (sel?.kind !== 'note' || !window.confirm('Delete this page of notes?')) return;
    await api.deleteNote(sel.id);
    const d = await refresh();
    setSel(d.pages.length ? { kind: 'page', id: d.pages[0].id } : null);
  };

  if (!data) return <div class="notebook">Opening the notebook…</div>;
  const page = sel?.kind === 'page' ? data.pages.find((p) => p.id === sel.id) : undefined;
  const words = wordCount(draft.body);

  return (
    <div class="notebook">
      <nav class="notebook__index" aria-label="Notebook pages">
        <h3>From the vignettes</h3>
        <ul>
          {data.pages.map((p) => {
            const read = game.pages_read.includes(p.id);
            return (
              <li key={p.id}>
                <button class={`nb-item${sel?.kind === 'page' && sel.id === p.id ? ' is-selected' : ''}`} onClick={() => setSel({ kind: 'page', id: p.id })}>
                  <span class={`nb-item__mark${read ? ' is-read' : ''}`}>{read ? '✓' : `+${p.rp}`}</span>
                  {p.title}
                </button>
              </li>
            );
          })}
        </ul>
        <h3>My pages</h3>
        <ul>
          {data.notes.map((n) => (
            <li key={n.id}>
              <button class={`nb-item${sel?.kind === 'note' && sel.id === n.id ? ' is-selected' : ''}`} onClick={() => setSel({ kind: 'note', id: n.id })}>
                <span class={`nb-item__mark${n.qualifies ? ' is-read' : ''}`}>✎</span>
                {n.title}
              </button>
            </li>
          ))}
        </ul>
        <button class="btn btn--wide" onClick={newNote} data-testid="new-note">
          + New page
        </button>
        <p class="fine">
          Your pages earn +{rules.note_rp} RP once they reach {rules.note_min_words} words, up to one page per mission you
          have attempted ({game.notes.awarded}/{game.notes.cap} earned so far).
        </p>
        <ExportButtons onNotice={onNotice} compact />
      </nav>

      <div class="notebook__page">
        {page && (
          <PageView
            page={page}
            game={game}
            rules={rules}
            cursor={cursor}
            onSnapshot={onSnapshot}
            onNotice={onNotice}
            onRead={() => undefined}
          />
        )}
        {note && (
          <div class="note-editor" data-note={note.id}>
            <input
              class="note-editor__title"
              value={draft.title}
              aria-label="Page title"
              onInput={(e) => scheduleSave({ ...draft, title: (e.target as HTMLInputElement).value })}
            />
            <div class="note-editor__bar">
              <button class={`tab${!preview ? ' is-active' : ''}`} onClick={() => setPreview(false)}>
                Write
              </button>
              <button class={`tab${preview ? ' is-active' : ''}`} onClick={() => setPreview(true)}>
                Preview
              </button>
              <span class="toolbar__spacer" />
              <span class={`words${words >= rules.note_min_words ? ' words--ok' : ''}`} data-testid="word-count">
                {words}/{rules.note_min_words} words
              </span>
              <button class="btn btn--ghost" onClick={deleteNote}>
                Delete
              </button>
            </div>
            {preview ? (
              <Markdown src={draft.body || '*Nothing written yet.*'} class="note-editor__preview" />
            ) : (
              <textarea
                class="note-editor__body"
                value={draft.body}
                placeholder="Write what you learned, in your own words. Markdown works: **bold**, `code`, lists…"
                onInput={(e) => scheduleSave({ ...draft, body: (e.target as HTMLTextAreaElement).value })}
                data-testid="note-body"
              />
            )}
          </div>
        )}
        {!page && !note && <p class="muted">Pick a page.</p>}
      </div>
    </div>
  );
}
