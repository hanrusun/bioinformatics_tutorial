// Appearance of each built-in patient. Keys match `patient.art` in the
// illness files (illnesses/*.yaml).

export interface Look {
  id: string;
  child: boolean;
  skin: string;
  skinShade: string;
  lips: string;
  hair: string;
  hairShade: string;
  hairStyle: 'short' | 'puffs' | 'bun' | 'curly';
  gown: string;
  gownDots: string;
  blanket: string;
  blanketShade: string;
  prop: 'honey' | 'rabbit' | 'sourdough' | 'ball';
}

export const LOOKS: Record<string, Look> = {
  walter: {
    id: 'walter',
    child: false,
    skin: '#e9bf9b',
    skinShade: '#cf9f7a',
    lips: '#b9776a',
    hair: '#c9ccd1',
    hairShade: '#9fa5ad',
    hairStyle: 'short',
    gown: '#9cc4dd',
    gownDots: '#7aa9c7',
    blanket: '#dfe7ee',
    blanketShade: '#bccad6',
    prop: 'honey',
  },
  mia: {
    id: 'mia',
    child: true,
    skin: '#8d5a3b',
    skinShade: '#744629',
    lips: '#6b3a2c',
    hair: '#241814',
    hairShade: '#3a2820',
    hairStyle: 'puffs',
    gown: '#f3c6d8',
    gownDots: '#e79ab9',
    blanket: '#fff3c9',
    blanketShade: '#ecd89a',
    prop: 'rabbit',
  },
  anjali: {
    id: 'anjali',
    child: false,
    skin: '#b27a52',
    skinShade: '#95613d',
    lips: '#8a4b3f',
    hair: '#1f1714',
    hairShade: '#3a2a22',
    hairStyle: 'bun',
    gown: '#b9d9c6',
    gownDots: '#8fc2a4',
    blanket: '#f6e7d8',
    blanketShade: '#e2cdb6',
    prop: 'sourdough',
  },
  tomas: {
    id: 'tomas',
    child: false,
    skin: '#c99373',
    skinShade: '#ab7757',
    lips: '#9a5a4c',
    hair: '#2a1d16',
    hairShade: '#4a3428',
    hairStyle: 'curly',
    gown: '#c9d4f2',
    gownDots: '#a3b3e0',
    blanket: '#e8f1e4',
    blanketShade: '#c7d8c0',
    prop: 'ball',
  },
};

export const DEFAULT_LOOK = LOOKS.walter;

/** Mix two #rrggbb colours; t = 0 gives a, t = 1 gives b. */
export function mix(a: string, b: string, t: number): string {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  const c = pa.map((v, i) => Math.round(v + (pb[i] - v) * Math.max(0, Math.min(1, t))));
  return `#${c.map((v) => v.toString(16).padStart(2, '0')).join('')}`;
}
