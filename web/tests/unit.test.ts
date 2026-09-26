import { describe, expect, it } from 'vitest';
import { resolveArt } from '../src/art/Scene';
import { mix } from '../src/art/looks';
import { formatVital, vitalTone, wordCount } from '../src/lib/format';
import { renderMarkdown } from '../src/lib/markdown';

describe('art manifest', () => {
  it('falls back to the built-in scene when the manifest is empty', () => {
    const r = resolveArt({ scene: { default: '' } }, 'walter', 'stable', ['cannula', 'cough']);
    expect(r.baseImage).toBeNull();
    expect(r.builtInOverlays).toEqual(['cannula', 'cough']);
    expect(r.customOverlays).toEqual([]);
  });

  it('uses custom stage images and overlay files when provided', () => {
    const r = resolveArt(
      { scene: { default: 'room.png', critical: 'icu.png' }, overlays: { cannula: 'o2.png' } },
      'walter',
      'critical',
      ['cannula', 'cough'],
    );
    expect(r.baseImage).toBe('/art/walter/icu.png');
    expect(r.customOverlays).toEqual([{ key: 'cannula', src: '/art/walter/o2.png' }]);
    expect(r.builtInOverlays).toEqual(['cough']);
    expect(resolveArt({ scene: { default: 'room.png' } }, 'mia', 'stable', []).baseImage).toBe('/art/mia/room.png');
  });
});

describe('formatting', () => {
  const v = { hr: 118.4, rr: 26, spo2: 97.6, sbp: 98.2, dbp: 60.1, temp: 37.24 };
  it('formats vitals', () => {
    expect(formatVital('hr', v)).toBe('118');
    expect(formatVital('sbp', v)).toBe('98/60');
    expect(formatVital('temp', v)).toBe('37.2');
    expect(formatVital('hr', { ...v, hr: 0 })).toBe('--');
  });

  it('uses child ranges for children', () => {
    expect(vitalTone('hr', 118, true)).toBe('good');
    expect(vitalTone('hr', 118, false)).toBe('warn');
    expect(vitalTone('spo2', 88)).toBe('bad');
    expect(vitalTone('temp', 38.6)).toBe('bad');
  });

  it('counts words like the engine does', () => {
    expect(wordCount('NormalizeData() scales counts; log1p(x) then x10,000.')).toBe(6);
    expect(wordCount('  ')).toBe(0);
  });

  it('mixes colours', () => {
    expect(mix('#000000', '#ffffff', 0.5)).toBe('#808080');
    expect(mix('#102030', '#102030', 0.7)).toBe('#102030');
  });
});

describe('markdown', () => {
  it('renders and sanitizes', () => {
    const html = renderMarkdown('**bold** `code` <img src=x onerror="alert(1)"><script>alert(1)</script>');
    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('<code>code</code>');
    expect(html).not.toContain('onerror');
    expect(html).not.toContain('<script');
  });
});
