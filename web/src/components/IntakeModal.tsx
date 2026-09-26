import type { CampaignMeta } from '../types';

interface Props {
  campaign: CampaignMeta;
  difficulty: string;
  busy: boolean;
  onBegin: () => void;
  onCancel: () => void;
}

export function IntakeModal({ campaign, busy, onBegin, onCancel }: Props) {
  const p = campaign.patient;
  return (
    <div class="popup-backdrop">
      <div class="popup popup--intake" role="dialog" aria-labelledby="intake-title">
        <div class="popup__kicker">ADMISSION · {p.illness.short}</div>
        <h2 id="intake-title">{p.name}</h2>
        <p class="muted">
          {p.age} years · {p.sex}
        </p>
        <p>{p.background}</p>
        <p>
          <strong>Presenting:</strong> {p.presenting}
        </p>
        <p class="intake__mission">
          The lab has one job: find a cure before {p.first_name}’s condition runs out of time. Work through the
          missions, and every correct analysis moves the cure forward.
        </p>
        <p class="fine">{p.fictional_notice}</p>
        <div class="popup__actions">
          <button class="btn btn--ghost" onClick={onCancel}>
            Not yet
          </button>
          <button class="btn btn--primary" onClick={onBegin} disabled={busy} data-testid="begin">
            {busy ? 'Admitting…' : 'Begin treatment'}
          </button>
        </div>
      </div>
    </div>
  );
}
