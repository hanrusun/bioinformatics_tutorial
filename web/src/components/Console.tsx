import { useEffect, useRef } from 'preact/hooks';
import type { Execution, Outcome } from '../types';

export type ConsoleEntry =
  | { id: number; kind: 'setup'; ok: boolean; execution?: Execution; message: string }
  | { id: number; kind: 'run'; execution: Execution; debug: string[] }
  | { id: number; kind: 'submit'; outcome: Outcome }
  | { id: number; kind: 'debug'; error: string; help: string[] }
  | { id: number; kind: 'info'; message: string };

function ExecOutput({ execution }: { execution: Execution }) {
  return (
    <>
      {execution.stdout && <pre class="out out--stdout">{execution.stdout}</pre>}
      {execution.results.map((r) => (
        <pre class="out out--result">{r}</pre>
      ))}
      {execution.images.map((img) => (
        <img class="out out--plot" src={`data:image/png;base64,${img}`} alt="Plot output" />
      ))}
      {execution.stderr && <pre class="out out--stderr">{execution.stderr}</pre>}
      {execution.error && (
        <div class="out out--error">
          <strong>{execution.error.ename === 'ERROR' ? 'Error' : execution.error.ename}</strong>{' '}
          <span>{execution.error.evalue}</span>
          {execution.error.traceback.length > 0 && (
            <details>
              <summary>Traceback</summary>
              <pre>{execution.error.traceback.join('\n')}</pre>
            </details>
          )}
        </div>
      )}
    </>
  );
}

function Help({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <div class="out out--help">
      <strong>Debugging help</strong>
      <ul>
        {items.map((h) => (
          <li>{h}</li>
        ))}
      </ul>
    </div>
  );
}

export function Console({ entries }: { entries: ConsoleEntry[] }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => end.current?.scrollIntoView({ block: 'end' }), [entries.length]);
  return (
    <div class="console" aria-live="polite">
      {entries.length === 0 && <p class="console__empty">Output appears here. Run is free; Submit is graded.</p>}
      {entries.map((e) => (
        <div key={e.id} class={`entry entry--${e.kind}`}>
          {e.kind === 'setup' && (
            <div class={`banner ${e.ok ? 'banner--info' : 'banner--bad'}`}>{e.message}</div>
          )}
          {e.kind === 'info' && <div class="banner banner--info">{e.message}</div>}
          {e.kind === 'run' && (
            <>
              <div class="entry__label">▶ Run <span class="muted">({e.execution.elapsed.toFixed(1)}s, not graded)</span></div>
              <ExecOutput execution={e.execution} />
              <Help items={e.debug} />
            </>
          )}
          {e.kind === 'submit' && (
            <>
              <div class="entry__label">✔ Submit <span class="muted">({e.outcome.execution.elapsed.toFixed(1)}s)</span></div>
              <ExecOutput execution={e.outcome.execution} />
              <div
                class={`banner ${e.outcome.passed ? 'banner--good' : e.outcome.graded ? 'banner--bad' : 'banner--warn'}`}
                data-testid="submit-result"
              >
                {e.outcome.passed ? '✓ ' : e.outcome.graded ? '✗ ' : '⏱ '}
                {e.outcome.message}
                {!e.outcome.passed && e.outcome.graded && <span class="banner__sub"> The disease evolves…</span>}
                {!e.outcome.graded && <span class="banner__sub"> Not counted as a mistake.</span>}
              </div>
              <Help items={e.outcome.debug} />
            </>
          )}
          {e.kind === 'debug' && (
            <div class="out out--help">
              <strong>🩺 Error explained</strong>
              {e.error ? <pre class="out out--stderr">{e.error}</pre> : <p>No error to explain yet. Run or submit something first.</p>}
              {e.help.length ? (
                <ul>
                  {e.help.map((h) => (
                    <li>{h}</li>
                  ))}
                </ul>
              ) : (
                e.error && <p>No specific advice for this one. Compare your code with the task list and the notebook page.</p>
              )}
            </div>
          )}
        </div>
      ))}
      <div ref={end} />
    </div>
  );
}
