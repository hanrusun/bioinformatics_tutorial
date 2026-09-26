import type { Stage, Vitals } from '../types';

export const STAGE_LABEL: Record<Stage, string> = {
  stable: 'Stable',
  symptomatic: 'Symptomatic',
  serious: 'Serious',
  critical: 'Critical',
  deceased: 'Deceased',
  cured: 'Cured',
};

export type Tone = 'good' | 'warn' | 'bad' | 'neutral';

export function stageTone(stage: Stage): Tone {
  if (stage === 'stable' || stage === 'cured') return 'good';
  if (stage === 'symptomatic') return 'warn';
  if (stage === 'deceased') return 'neutral';
  return 'bad';
}

/** Rough clinical tone of a vital sign (for colouring the monitor). */
export function vitalTone(key: keyof Vitals, value: number, child = false): Tone {
  if (value === 0) return 'neutral';
  switch (key) {
    case 'hr':
      return child
        ? value > 160 || value < 80 ? 'bad' : value > 140 ? 'warn' : 'good'
        : value > 120 || value < 50 ? 'bad' : value > 100 ? 'warn' : 'good';
    case 'spo2':
      return value < 90 ? 'bad' : value < 94 ? 'warn' : 'good';
    case 'rr':
      return child
        ? value > 45 ? 'bad' : value > 34 ? 'warn' : 'good'
        : value > 28 ? 'bad' : value > 20 ? 'warn' : 'good';
    case 'sbp':
      return child
        ? value > 125 || value < 75 ? 'bad' : value > 112 ? 'warn' : 'good'
        : value > 160 || value < 95 ? 'bad' : value > 140 || value < 105 ? 'warn' : 'good';
    case 'temp':
      return value >= 38.5 ? 'bad' : value >= 37.8 ? 'warn' : 'good';
    default:
      return 'neutral';
  }
}

export const pct = (x: number) => `${Math.round(x)}%`;

export function formatVital(key: keyof Vitals, v: Vitals): string {
  if (v.hr === 0 && key !== 'temp') return '--';
  switch (key) {
    case 'sbp':
    case 'dbp':
      return `${Math.round(v.sbp)}/${Math.round(v.dbp)}`;
    case 'temp':
      return v.temp.toFixed(1);
    default:
      return String(Math.round(v[key]));
  }
}

export function wordCount(text: string): number {
  return (text || '').split(/\s+/).filter((t) => /[A-Za-z0-9]/.test(t)).length;
}

export function plural(n: number, word: string, pluralWord = `${word}s`) {
  return `${n} ${n === 1 ? word : pluralWord}`;
}
