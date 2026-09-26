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
      <path d="M87 36 V148 M26 92 H148" stroke="#56707f" stroke-width="4" />
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

        {/* arm on top of the blanket with the IV */}
        <g>
          <path d={`M${head.cx + 30} 238 C${head.cx + 50} 240 ${head.cx + 70} 244 262 248`} stroke={look.gown} stroke-width="13" stroke-linecap="round" fill="none" />
          <path d="M236 246 C246 247 256 248 268 248" stroke={skin} stroke-width="10" stroke-linecap="round" />
          <ellipse cx="274" cy="248" rx="7" ry="5.5" fill={skin} />
          <rect x="250" y="243" width="9" height="9" rx="1.5" fill="#f5f2e8" opacity="0.95" />
          {ov.has('spots') && (
            <g fill="#5c5ca8" opacity="0.8">
              <circle cx="240" cy="246" r="1.5" />
              <circle cx="264" cy="250" r="1.2" />
            </g>
          )}
        </g>

        {/* Clover the rabbit */}
        {look.prop === 'rabbit' && (
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
