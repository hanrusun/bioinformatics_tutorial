import { useState } from 'preact/hooks';
import type { CampaignMeta, Meta } from '../types';
import { Scene } from '../art/Scene';

interface Props {
  meta: Meta;
  activeEnded: boolean;
  onStart: (campaign: CampaignMeta, difficulty: string) => void;
  onContinue: () => void;
}

export function TitleScreen({ meta, activeEnded, onStart, onContinue }: Props) {
  const [difficulty, setDifficulty] = useState('normal');
  const titles = Object.fromEntries(meta.campaigns.map((c) => [c.id, c.title]));
  return (
    <main class="title-screen">
      <header class="hero">
        <div class="hero__mark">✚</div>
        <h1>CURE LAB</h1>
        <p class="hero__tag">
          Plague Inc., in reverse. A patient is getting sicker. Your code is the cure.
        </p>
        <p class="hero__sub">
          Learn <strong>{meta.pack.name}</strong> {meta.pack.tool_version} by working through real analyses. Every
          mission and quiz comes straight from the official{' '}
          <a href={meta.pack.source_pin.site} target="_blank" rel="noopener noreferrer">
            {meta.pack.name} tutorials
          </a>
          .
        </p>
        {meta.active && (
          <button class="btn btn--primary btn--big" onClick={onContinue} data-testid="continue">
            {activeEnded ? 'Review last game →' : 'Continue treatment →'}
          </button>
        )}
      </header>

      <section class="how">
        <div>
          <h3>Cure</h3>
          <p>Passing a coding mission adds 5–11% to the cure. Each journal-club question adds 1%. Reach 100% to win.</p>
        </div>
        <div>
          <h3>Lethality</h3>
          <p>The disease worsens slowly on its own. Every wrong submission or answer lets it evolve a new symptom.</p>
        </div>
        <div>
          <h3>Research points</h3>
          <p>Read notebook pages and write your own notes to earn RP, then spend them on hints.</p>
        </div>
        <div>
          <h3>Free practice</h3>
          <p>Run is free and never counts against you. Only Submit is graded. The clock pauses while your code runs.</p>
        </div>
      </section>

      <section class="difficulty" aria-label="Difficulty">
        {meta.difficulties.map((d) => (
          <label class={`diff${difficulty === d.id ? ' is-selected' : ''}`}>
            <input type="radio" name="difficulty" value={d.id} checked={difficulty === d.id} onChange={() => setDifficulty(d.id)} />
            <strong>{d.label}</strong>
            <span>{d.description}</span>
          </label>
        ))}
      </section>

      <section class="campaigns">
        {meta.campaigns.map((c) => (
          <article class={`campaign${c.locked ? ' campaign--locked' : ''}`} data-campaign={c.id}>
            <div class="campaign__art">
              <Scene art={c.patient.art} stage={c.won ? 'cured' : 'stable'} overlays={[]} rr={0} hr={c.locked ? 0 : 80} />
            </div>
            <div class="campaign__body">
              <p class="campaign__illness">{c.patient.illness.name}</p>
              <h2>{c.title}</h2>
              <p class="muted">{c.subtitle}</p>
              <p>{c.summary}</p>
              <p class="fine">
                Patient: {c.patient.name}, {c.patient.age} · {c.missions} missions · {c.quizzes} journal-club questions
                {c.won && ' · ✓ cured'}
              </p>
              {c.locked ? (
                <button class="btn" disabled>
                  🔒 Cure “{titles[c.unlock_after ?? ''] ?? c.unlock_after}” first
                </button>
              ) : (
                <button class="btn btn--primary" onClick={() => onStart(c, difficulty)} data-testid={`start-${c.id}`}>
                  Admit {c.patient.first_name} →
                </button>
              )}
            </div>
          </article>
        ))}
      </section>
      <footer class="credits fine">
        Tutorial content is quoted from {meta.pack.source_pin.repo}@{meta.pack.source_pin.ref} and belongs to its
        authors. Patients are fictional. Game mechanics inspired by Plague Inc. (Ndemic Creations); not affiliated.
      </footer>
    </main>
  );
}
