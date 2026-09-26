import type { GameView, PatientInfo } from '../types';
import { Scene } from '../art/Scene';
import { ExportButtons } from './NotebookPanel';

interface Props {
  game: GameView;
  patient: PatientInfo;
  unlocks: string | null;
  onAgain: () => void;
  onMenu: () => void;
  onNotice: (text: string, tone?: 'info' | 'bad') => void;
}

export function EndScreen({ game, patient, unlocks, onAgain, onMenu, onNotice }: Props) {
  const won = game.status === 'won';
  const final = [...game.timeline].reverse().find((t) => t.kind === 'end');
  const s = game.stats;
  return (
    <div class="end-backdrop">
      <div class={`end end--${won ? 'won' : 'lost'}`} role="dialog" aria-labelledby="end-title" data-testid={`end-${game.status}`}>
        <div class="end__art">
          {/* no symptom overlays on the final picture: cured, or at peace */}
          <Scene art={patient.art} stage={won ? 'cured' : 'deceased'} overlays={[]} rr={won ? 16 : 0} hr={won ? 72 : 0} />
        </div>
        <div class="end__body">
          <div class="popup__kicker">{won ? 'CURE FOUND' : 'THE PATIENT HAS DIED'}</div>
          <h2 id="end-title">{won ? `${patient.first_name} is going home` : `In memory of ${patient.name}`}</h2>
          {final && <p class="end__text">{final.text}</p>}
          {won && unlocks && <p class="banner banner--good">New campaign unlocked: {unlocks}</p>}
          <dl class="stats">
            <div><dt>Cure</dt><dd>{s.research}%</dd></div>
            <div><dt>Hospital days</dt><dd>{s.days}</dd></div>
            <div><dt>Active time</dt><dd>{Math.round(s.active_minutes)} min</dd></div>
            <div><dt>Missions</dt><dd>{s.missions_completed}/{s.missions_total}</dd></div>
            <div><dt>Journal club</dt><dd>{s.quizzes_correct}/{s.quizzes_total}</dd></div>
            <div><dt>Mistakes</dt><dd>{s.errors}</dd></div>
            <div><dt>Hints used</dt><dd>{s.hints_bought}</dd></div>
            <div><dt>RP earned</dt><dd>{s.rp_earned}</dd></div>
            <div><dt>Pages read</dt><dd>{s.pages_read}</dd></div>
          </dl>
          <h3>Keep your lab notebook</h3>
          <ExportButtons onNotice={onNotice} />
          <div class="popup__actions">
            <button class="btn btn--ghost" onClick={onMenu}>
              Campaigns
            </button>
            <button class="btn btn--primary" onClick={onAgain} data-testid="play-again">
              {won ? 'Play again' : 'Try again'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
