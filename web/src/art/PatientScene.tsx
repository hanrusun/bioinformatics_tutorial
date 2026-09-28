// Built-in, original patient illustration (flat vector SVG).
//
// The scene is layered so every piece can react to the game:
//   room (window light by stage) -> furniture -> bed -> patient -> overlays
// Stage drives skin tone, eyes, mouth and room lighting; evolved traits add
// overlays (cannula, "raccoon eyes", swelling, ...). Any piece can be swapped
// for custom art through public/art/<patient>/manifest.json (see docs/ART.md).

import type { Stage } from '../types';
import { LOOKS, DEFAULT_LOOK, mix, type Look } from './looks';

export interface SceneProps {
  art: string;
  stage: Stage;
  overlays: string[];
  rr: number; // breaths per minute, drives the breathing animation
  hr: number;
  flash?: boolean; // brief pulse when a new trait appears
}

const W = 480;
const H = 360;

// fixed positions so the art is stable between renders
const SNOW: [number, number, number][] = [
  [34, 50, 1.6], [52, 70, 1.2], [70, 46, 1.4], [96, 60, 1.8], [118, 44, 1.2], [140, 66, 1.5],
  [44, 100, 1.3], [66, 118, 1.7], [104, 96, 1.2], [128, 114, 1.6], [84, 128, 1.1], [58, 88, 1],
];
const GLITTER: [number, number, string][] = [
  [214, 244, '#f7c948'], [232, 252, '#f472b6'], [252, 240, '#67e8f9'], [270, 256, '#f7c948'],
  [290, 244, '#c084fc'], [306, 258, '#f472b6'], [322, 246, '#67e8f9'], [244, 262, '#c084fc'],
  [198, 256, '#f472b6'], [284, 266, '#f7c948'], [226, 236, '#67e8f9'], [312, 236, '#f7c948'],
];

function skinFor(look: Look, stage: Stage, overlays: Set<string>) {
  const pale = overlays.has('pale') ? 0.18 : 0;
  const drain =
    { stable: 0, symptomatic: 0.08, serious: 0.18, critical: 0.3, deceased: 0.42, cured: 0 }[stage] + pale;
  let skin = mix(look.skin, '#b9bcc4', drain);
  let shade = mix(look.skinShade, '#9c9faa', drain);
  if (overlays.has('jaundice') && stage !== 'cured') {
    skin = mix(skin, '#e2c24a', 0.35);
    shade = mix(shade, '#bf9d2c', 0.3);
  }
  return { skin, shade };
}

function windowSky(stage: Stage) {
  switch (stage) {
    case 'cured':
      return ['#8fd3ff', '#fff1c4'];
    case 'critical':
      return ['#3b3561', '#c9786a'];
    case 'deceased':
      return ['#0d1530', '#1f2b52'];
    case 'serious':
      return ['#6d8fb1', '#d8c3a5'];
    default:
      return ['#7fb4d6', '#d6ecf5'];
  }
}

export function PatientScene({ art, stage, overlays, rr, hr, flash }: SceneProps) {
  const look = LOOKS[art] ?? DEFAULT_LOOK;
  const ov = new Set(stage === 'cured' ? [] : overlays);
  const child = look.child;
  const { skin, shade } = skinFor(look, stage, ov);
  const [skyTop, skyBottom] = windowSky(stage);
  const breathe = rr > 0 && stage !== 'deceased' ? `${(60 / Math.max(rr, 6)).toFixed(2)}s` : '0s';
  const beat = hr > 0 ? `${(60 / Math.max(hr, 30)).toFixed(2)}s` : '0s';

  // geometry
  const head = child ? { cx: 176, cy: 200, r: 25 } : { cx: 172, cy: 196, r: 27 };
  const bodyEnd = child ? 335 : 392;
  const swollen = ov.has('face_swelling');
  const eyesClosed = stage === 'deceased' || stage === 'critical';
  const eyesHeavy = stage === 'serious' || ov.has('tired');
  const smile = stage === 'cured';
  const frown = stage === 'serious' || stage === 'critical' || ov.has('wince');
  const dim = { stable: 0, symptomatic: 0.04, serious: 0.12, critical: 0.22, deceased: 0.5, cured: 0 }[stage];
  const eyeY = head.cy - 3;
  const eyeL = head.cx - 10;
  const eyeR = head.cx + 9;
  const mouthY = head.cy + 13;

  return (
    <svg
      class={`scene${flash ? ' scene--flash' : ''}`}
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`Hospital room. The patient is ${stage}.`}
    >
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color={skyTop} />
          <stop offset="1" stop-color={skyBottom} />
        </linearGradient>
        <linearGradient id="wall" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#2d4150" />
          <stop offset="1" stop-color="#253643" />
        </linearGradient>
        <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#1c2831" />
          <stop offset="1" stop-color="#141d24" />
        </linearGradient>
        <radialGradient id="warm" cx="0.2" cy="0.25" r="0.9">
          <stop offset="0" stop-color="#ffe7a3" stop-opacity="0.35" />
          <stop offset="1" stop-color="#ffe7a3" stop-opacity="0" />
        </radialGradient>
        <clipPath id="windowClip">
          <rect x="26" y="36" width="122" height="112" rx="4" />
        </clipPath>
      </defs>

      {/* ---------------------------------------------------------- room */}
      <rect width={W} height={H} fill="url(#wall)" />
      <rect y="286" width={W} height={H - 286} fill="url(#floor)" />
      <rect y="284" width={W} height="4" fill="#33495a" />

      {/* window */}
      <rect x="22" y="32" width="130" height="120" rx="6" fill="#56707f" />
      <rect x="26" y="36" width="122" height="112" rx="4" fill="url(#sky)" />
      {stage === 'deceased' && (
        <g fill="#f4f1d0">
          <circle cx="58" cy="62" r="1.6" />
          <circle cx="112" cy="54" r="1.2" />
          <circle cx="94" cy="92" r="1" />
          <path d="M122 70 a12 12 0 1 0 8 20 a9 9 0 1 1 -8 -20z" opacity="0.9" />
        </g>
      )}
      {stage === 'cured' && <circle cx="120" cy="64" r="16" fill="#fff4b0" />}
      {stage !== 'deceased' && stage !== 'cured' && (
        <g fill="#ffffff" opacity="0.75" clip-path="url(#windowClip)">
          <ellipse class="cloud" cx="60" cy="70" rx="18" ry="7" />
          <ellipse class="cloud cloud--slow" cx="112" cy="104" rx="14" ry="5" />
        </g>
      )}
      {ov.has('haze') && (
        <rect x="26" y="36" width="122" height="112" rx="4" fill="#8a7a55" opacity="0.55" class="haze" />
      )}
      {ov.has('snow') && (
        <g clip-path="url(#windowClip)">
          <rect x="26" y="36" width="122" height="112" fill="#dfe8f2" opacity="0.55" />
          <g class="snow" fill="#ffffff">
            {SNOW.map(([x, y, r], i) => (
              <circle key={i} cx={x} cy={y} r={r} />
            ))}
          </g>
          <path d="M26 140 q30 -8 60 0 t62 -2 V148 H26z" fill="#ffffff" />
        </g>
      )}
      <path d="M87 36 V148 M26 92 H148" stroke="#56707f" stroke-width="4" />
      {ov.has('cigarettes') && (
        <g transform="translate(104 136) rotate(-8)" aria-label="a hidden cigarette pack">
          <rect width="18" height="13" rx="1.5" fill="#f4f4f4" stroke="#c9c9c9" />
          <rect width="18" height="5" rx="1.5" fill="#c8373a" />
          <rect x="4" y="-4" width="3" height="5" fill="#f3e3c3" />
          <rect x="4" y="-4" width="3" height="1.6" fill="#d9894b" />
        </g>
      )}
      {ov.has('bee') && (
        <g class="bee" transform="translate(168 118)">
          <ellipse cx="0" cy="0" rx="6" ry="4.2" fill="#f7c948" />
          <path d="M-2 -4 v8 M1.5 -4 v8" stroke="#2b211c" stroke-width="1.6" />
          <ellipse cx="-1" cy="-6" rx="3.5" ry="2.4" fill="#e6f4ff" opacity="0.85" />
          <ellipse cx="3" cy="-6" rx="3.5" ry="2.4" fill="#e6f4ff" opacity="0.85" />
          <path d="M-9 4 q-8 4 -14 -2" stroke="#e6edf3" stroke-width="1" stroke-dasharray="2 2" fill="none" />
        </g>
      )}
      <path d="M18 28 h26 v128 q-10 4 -26 0z" fill="#7d5e7a" opacity="0.9" />
      <path d="M156 28 h-20 v128 q8 4 20 0z" fill="#7d5e7a" opacity="0.9" />

      {/* child's drawing taped to the wall */}
      {look.prop === 'rabbit' && (
        <g transform="translate(196 44) rotate(-4)">
          <rect width="58" height="44" fill="#fbfbf2" />
          <rect x="22" y="-4" width="14" height="7" fill="#e7dca1" opacity="0.8" />
          <circle cx="47" cy="11" r="6" fill="#f7c948" />
          <path d="M8 38 L16 22 L24 38 M16 22 v-6 M34 38 L40 26 L46 38 M40 26 v-5" stroke="#3b82c4" stroke-width="2" fill="none" />
          <circle cx="16" cy="13" r="3.5" fill="none" stroke="#3b82c4" stroke-width="2" />
          <circle cx="40" cy="18" r="3" fill="none" stroke="#e05d8f" stroke-width="2" />
          <path d="M4 40 h50" stroke="#58a55c" stroke-width="3" />
        </g>
      )}

      {/* Kiara's drawing of a birthday cake */}
      {look.prop === 'sourdough' && (
        <g transform="translate(196 44) rotate(3)">
          <rect width="58" height="44" fill="#fbfbf2" />
          <rect x="22" y="-4" width="14" height="7" fill="#e7dca1" opacity="0.8" />
          <rect x="14" y="22" width="30" height="16" rx="2" fill="#f4a7c1" stroke="#d9709a" stroke-width="1.5" />
          <path d="M14 27 q4 4 7.5 0 t7.5 0 t7.5 0 t7.5 0" stroke="#fff" stroke-width="2" fill="none" />
          <path d="M22 22 v-7 M29 22 v-7 M36 22 v-7" stroke="#3b82c4" stroke-width="2" />
          <path d="M22 13 q-2 -3 0 -5 q2 2 0 5 M29 13 q-2 -3 0 -5 q2 2 0 5 M36 13 q-2 -3 0 -5 q2 2 0 5" fill="#f7c948" />
          <path d="M4 40 h50" stroke="#58a55c" stroke-width="3" />
        </g>
      )}

      {ov.has('isolation') && (
        <g transform="translate(262 96)">
          <rect width="62" height="26" rx="3" fill="#f7d23e" stroke="#b8961a" />
          <text x="31" y="11" text-anchor="middle" font-size="7.5" font-weight="700" fill="#2b2410" font-family="sans-serif">
            PROTECTIVE
          </text>
          <text x="31" y="21" text-anchor="middle" font-size="7.5" font-weight="700" fill="#2b2410" font-family="sans-serif">
            ISOLATION
          </text>
        </g>
      )}

      {/* wall monitor (decorative; the live monitor is below the scene) */}
      <g transform="translate(330 22)">
        <rect width="124" height="72" rx="6" fill="#0c1116" stroke="#3d4e5b" stroke-width="3" />
        <polyline
          class={hr > 0 ? 'wall-ecg' : ''}
          style={{ animationDuration: beat === '0s' ? '0s' : `calc(${beat} * 4)` }}
          points={hr > 0 ? '6,40 26,40 32,40 36,28 40,54 44,18 48,46 52,40 74,40 80,40 84,28 88,54 92,18 96,46 100,40 118,40' : '6,40 118,40'}
          fill="none"
          stroke={stage === 'critical' ? '#ff5d5d' : hr > 0 ? '#3ee07a' : '#6b7a86'}
          stroke-width="2"
        />
        <circle cx="112" cy="10" r="3.5" fill={stage === 'critical' ? '#ff5d5d' : '#3ee07a'} class={stage === 'critical' ? 'blink' : ''} />
        <rect x="52" y="72" width="20" height="18" fill="#3d4e5b" />
      </g>

      {/* bedside table + props */}
      <g>
        <rect x="16" y="232" width="78" height="70" rx="4" fill="#8b6b4d" />
        <rect x="12" y="226" width="86" height="10" rx="3" fill="#a3805f" />
        <rect x="24" y="252" width="62" height="3" fill="#6f5439" />
        <circle cx="55" cy="272" r="3" fill="#5a4330" />
        {look.prop === 'honey' && stage !== 'deceased' && (
          <g transform="translate(58 196)">
            <rect x="0" y="6" width="26" height="26" rx="5" fill="#f2b233" stroke="#c98a12" stroke-width="1.5" />
            <rect x="-1" y="2" width="28" height="7" rx="2" fill="#6b4a2b" />
            <path d="M8 18 l5 -3 l5 3 v6 l-5 3 l-5 -3z" fill="#ffd66b" stroke="#c98a12" />
          </g>
        )}
        {look.prop === 'ball' && stage !== 'deceased' && (
          <g transform="translate(70 212)">
            <circle cx="0" cy="0" r="13" fill="#fbfbfb" stroke="#cfd6dc" stroke-width="1" />
            <path d="M0 -5 l4.8 3.5 -1.8 5.6 h-6 l-1.8 -5.6z" fill="#2b2f36" />
            <path d="M0 -13 v8 M4.8 -1.5 l7.6 -2.5 M3 4.1 l4.6 6.8 M-3 4.1 l-4.6 6.8 M-4.8 -1.5 l-7.6 -2.5" stroke="#2b2f36" stroke-width="1.2" />
          </g>
        )}
        {look.prop === 'sourdough' && stage !== 'deceased' && (
          <g transform="translate(58 188)">
            <rect x="0" y="6" width="26" height="34" rx="6" fill="#e9f3fb" opacity="0.9" stroke="#b7c8d6" stroke-width="1.5" />
            <rect x="2" y="16" width="22" height="22" rx="4" fill="#f3e6c8" />
            <circle cx="8" cy="22" r="1.4" fill="#fffaf0" />
            <circle cx="16" cy="26" r="1.8" fill="#fffaf0" />
            <circle cx="11" cy="31" r="1.2" fill="#fffaf0" />
            <rect x="-1" y="2" width="28" height="6" rx="2" fill="#c98a5a" />
            {/* Gerald's googly eyes */}
            <circle cx="9" cy="12" r="2.6" fill="#fff" stroke="#8a8a8a" stroke-width="0.6" />
            <circle cx="17" cy="12" r="2.6" fill="#fff" stroke="#8a8a8a" stroke-width="0.6" />
            <circle cx="9.6" cy="12.6" r="1.1" fill="#2b211c" />
            <circle cx="16.4" cy="12.4" r="1.1" fill="#2b211c" />
          </g>
        )}
        {ov.has('tissue') && (
          <g transform="translate(24 212)">
            <path d="M0 14 q6 -14 16 -8 q10 -8 16 4 q4 8 -4 12 h-24 q-6 -2 -4 -8z" fill="#fafafa" stroke="#d6d6d6" />
            <circle cx="16" cy="12" r="2.6" fill="#c53b3b" />
          </g>
        )}
        {stage === 'deceased' && (
          <g transform="translate(60 176)">
            <rect x="4" y="30" width="16" height="22" rx="3" fill="#9fb7c9" opacity="0.9" />
            <path d="M12 30 C12 18 10 10 12 2" stroke="#4f8a4f" stroke-width="2" fill="none" />
            <circle cx="12" cy="4" r="6" fill="#f6f1ff" />
            <circle cx="12" cy="4" r="2.4" fill="#f7d774" />
          </g>
        )}
        {stage === 'cured' && (
          <g transform="translate(30 186) rotate(-6)">
            <rect width="44" height="34" rx="2" fill="#fff7e8" stroke="#e6cfa6" />
            <path d="M22 10 c-4 -6 -12 -2 -8 4 l8 8 l8 -8 c4 -6 -4 -10 -8 -4z" fill="#ef6f7d" />
          </g>
        )}
      </g>

      {ov.has('chicken') && (
        <g transform="translate(26 300)">
          <path d="M0 0 h30 l-4 32 h-22z" fill="#fbfbfb" />
          <path d="M4 0 l3 32 M11 0 l1 32 M18 0 l-1 32 M25 0 l-3 32" stroke="#d23b36" stroke-width="3" />
          <ellipse cx="9" cy="-2" rx="7" ry="5" fill="#c8843a" />
          <ellipse cx="20" cy="-3" rx="7" ry="5" fill="#b8742e" />
          <rect x="-2" y="-1" width="34" height="4" rx="1" fill="#d23b36" />
        </g>
      )}

      {/* IV pole */}
      <g>
        <rect x="408" y="96" width="4" height="200" fill="#9aa7b2" />
        <path d="M398 300 h24 M410 300 l-12 8 M410 300 l12 8" stroke="#9aa7b2" stroke-width="3" />
        <path d="M396 96 h28" stroke="#9aa7b2" stroke-width="3" />
        <g>
          <rect x="398" y="100" width="24" height="40" rx="6" fill="#e9f3fb" opacity="0.9" stroke="#b7c8d6" />
          <rect x="400" y="116" width="20" height="22" rx="4" fill="#bfe2f5" />
          <circle class="drip" cx="410" cy="148" r="1.6" fill="#9fd4f0" style={{ animationDuration: ov.has('iv') ? '0.9s' : '1.8s' }} />
        </g>
        {ov.has('iv') && (
          <g>
            <rect x="372" y="104" width="20" height="34" rx="5" fill="#fff6e3" opacity="0.95" stroke="#dcc9a5" />
            <rect x="374" y="118" width="16" height="18" rx="4" fill="#ffe0a3" />
            <path d="M382 138 C382 190 330 220 272 246" stroke="#e8d2a6" stroke-width="2" fill="none" />
          </g>
        )}
        <path d="M410 140 C410 200 330 226 262 246" stroke="#cfe6f3" stroke-width="2" fill="none" />
      </g>

      {/* crutches */}
      {ov.has('crutches') && (
        <g stroke="#9aa7b2" stroke-width="3" stroke-linecap="round" fill="none">
          <path d="M366 300 L384 168 M374 300 L392 168" />
          <path d="M380 170 h16" stroke-width="5" />
          <path d="M369 238 h9" stroke="#6b7d8d" stroke-width="4" />
          <path d="M380 300 L398 172 M388 300 L406 172" opacity="0.8" />
          <path d="M394 174 h16" stroke-width="5" opacity="0.8" />
        </g>
      )}

      {/* drain bottle */}
      {ov.has('drain') && (
        <g>
          <path d="M300 262 C300 290 318 300 330 306" stroke="#d98e8e" stroke-width="3" fill="none" />
          <rect x="322" y="300" width="30" height="36" rx="6" fill="#eef4f8" stroke="#b7c8d6" />
          <rect x="325" y="318" width="24" height="15" rx="3" fill="#e2a0a0" />
        </g>
      )}

      {/* ---------------------------------------------------------- bed */}
      <rect x="106" y="160" width="18" height="126" rx="5" fill="#8fa2b3" />
      <rect x="110" y="168" width="10" height="100" rx="3" fill="#a9bac8" />
      <rect x="106" y="258" width="318" height="24" rx="6" fill="#8fa2b3" />
      <rect x="120" y="282" width="8" height="16" fill="#6b7d8d" />
      <rect x="400" y="282" width="8" height="16" fill="#6b7d8d" />
      <circle cx="124" cy="302" r="6" fill="#39485a" />
      <circle cx="404" cy="302" r="6" fill="#39485a" />
      <rect x="116" y="236" width="304" height="26" rx="8" fill="#f0f3f6" />
      <ellipse cx="164" cy="214" rx="50" ry="21" fill="#f7f9fb" stroke="#dfe5ea" />

      {/* ---------------------------------------------------------- patient */}
      <g class={`patient patient--${stage}`}>
        {/* shoulders / gown */}
        <path
          d={`M${head.cx - 34} 244 C${head.cx - 30} 226 ${head.cx - 12} 222 ${head.cx} 222 C${head.cx + 16} 222 ${head.cx + 38} 226 ${head.cx + 44} 244 Z`}
          fill={look.gown}
        />
        <g fill={look.gownDots} opacity="0.7">
          <circle cx={head.cx - 18} cy="234" r="1.6" />
          <circle cx={head.cx + 4} cy="230" r="1.6" />
          <circle cx={head.cx + 24} cy="236" r="1.6" />
        </g>
        {ov.has('brace') && (
          <rect x={head.cx - 16} y={head.cy + 20} width="34" height="12" rx="5" fill="#f4f4f4" stroke="#c9d1d8" />
        )}

        {/* head */}
        <g transform={swollen ? `translate(${head.cx} ${head.cy}) scale(1.1 1.06) translate(${-head.cx} ${-head.cy})` : undefined}>
          {look.hairStyle === 'puffs' && (
            <g fill={look.hair}>
              <circle cx={head.cx - 22} cy={head.cy - 22} r="12" />
              <circle cx={head.cx + 20} cy={head.cy - 24} r="12" />
              <circle cx={head.cx - 22} cy={head.cy - 22} r="4" fill="#e05d8f" transform="translate(6 8)" />
              <circle cx={head.cx + 20} cy={head.cy - 24} r="4" fill="#e05d8f" transform="translate(-6 9)" />
            </g>
          )}
          {look.hairStyle === 'bun' && (
            <g fill={look.hair}>
              <circle cx={head.cx - 10} cy={head.cy - head.r - 4} r="11" />
              <path d={`M${head.cx - 18} ${head.cy - head.r} q8 -6 16 0`} stroke={look.hairShade} stroke-width="1.5" fill="none" />
            </g>
          )}
          <ellipse cx={head.cx} cy={head.cy} rx={head.r} ry={head.r + 2} fill={skin} />
          {/* ears */}
          <ellipse cx={head.cx - head.r + 1} cy={head.cy + 2} rx="4" ry="6" fill={shade} />
          <ellipse cx={head.cx + head.r - 1} cy={head.cy + 2} rx="4" ry="6" fill={shade} />
          {/* hair */}
          {look.hairStyle === 'short' ? (
            <path
              d={`M${head.cx - head.r} ${head.cy - 4} C${head.cx - head.r} ${head.cy - 30} ${head.cx + head.r} ${head.cy - 34} ${head.cx + head.r} ${head.cy - 6} C${head.cx + 14} ${head.cy - 22} ${head.cx - 10} ${head.cy - 24} ${head.cx - head.r} ${head.cy - 4}Z`}
              fill={look.hair}
            />
          ) : (
            <path
              d={`M${head.cx - head.r - 1} ${head.cy} C${head.cx - head.r} ${head.cy - 34} ${head.cx + head.r} ${head.cy - 34} ${head.cx + head.r + 1} ${head.cy} C${head.cx + 16} ${head.cy - 20} ${head.cx - 16} ${head.cy - 20} ${head.cx - head.r - 1} ${head.cy}Z`}
              fill={look.hair}
            />
          )}
          {look.hairStyle === 'curly' && (
            <g fill={look.hair}>
              {[-20, -12, -4, 4, 12, 20].map((dx, i) => (
                <circle cx={head.cx + dx} cy={head.cy - head.r + 6 - (Math.abs(dx) < 10 ? 4 : 0) + (i % 2)} r="6" />
              ))}
            </g>
          )}
          {look.hairStyle === 'short' && (
            <g fill={look.hairShade} opacity="0.55">
              {[-8, -3, 2, 7, 12].map((dx) => (
                <circle cx={head.cx + dx} cy={head.cy + 20 + (Math.abs(dx) > 8 ? -2 : 0)} r="0.9" />
              ))}
            </g>
          )}
          {ov.has('headwrap') && (
            <path
              d={`M${head.cx - head.r} ${head.cy - 10} C${head.cx - 10} ${head.cy - 20} ${head.cx + 10} ${head.cy - 20} ${head.cx + head.r} ${head.cy - 10} L${head.cx + head.r} ${head.cy - 2} C${head.cx + 10} ${head.cy - 12} ${head.cx - 10} ${head.cy - 12} ${head.cx - head.r} ${head.cy - 2}Z`}
              fill="#f7f7f7"
              stroke="#d9dde1"
            />
          )}

          {ov.has('plaster') && (
            <g transform={`translate(${head.cx + 6} ${head.cy - 16}) rotate(-18)`}>
              <rect x="-8" y="-3" width="16" height="6" rx="3" fill="#f2c9a0" stroke="#d8a979" stroke-width="0.8" />
              <rect x="-3" y="-2" width="6" height="4" rx="1" fill="#e8b889" />
            </g>
          )}

          {/* cheeks */}
          {(ov.has('flushed') || stage === 'cured' || ov.has('face_swelling')) && (
            <g fill={stage === 'cured' ? '#f39a9a' : '#e76f6f'} opacity={stage === 'cured' ? 0.35 : 0.45}>
              <ellipse cx={eyeL - 3} cy={head.cy + 8} rx="6" ry="3.5" />
              <ellipse cx={eyeR + 3} cy={head.cy + 8} rx="6" ry="3.5" />
            </g>
          )}
          {(ov.has('thin') || ov.has('cachexia')) && (
            <g fill={shade} opacity={ov.has('cachexia') ? 0.75 : 0.45}>
              <ellipse cx={eyeL - 2} cy={head.cy + 10} rx="5" ry="6" />
              <ellipse cx={eyeR + 2} cy={head.cy + 10} rx="5" ry="6" />
            </g>
          )}

          {/* eyes */}
          {ov.has('raccoon_eyes') && (
            <g fill="#5b3a63" opacity="0.6">
              <ellipse cx={eyeL} cy={eyeY + 1} rx="8" ry="6.5" />
              <ellipse cx={eyeR} cy={eyeY + 1} rx="8" ry="6.5" />
            </g>
          )}
          {eyesClosed ? (
            <g stroke="#3a2a24" stroke-width="1.8" fill="none" stroke-linecap="round">
              <path d={`M${eyeL - 5} ${eyeY} q5 3.5 10 0`} />
              <path d={`M${eyeR - 5} ${eyeY} q5 3.5 10 0`} />
            </g>
          ) : (
            <g>
              {[eyeL, eyeR].map((x, i) => (
                <g>
                  <ellipse cx={x} cy={eyeY} rx="4.4" ry="3.6" fill={ov.has('jaundice') ? '#f2e6a6' : '#fbfbfb'} />
                  <circle class={ov.has('dancing_eyes') ? 'pupil pupil--dance' : 'pupil'} cx={x + 0.5} cy={eyeY + 0.3} r="2.3" fill="#2b211c" />
                  {/* eyelids: blink animation, heavy lids, ptosis on the right eye */}
                  <rect
                    class="eyelid"
                    x={x - 5.5}
                    y={eyeY - 4.5}
                    width="11"
                    height={eyesHeavy ? 5 : ov.has('ptosis') && i === 1 ? 6.5 : 1}
                    fill={skin}
                  />
                </g>
              ))}
            </g>
          )}
          {/* brows */}
          <g stroke={look.hairStyle === 'short' ? '#8e949b' : look.hair} stroke-width="2" stroke-linecap="round" fill="none">
            <path d={frown ? `M${eyeL - 6} ${eyeY - 7} L${eyeL + 4} ${eyeY - 5}` : `M${eyeL - 6} ${eyeY - 7} q5 -2 10 0`} />
            <path d={frown ? `M${eyeR + 6} ${eyeY - 7} L${eyeR - 4} ${eyeY - 5}` : `M${eyeR - 4} ${eyeY - 7} q5 -2 10 0`} />
          </g>
          {/* nose */}
          <path d={`M${head.cx} ${head.cy} q3 5 -1 7`} stroke={shade} stroke-width="1.6" fill="none" stroke-linecap="round" />
          {/* mouth */}
          {smile ? (
            <path d={`M${head.cx - 8} ${mouthY - 1} q8 8 16 0`} stroke={look.lips} stroke-width="2.2" fill="#fff" stroke-linejoin="round" />
          ) : frown && stage !== 'deceased' ? (
            <path d={`M${head.cx - 6} ${mouthY + 2} q6 -4 12 0`} stroke={look.lips} stroke-width="2" fill="none" stroke-linecap="round" />
          ) : (
            <path d={`M${head.cx - 5} ${mouthY} q5 ${stage === 'stable' ? 3 : 1} 10 0`} stroke={look.lips} stroke-width="2" fill="none" stroke-linecap="round" />
          )}
          {ov.has('bruises') && (
            <ellipse cx={head.cx + 13} cy={head.cy + 19} rx="4" ry="2.8" fill="#6b4a86" opacity="0.4" />
          )}
          {/* skin nodules */}
          {ov.has('spots') && (
            <g fill="#5c5ca8" opacity="0.8">
              <circle cx={head.cx - 14} cy={head.cy + 14} r="1.6" />
              <circle cx={head.cx + 16} cy={head.cy - 8} r="1.4" />
              <circle cx={head.cx + 12} cy={head.cy + 16} r="1.2" />
            </g>
          )}
          {/* nasal cannula */}
          {ov.has('cannula') && stage !== 'critical' && stage !== 'deceased' && (
            <path
              d={`M${head.cx - head.r + 2} ${head.cy + 2} C${head.cx - 16} ${head.cy + 14} ${head.cx - 4} ${head.cy + 9} ${head.cx} ${head.cy + 8} C${head.cx + 4} ${head.cy + 9} ${head.cx + 16} ${head.cy + 14} ${head.cx + head.r - 2} ${head.cy + 2}`}
              stroke="#cfeaf5"
              stroke-width="2.2"
              fill="none"
            />
          )}
          {/* oxygen mask when critical */}
          {stage === 'critical' && (
            <g>
              <path d={`M${head.cx - head.r + 1} ${head.cy} L${head.cx - 12} ${head.cy + 6} M${head.cx + head.r - 1} ${head.cy} L${head.cx + 12} ${head.cy + 6}`} stroke="#a3d7ee" stroke-width="1.6" />
              <ellipse cx={head.cx} cy={head.cy + 11} rx="12" ry="10" fill="#d9f0fa" opacity="0.7" stroke="#a3d7ee" />
            </g>
          )}
        </g>

        {/* cough puffs */}
        {ov.has('cough') && stage !== 'deceased' && stage !== 'critical' && (
          <g class="cough" stroke="#dfe7ee" stroke-width="2" fill="none" stroke-linecap="round">
            <path d={`M${head.cx + 22} ${mouthY - 2} q6 -3 10 0`} />
            <path d={`M${head.cx + 26} ${mouthY + 5} q7 -3 12 0`} />
          </g>
        )}

        {/* blanket (breathing) */}
        <g class="breath" style={{ animationDuration: breathe }}>
          <path
            d={`M${head.cx - 30} 246 C${head.cx + 10} 232 ${head.cx + 60} 234 ${bodyEnd - 30} 238 C${bodyEnd - 8} 236 ${bodyEnd + 6} 244 ${bodyEnd + 8} 262 L${head.cx - 34} 264 Z`}
            fill={look.blanket}
          />
          <path d={`M${head.cx - 28} 247 C${head.cx + 10} 236 ${head.cx + 60} 238 ${bodyEnd - 30} 241`} stroke="#ffffff" stroke-width="3" fill="none" opacity="0.8" />
          {ov.has('belly') && <ellipse cx={head.cx + 86} cy="238" rx="30" ry="12" fill={look.blanket} stroke={look.blanketShade} />}
          <path d={`M${head.cx + 120} 256 q30 -8 60 0`} stroke={look.blanketShade} stroke-width="2" fill="none" />
          <ellipse cx={bodyEnd - 14} cy="244" rx="14" ry="10" fill={look.blanket} stroke={look.blanketShade} />
        </g>

        {/* arm on top of the blanket with the IV: the sleeve starts inside the
            shoulder, so it reads as one limb over the blanket's edge */}
        <g>
          <path d={`M${head.cx + 22} 231 C${head.cx + 44} 236 ${head.cx + 68} 245 262 248`} stroke={look.gown} stroke-width="13" stroke-linecap="round" fill="none" />
          <path d="M236 246 C246 247 256 248 268 248" stroke={skin} stroke-width="10" stroke-linecap="round" />
          <ellipse cx="274" cy="248" rx="7" ry="5.5" fill={skin} />
          <rect x="250" y="243" width="9" height="9" rx="1.5" fill="#f5f2e8" opacity="0.95" />
          {ov.has('bruises') && (
            <g>
              <ellipse cx="245" cy="247" rx="4.5" ry="3" fill="#6b4a86" opacity="0.55" />
              <ellipse cx="245" cy="247" rx="2.2" ry="1.4" fill="#4a2f63" opacity="0.5" />
              <ellipse cx="266" cy="249" rx="3.2" ry="2.4" fill="#8a7a3e" opacity="0.45" />
            </g>
          )}
          {ov.has('spots') && (
            <g fill="#5c5ca8" opacity="0.8">
              <circle cx="240" cy="246" r="1.5" />
              <circle cx="264" cy="250" r="1.2" />
            </g>
          )}
        </g>

        {ov.has('sticker') && (
          <path
            d="M276 238 l2.2 4.6 5 .6 -3.7 3.4 1 5 -4.5 -2.5 -4.5 2.5 1 -5 -3.7 -3.4 5 -.6z"
            fill="#f7c948"
            stroke="#c99a18"
            stroke-width="0.8"
          />
        )}
        {ov.has('pills') && (
          <g transform="translate(292 228)">
            <path d="M0 0 h14 l-2 11 h-10z" fill="#ffffff" stroke="#c9d1d8" />
            <circle cx="5" cy="-1" r="2" fill="#f0a3c0" />
            <circle cx="9" cy="-1.5" r="2" fill="#9fd4f0" />
          </g>
        )}
        {ov.has('crayons') && (
          <g transform="translate(296 250)">
            <rect x="0" y="0" width="16" height="4" rx="1.5" fill="#8b5cf6" transform="rotate(-12)" />
            <rect x="10" y="4" width="16" height="4" rx="1.5" fill="#ef4444" transform="rotate(18 18 6)" />
            <rect x="-6" y="6" width="16" height="4" rx="1.5" fill="#22c55e" transform="rotate(6)" />
          </g>
        )}
        {ov.has('glitter') && (
          <g class="glitter">
            {GLITTER.map(([x, y, c], i) => (
              <path key={i} d={`M${x} ${y - 3} L${x + 1} ${y - 1} L${x + 3} ${y} L${x + 1} ${y + 1} L${x} ${y + 3} L${x - 1} ${y + 1} L${x - 3} ${y} L${x - 1} ${y - 1}Z`} fill={c} />
            ))}
          </g>
        )}

        {/* Clover the rabbit (unless he's been sent to the laundry) */}
        {look.prop === 'rabbit' && !ov.has('clover_missing') && (
          <g transform={stage === 'cured' ? 'translate(214 196) rotate(-10)' : 'translate(118 214)'}>
            <ellipse cx="14" cy="26" rx="13" ry="11" fill="#e8e6ef" />
            <circle cx="14" cy="12" r="9" fill="#efedf5" />
            <ellipse cx="9" cy="-2" rx="3.2" ry="10" fill="#efedf5" transform="rotate(-12 9 -2)" />
            <ellipse cx="19" cy="-2" rx="3.2" ry="10" fill="#efedf5" transform="rotate(12 19 -2)" />
            <ellipse cx="9" cy="-2" rx="1.4" ry="6.5" fill="#f3b7c8" transform="rotate(-12 9 -2)" />
            <ellipse cx="19" cy="-2" rx="1.4" ry="6.5" fill="#f3b7c8" transform="rotate(12 19 -2)" />
            <circle cx="11" cy="11" r="1.2" fill="#3a3340" />
            <circle cx="17" cy="11" r="1.2" fill="#3a3340" />
            <circle cx="14" cy="14.5" r="1.3" fill="#e58aa5" />
          </g>
        )}
      </g>

      {/* balloons when cured */}
      {stage === 'cured' && (
        <g class="balloons">
          <path d="M404 250 C396 200 380 170 372 132 M404 250 C408 200 420 170 430 126 M404 250 C402 210 400 180 400 112" stroke="#d6dde3" stroke-width="1.2" fill="none" />
          <ellipse cx="372" cy="118" rx="15" ry="18" fill="#ef6f7d" />
          <ellipse cx="430" cy="112" rx="15" ry="18" fill="#3ecfb0" />
          <ellipse cx="400" cy="96" rx="15" ry="18" fill="#f7c948" />
        </g>
      )}

      {/* lighting */}
      {stage === 'cured' && <rect width={W} height={H} fill="url(#warm)" />}
      {dim > 0 && <rect width={W} height={H} fill="#050a12" opacity={dim} />}
      {flash && <rect class="flash" width={W} height={H} fill="#ff3b3b" />}
    </svg>
  );
}
