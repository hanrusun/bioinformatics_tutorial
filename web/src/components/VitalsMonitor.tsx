import { useEffect, useRef } from 'preact/hooks';
import type { Vitals } from '../types';
import { formatVital, vitalTone } from '../lib/format';

interface Props {
  vitals: Vitals;
  child: boolean;
  alarm: boolean;
}

// One heartbeat of a stylised ECG (P, QRS, T), phase in [0, 1).
function ecg(phase: number): number {
  const g = (mu: number, sigma: number, a: number) => a * Math.exp(-((phase - mu) ** 2) / (2 * sigma ** 2));
  return g(0.18, 0.025, 0.12) - g(0.36, 0.008, 0.12) + g(0.39, 0.012, 1) - g(0.42, 0.01, 0.25) + g(0.66, 0.05, 0.28);
}

function pleth(phase: number): number {
  const g = (mu: number, sigma: number, a: number) => a * Math.exp(-((phase - mu) ** 2) / (2 * sigma ** 2));
  return g(0.3, 0.09, 1) + g(0.62, 0.07, 0.35);
}

/** Bedside monitor: sweeping ECG + pleth traces and the vital signs. */
export function VitalsMonitor({ vitals, child, alarm }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const hrRef = useRef(vitals.hr);
  hrRef.current = vitals.hr;

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const ctx = el.getContext('2d');
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const w = el.clientWidth || 300;
    const h = el.clientHeight || 110;
    el.width = w * dpr;
    el.height = h * dpr;
    ctx.scale(dpr, dpr);
    const speed = 70; // px per second
    let x = 0;
    let beat = 0;
    let breath = 0;
    let last = performance.now();
    let prev = [h * 0.32, h * 0.8];
    let raf = 0;
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    const frame = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const hr = hrRef.current;
      const steps = Math.max(1, Math.round(speed * dt));
      for (let i = 0; i < steps; i++) {
        const t = dt / steps;
        beat = hr > 0 ? (beat + (hr / 60) * t) % 1 : 0;
        breath = (breath + t * 0.3) % 1;
        const ecgY = h * 0.34 - (hr > 0 ? ecg(beat) * h * 0.26 : 0);
        const plY = h * 0.84 - (hr > 0 ? pleth(beat) * h * 0.14 : 0);
        const nx = x + 1;
        ctx.clearRect(nx, 0, 8, h);
        ctx.lineWidth = 1.6;
        ctx.strokeStyle = alarm ? '#ff6b6b' : '#3ee07a';
        ctx.beginPath();
        ctx.moveTo(x, prev[0]);
        ctx.lineTo(nx, ecgY);
        ctx.stroke();
        ctx.strokeStyle = '#59c7f0';
        ctx.beginPath();
        ctx.moveTo(x, prev[1]);
        ctx.lineTo(nx, plY);
        ctx.stroke();
        prev = [ecgY, plY];
        x = nx >= w ? 0 : nx;
        if (x === 0) prev = [ecgY, plY];
      }
      if (!reduce) raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [alarm]);

  const cell = (key: keyof Vitals, label: string, unit: string) => (
    <div class={`vital vital--${vitalTone(key, vitals[key], child)}`} data-vital={key}>
      <span class="vital__label">{label}</span>
      <span class="vital__value">{formatVital(key, vitals)}</span>
      <span class="vital__unit">{unit}</span>
    </div>
  );

  return (
    <div class={`monitor${alarm ? ' monitor--alarm' : ''}`} aria-label="Vital signs monitor">
      <canvas ref={canvas} class="monitor__trace" aria-hidden="true" />
      <div class="monitor__numbers">
        {cell('hr', 'HR', 'bpm')}
        {cell('spo2', 'SpO₂', '%')}
        {cell('sbp', 'BP', 'mmHg')}
        {cell('rr', 'RR', '/min')}
        {cell('temp', 'Temp', '°C')}
      </div>
    </div>
  );
}
