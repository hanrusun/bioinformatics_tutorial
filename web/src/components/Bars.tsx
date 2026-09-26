import type { GameView } from '../types';

interface TopProps {
  game: GameView;
  difficultyLabel: string;
  onMenu: () => void;
}

export function TopBar({ game, difficultyLabel, onMenu }: TopProps) {
  return (
    <header class="topbar">
      <button class="brand" onClick={onMenu} title="Back to campaigns">
        <span class="brand__mark">✚</span> CURE LAB
      </button>
      <span class="topbar__campaign">{game.campaign_title}</span>
      <span class="chip">Day {game.day}</span>
      <span class="chip chip--muted">{difficultyLabel}</span>
      <span class="topbar__spacer" />
      {game.paused && <span class="chip chip--paused">⏸ Clock paused while code runs</span>}
      <span
        class="chip chip--rp"
        data-testid="rp"
        title="Research Points: earn them by reading notebook pages and writing your own notes; spend them on hints."
      >
        ◆ {game.rp} RP
      </span>
    </header>
  );
}

function Meter({ label, value, tone, testid, detail }: { label: string; value: number; tone: string; testid: string; detail?: string }) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div class={`meter meter--${tone}`} data-testid={testid}>
      <div class="meter__head">
        <span class="meter__label">{label}</span>
        <span class="meter__value">{Math.round(v)}%</span>
      </div>
      <div class="meter__track" role="progressbar" aria-label={label} aria-valuenow={Math.round(v)} aria-valuemin={0} aria-valuemax={100}>
        <div class="meter__fill" style={{ width: `${v}%` }} />
      </div>
      {detail && <span class="meter__detail">{detail}</span>}
    </div>
  );
}

export function BottomBar({ game }: { game: GameView }) {
  return (
    <footer class="bottombar">
      <Meter label="CURE RESEARCH" value={game.research} tone="cure" testid="cure" detail="missions and journal club" />
      <Meter label="LETHALITY" value={game.severity} tone="lethal" testid="lethality" detail={`${game.errors} mistakes · ${game.traits.length} traits evolved`} />
      <Meter label="HEALTH" value={game.health} tone="health" testid="health" detail={`falling ${game.decline_per_hour.toFixed(1)}/h`} />
    </footer>
  );
}
