import type { MissionSummary, QuizView } from '../types';

interface Props {
  missions: MissionSummary[];
  quizzes: QuizView[];
  selected: string | null;
  onSelect: (id: string) => void;
}

export function MissionList({ missions, quizzes, selected, onSelect }: Props) {
  return (
    <ol class="mission-list" aria-label="Missions">
      {missions.map((m, i) => {
        const openQuizzes = quizzes.filter((q) => q.after === m.id && q.status === 'available').length;
        return (
          <li key={m.id}>
            <button
              class={`mission-item mission-item--${m.status}${selected === m.id ? ' is-selected' : ''}`}
              disabled={m.status === 'locked'}
              onClick={() => onSelect(m.id)}
              data-mission={m.id}
            >
              <span class="mission-item__num">{m.status === 'completed' ? '✓' : m.status === 'locked' ? '🔒' : i + 1}</span>
              <span class="mission-item__title">{m.title}</span>
              <span class="mission-item__pts">+{m.points}%</span>
              {m.wrong > 0 && <span class="mission-item__wrong" title="Wrong attempts">✗{m.wrong}</span>}
              {openQuizzes > 0 && <span class="mission-item__quiz" title="Journal club questions unlocked">?{openQuizzes}</span>}
            </button>
          </li>
        );
      })}
    </ol>
  );
}
