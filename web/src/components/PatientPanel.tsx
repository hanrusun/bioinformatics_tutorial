import type { GameView, PatientInfo } from '../types';
import { Scene } from '../art/Scene';
import { VitalsMonitor } from './VitalsMonitor';
import { STAGE_LABEL, stageTone } from '../lib/format';

interface Props {
  game: GameView;
  patient: PatientInfo;
  flash: boolean;
}

export function PatientPanel({ game, patient, flash }: Props) {
  const child = Number(patient.age) < 12;
  const notes = [...game.timeline].reverse().slice(0, 40);
  return (
    <aside class="patient-panel" aria-label="Patient">
      <div class="patient-id">
        <div>
          <h2>{patient.name}</h2>
          <p class="muted">
            {patient.age} y · {patient.illness.name}
          </p>
        </div>
        <span class={`stage stage--${stageTone(game.stage)}`} data-stage={game.stage}>
          {STAGE_LABEL[game.stage]}
        </span>
      </div>
      <Scene art={patient.art} stage={game.stage} overlays={game.overlays} rr={game.vitals.rr} hr={game.vitals.hr} flash={flash} />
      <VitalsMonitor vitals={game.vitals} child={child} alarm={game.stage === 'critical'} />
      <details class="patient-card">
        <summary>About {patient.first_name}</summary>
        <p>{patient.background}</p>
        <p>
          <strong>Presenting:</strong> {patient.presenting}
        </p>
        <p class="fine">{patient.fictional_notice}</p>
      </details>
      <section class="chart" aria-label="Patient chart">
        <h3>Chart notes</h3>
        <ol>
          {notes.map((n, i) => (
            <li key={`${n.day}-${i}`} class={`note note--${n.kind}`}>
              <span class="note__day">Day {n.day}</span>
              <span>{n.text}</span>
            </li>
          ))}
        </ol>
      </section>
    </aside>
  );
}
