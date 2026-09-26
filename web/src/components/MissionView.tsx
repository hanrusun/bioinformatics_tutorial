import { useEffect, useRef, useState } from 'preact/hooks';
import { api, ApiError } from '../api';
import type { GameView, MissionDetail, Snapshot } from '../types';
import { draftKey, load, save, remove } from '../lib/storage';
import { CodeEditor } from './CodeEditor';
import { Console, type ConsoleEntry } from './Console';
import { Markdown } from './Markdown';

interface Props {
  missionId: string;
  game: GameView;
  cursor: () => number;
  language: string;
  onSnapshot: (s: Snapshot) => void;
  onOpenPage: (pageId: string) => void;
  onNotice: (text: string, tone?: 'info' | 'bad') => void;
}

type Busy = null | 'setup' | 'run' | 'submit' | 'hint' | 'debug';
type NewEntry = ConsoleEntry extends infer E ? (E extends ConsoleEntry ? Omit<E, 'id'> : never) : never;

let entryId = 1;

export function MissionView({ missionId, game, cursor, language, onSnapshot, onOpenPage, onNotice }: Props) {
  const [detail, setDetail] = useState<MissionDetail | null>(null);
  const [code, setCode] = useState('');
  const [codeVersion, setCodeVersion] = useState(0);
  const [busy, setBusy] = useState<Busy>(null);
  const [log, setLog] = useState<ConsoleEntry[]>([]);
  const prepared = useRef<string | null>(null);
  const summary = game.missions.find((m) => m.id === missionId);
  const completed = summary?.status === 'completed';
  const over = game.status !== 'playing';

  const push = (e: NewEntry) => setLog((l) => [...l.slice(-40), { ...e, id: entryId++ } as ConsoleEntry]);

  const prepare = async (reason: 'open' | 'reset') => {
    setBusy('setup');
    push({ kind: 'info', message: reason === 'open' ? 'Preparing the lab bench: fresh R session, loading this mission’s starting data…' : 'Resetting the bench…' });
    try {
      const res = await api.startMission(missionId);
      prepared.current = missionId;
      push({ kind: 'setup', ok: true, execution: res.execution, message: `Bench ready (${res.execution.elapsed.toFixed(1)}s). The clock was paused while it loaded.` });
    } catch (err) {
      prepared.current = null;
      push({ kind: 'setup', ok: false, message: `Could not prepare the bench: ${(err as Error).message}` });
    } finally {
      setBusy(null);
    }
  };

  // load mission detail + draft, then prepare the kernel
  useEffect(() => {
    let live = true;
    setDetail(null);
    setLog([]);
    api
      .mission(missionId)
      .then((d) => {
        if (!live) return;
        setDetail(d);
        setCode(load(draftKey(game.campaign, missionId)) ?? d.starter_code);
        setCodeVersion((v) => v + 1);
        if (d.status !== 'locked' && !over && prepared.current !== missionId) prepare('open');
      })
      .catch((err) => onNotice((err as Error).message, 'bad'));
    return () => {
      live = false;
    };
  }, [missionId]);

  const onChange = (value: string) => {
    setCode(value);
    save(draftKey(game.campaign, missionId), value);
  };

  const guard = (fn: () => Promise<void>) => async () => {
    if (busy || over) return;
    try {
      await fn();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : (err as Error).message;
      push({ kind: 'info', message: `⚠ ${msg}` });
    } finally {
      setBusy(null);
    }
  };

  const run = guard(async () => {
    setBusy('run');
    const res = await api.run(missionId, code, cursor());
    onSnapshot(res);
    push({ kind: 'run', execution: res.execution, debug: res.debug });
  });

  const submit = guard(async () => {
    if (completed) return;
    if (!code.trim()) {
      push({ kind: 'info', message: 'Write some code before submitting.' });
      return;
    }
    setBusy('submit');
    const res = await api.submit(missionId, code, cursor());
    onSnapshot(res);
    push({ kind: 'submit', outcome: res.outcome });
    if (res.outcome.passed) setDetail(await api.mission(missionId));
  });

  const hint = guard(async () => {
    setBusy('hint');
    const res = await api.hint(missionId, cursor());
    onSnapshot(res);
    setDetail(await api.mission(missionId));
  });

  const explain = guard(async () => {
    setBusy('debug');
    const res = await api.debug(missionId);
    push({ kind: 'debug', error: res.error, help: res.help });
  });

  const resetCode = () => {
    if (!detail) return;
    remove(draftKey(game.campaign, missionId));
    setCode(detail.starter_code);
    setCodeVersion((v) => v + 1);
  };

  if (!detail) return <div class="mission-view mission-view--loading">Loading mission…</div>;

  const nextHint = detail.hints.length;
  const canBuy = nextHint < detail.hint_total && game.rp >= detail.hint_cost && !over;

  return (
    <div class="mission-view" data-mission-view={missionId}>
      <header class="mission-head">
        <div>
          <h2>{detail.title}</h2>
          <a class="source" href={detail.source.site_url} target="_blank" rel="noopener noreferrer" title={`Pinned: ${detail.source.pinned_url}`}>
            📖 {detail.source.vignette.replace(/\.Rmd$/, '')} › {detail.source.section}
          </a>
        </div>
        <span class={`pts${completed ? ' pts--done' : ''}`}>{completed ? `✓ +${detail.points}%` : `+${detail.points}% cure`}</span>
      </header>

      <div class="mission-body">
        <section class="brief">
          <Markdown src={detail.briefing} />
          <h3>Your task</h3>
          <ul class="tasks">
            {detail.task.map((t) => (
              <li>
                <Markdown src={t} class="md--inline" />
              </li>
            ))}
          </ul>
          {detail.notebook_pages.length > 0 && (
            <p class="nb-links">
              Notebook:{' '}
              {detail.notebook_pages.map((p) => (
                <button class="link" onClick={() => onOpenPage(p.id)}>
                  {p.title}
                </button>
              ))}
            </p>
          )}
          <div class="hints">
            {detail.hints.map((h, i) => (
              <div class="hint" key={i}>
                <span class="hint__tier">Hint {i + 1}</span>
                <Markdown src={h} />
              </div>
            ))}
          </div>
        </section>

        <section class="workbench">
          <CodeEditor value={code} version={codeVersion} language={language} onChange={onChange} onRun={run} onSubmit={submit} />
          <div class="toolbar">
            <button class="btn btn--run" onClick={run} disabled={!!busy || over} title="Run your code (free, not graded). Ctrl/⌘+Enter">
              {busy === 'run' ? 'Running…' : '▶ Run'}
            </button>
            <button
              class="btn btn--submit"
              onClick={submit}
              disabled={!!busy || completed || over}
              title="Submit for grading. A wrong answer makes the disease evolve. Ctrl/⌘+Shift+Enter"
            >
              {completed ? 'Completed' : busy === 'submit' ? 'Grading…' : '✔ Submit'}
            </button>
            <button
              class="btn btn--hint"
              onClick={hint}
              disabled={!!busy || !canBuy}
              title={
                nextHint >= detail.hint_total
                  ? 'All hints revealed'
                  : game.rp < detail.hint_cost
                    ? 'Not enough research points. Read notebook pages or write notes to earn RP.'
                    : `Reveal hint ${nextHint + 1} for ${detail.hint_cost} RP`
              }
            >
              💡 Hint {Math.min(nextHint + 1, detail.hint_total)}/{detail.hint_total}
              {nextHint < detail.hint_total && <span class="cost">−{detail.hint_cost} RP</span>}
            </button>
            <button class="btn" onClick={explain} disabled={!!busy} title="Explain the last error (free)">
              🩺 Explain error
            </button>
            <span class="toolbar__spacer" />
            <button class="btn btn--ghost" onClick={resetCode} disabled={!!busy} title="Restore the starter code">
              ↺ Starter code
            </button>
            <button class="btn btn--ghost" onClick={() => prepare('reset')} disabled={!!busy || over} title="Fresh R session with this mission’s starting data">
              ⟲ Reset bench
            </button>
          </div>
          {busy === 'setup' && <div class="busy">Loading the mission’s starting data…</div>}
          <Console entries={log} />
        </section>
      </div>
    </div>
  );
}
