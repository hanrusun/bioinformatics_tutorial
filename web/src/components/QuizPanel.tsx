import { useState } from 'preact/hooks';
import { api, ApiError } from '../api';
import type { GameView, Snapshot } from '../types';

interface Props {
  game: GameView;
  cursor: () => number;
  onSnapshot: (s: Snapshot) => void;
}

export function QuizPanel({ game, cursor, onSnapshot }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const titles = Object.fromEntries(game.missions.map((m, i) => [m.id, `${i + 1}. ${m.title}`]));
  const available = game.quizzes.filter((q) => q.status === 'available').length;
  const done = game.quizzes.filter((q) => q.status === 'completed').length;

  const answer = async (quizId: string, choice: number) => {
    if (busy || game.status !== 'playing') return;
    setBusy(quizId);
    setError(null);
    try {
      onSnapshot(await api.answer(quizId, choice, cursor()));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div class="quiz-panel">
      <p class="panel-intro">
        Journal club: questions drawn word for word from the Seurat vignettes. Each correct answer adds{' '}
        <strong>+1% cure</strong>. Unlimited tries, but every wrong answer lets the disease evolve.{' '}
        <span class="muted">
          {done}/{game.quizzes.length} answered · {available} open
        </span>
      </p>
      {error && <div class="banner banner--bad">{error}</div>}
      <ol class="quiz-list">
        {game.quizzes.map((q) => (
          <li key={q.id} class={`quiz quiz--${q.status}`} data-quiz={q.id}>
            {q.status === 'locked' ? (
              <p class="muted">🔒 Unlocks after mission “{titles[q.after]}”.</p>
            ) : (
              <>
                <p class="quiz__q">{q.question}</p>
                <div class="quiz__choices">
                  {q.choices!.map((c, i) => {
                    const wrong = q.wrong_choices.includes(i);
                    const right = q.status === 'completed' && q.answer === i;
                    return (
                      <button
                        class={`choice${wrong ? ' choice--wrong' : ''}${right ? ' choice--right' : ''}`}
                        disabled={wrong || q.status === 'completed' || busy === q.id || game.status !== 'playing'}
                        onClick={() => answer(q.id, i)}
                      >
                        <span class="choice__key">{String.fromCharCode(65 + i)}</span> {c}
                      </button>
                    );
                  })}
                </div>
                {q.status === 'completed' && q.explanation && (
                  <div class="quiz__why">
                    <p>✓ {q.explanation}</p>
                    {q.source && (
                      <blockquote>
                        “{q.source.quote}”
                        <cite>
                          <a href={q.source.site_url} target="_blank" rel="noopener noreferrer">
                            {q.source.vignette.replace(/\.Rmd$/, '')} › {q.source.section}
                          </a>
                        </cite>
                      </blockquote>
                    )}
                  </div>
                )}
              </>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
