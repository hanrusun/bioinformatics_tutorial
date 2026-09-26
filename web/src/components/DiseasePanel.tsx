import type { GameView, PatientInfo } from '../types';

const CATEGORY_LABEL: Record<string, string> = {
  symptom: 'Symptom',
  complication: 'Complication',
  mutation: 'Mutation',
  resistance: 'Resistance',
  event: 'Event',
};

export function DiseasePanel({ game, patient }: { game: GameView; patient: PatientInfo }) {
  const tiers = [1, 2, 3, 4].map((tier) => game.tree.filter((t) => t.tier === tier)).filter((g) => g.length);
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
              {game.tree.filter((t) => t.acquired).length}/{game.tree.length}
              {bumps > 0 && ` +${bumps}`}
            </dd>
          </div>
        </dl>
      </header>
      <p class="panel-intro">
        Every wrong submission or quiz answer lets the disease evolve one trait. Traits unlock along the tree; later
        tiers are more dangerous. The disease also worsens slowly on its own while the clock runs.
      </p>
      <div class="tree">
        {tiers.map((group, i) => (
          <section class="tier" key={i}>
            <h3>Tier {i + 1}</h3>
            <div class="tier__traits">
              {group.map((t) => (
                <article class={`trait${t.acquired ? ' trait--on' : ''} trait--${t.category}`} data-trait={t.id}>
                  <header>
                    <span class="trait__cat">{CATEGORY_LABEL[t.category] ?? t.category}</span>
                    {t.acquired && <span class="trait__day">day {t.day}</span>}
                  </header>
                  <h4>{t.name}</h4>
                  {t.acquired ? <p>{t.note}</p> : <p class="muted">{t.requires.length ? 'Dormant: needs an earlier trait' : 'Dormant'}</p>}
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
