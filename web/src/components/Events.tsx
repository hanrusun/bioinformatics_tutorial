import { useEffect, useState } from 'preact/hooks';
import type { GameEvent } from '../types';

export interface Notice {
  id: number;
  text: string;
  tone: 'info' | 'good' | 'bad' | 'warn' | 'rp';
}

/** Queue of big "the disease evolved" cards, shown one at a time. */
export function TraitPopup({ event, onClose }: { event: GameEvent; onClose: () => void }) {
  useEffect(() => {
    const t = setTimeout(onClose, 8000);
    return () => clearTimeout(t);
  }, [event.id]);
  const progression = !event.data.trait;
  return (
    <div class="popup-backdrop" onClick={onClose}>
      <div class="popup popup--trait" role="alertdialog" aria-labelledby="trait-title" data-testid="trait-popup">
        <div class="popup__kicker">{progression ? 'THE DISEASE PROGRESSES' : 'THE DISEASE HAS EVOLVED'}</div>
        <h2 id="trait-title">{event.title}</h2>
        {event.data.category && !progression && <span class="trait__cat">{event.data.category}</span>}
        <p>{event.text}</p>
        <p class="popup__stat">
          Lethality +{Number(event.data.gain).toFixed(1)} → {Number(event.data.severity).toFixed(1)}%
        </p>
        <button class="btn" onClick={onClose} autofocus>
          Back to the lab
        </button>
      </div>
    </div>
  );
}

export function Toasts({ notices, onDismiss }: { notices: Notice[]; onDismiss: (id: number) => void }) {
  return (
    <div class="toasts" aria-live="polite">
      {notices.map((n) => (
        <Toast key={n.id} notice={n} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function Toast({ notice, onDismiss }: { notice: Notice; onDismiss: (id: number) => void }) {
  const [leaving, setLeaving] = useState(false);
  useEffect(() => {
    const a = setTimeout(() => setLeaving(true), 4200);
    const b = setTimeout(() => onDismiss(notice.id), 4600);
    return () => {
      clearTimeout(a);
      clearTimeout(b);
    };
  }, [notice.id]);
  return (
    <div class={`toast toast--${notice.tone}${leaving ? ' is-leaving' : ''}`} onClick={() => onDismiss(notice.id)}>
      {notice.text}
    </div>
  );
}
