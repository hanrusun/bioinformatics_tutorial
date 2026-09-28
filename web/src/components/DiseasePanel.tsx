import { useEffect, useState } from 'preact/hooks';
import { load, save } from '../lib/storage';
import type { GameView, PatientInfo, TreeTrait } from '../types';

const CATEGORY_LABEL: Record<string, string> = {
  symptom: 'Symptom',
  complication: 'Complication',
  mutation: 'Mutation',
  resistance: 'Resistance',
  event: 'Event',
};

// Traits that haven't happened yet stay hidden unless the player asks to see
// them, so each evolution is a surprise. The choice is remembered.
const REVEAL_KEY = 'curelab:reveal-tree';

function TraitCard({ t, revealed }: { t: TreeTrait; revealed: boolean }) {
  if (!t.acquired && !revealed) {
    return (
      <article class="trait trait--hidden">
        <header>
          <span class="trait__cat">Not evolved</span>
        </header>
        <h4>???</h4>
        <p class="muted">Keep your code clean and this may never happen.</p>
      </article>
    );
  }
  return (
    <article class={`trait${t.acquired ? ' trait--on' : ''} trait--${t.category}`} data-trait={t.id}>
      <header>
        <span class="trait__cat">{CATEGORY_LABEL[t.category] ?? t.category}</span>
        {t.acquired && <span class="trait__day">day {t.day}</span>}
      </header>
      <h4>{t.name}</h4>
      {t.acquired ? <p>{t.note}</p> : <p class="muted">{t.requires.length ? 'Dormant: needs an earlier trait' : 'Dormant'}</p>}
    </article>
  );
}

export function DiseasePanel({ game, patient }: { game: GameView; patient: PatientInfo }) {
  const [revealed, setRevealed] = useState(load(REVEAL_KEY) === '1');
  useEffect(() => save(REVEAL_KEY, revealed ? '1' : '0'), [revealed]);
  const disease = game.tree.filter((t) => t.category !== 'event');
  const events = game.tree.filter((t) => t.category === 'event');
  const tiers = [1, 2, 3, 4].map((tier) => disease.filter((t) => t.tier === tier)).filter((g) => g.length);
  const eventsSeen = events.filter((t) => t.acquired).length;
  const bumps = game.traits.filter((t) => !t.id).length;
  return (
    <div class="disease-panel">
      <header class="disease-head">
        <div>
          <h2>{patient.illness.name}</h2>
          <p class="muted">{patient.illness.blurb}</p>
        </div>
        <dl class="disease-stats">
          <div>
            <dt>Lethality</dt>
            <dd>{game.severity.toFixed(1)}%</dd>
          </div>
          <div>
            <dt>Decline</dt>
            <dd>
              {game.decline_per_hour.toFixed(1)} <small>health/h</small>
            </dd>
          </div>
          <div>
            <dt>Evolved</dt>
            <dd>
              {disease.filter((t) => t.acquired).length}/{disease.length}
              {bumps > 0 && ` +${bumps}`}
            </dd>
          </div>
        </dl>
      </header>
      <p class="panel-intro">
        Every wrong submission or quiz answer lets the disease evolve one trait. Traits unlock along the tree; later
        tiers are more dangerous. Now and then a mistake triggers a random ward event instead; most make things
        worse, a few are harmless. The disease also worsens slowly on its own while the clock runs.
      </p>
      <div class="tree-reveal">
        <button class="btn btn--ghost" onClick={() => setRevealed(!revealed)} aria-pressed={revealed} data-testid="reveal-tree">
          {revealed ? 'Hide what hasn\u2019t happened yet' : 'Reveal the whole disease tree'}
        </button>
        <span class="muted">{revealed ? 'Spoilers on: every possible trait is listed.' : 'Traits stay hidden until they evolve.'}</span>
      </div>
      <div class="tree">
        {tiers.map((group, i) => (
          <section class="tier" key={i}>
            <h3>Tier {i + 1}</h3>
            <div class="tier__traits">
              {group.map((t) => (
                <TraitCard t={t} revealed={revealed} />
              ))}
            </div>
          </section>
        ))}
        {events.length > 0 && (
          <section class="tier tier--events">
            <h3>
              Ward events <span class="muted">({eventsSeen}/{events.length} so far)</span>
            </h3>
            <div class="tier__traits">
              {events.map((t) =>
                t.acquired ? (
                  <article class="trait trait--on trait--event" data-trait={t.id}>
                    <header>
                      <span class="trait__cat">Patient event</span>
                      <span class="trait__day">day {t.day}</span>
                    </header>
                    <h4>{t.name}</h4>
                    <p>{t.note}</p>
                  </article>
                ) : (
                  <article class="trait trait--event trait--hidden" data-trait={t.id}>
                    <header>
                      <span class="trait__cat">Patient event</span>
                    </header>
                    <h4>???</h4>
                    <p class="muted">Something else could still go wrong on the ward.</p>
                  </article>
                ),
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
