import { useCallback, useEffect, useRef, useState } from 'preact/hooks';
import { api } from './api';
import type { CampaignMeta, GameEvent, Meta, Snapshot } from './types';
import { load, save } from './lib/storage';
import { TitleScreen } from './components/TitleScreen';
import { IntakeModal } from './components/IntakeModal';
import { TopBar, BottomBar } from './components/Bars';
import { PatientPanel } from './components/PatientPanel';
import { MissionList } from './components/MissionList';
import { MissionView } from './components/MissionView';
import { QuizPanel } from './components/QuizPanel';
import { NotebookPanel } from './components/NotebookPanel';
import { BedsidePanel } from './components/BedsidePanel';
import { ConsultPanel } from './components/ConsultPanel';
import { DiseasePanel } from './components/DiseasePanel';
import { EndScreen } from './components/EndScreen';
import { TraitPopup, Toasts, type Notice } from './components/Events';

type Tab = 'missions' | 'journal' | 'notebook' | 'disease' | 'consult' | 'bedside';
let noticeId = 1;

export function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [screen, setScreen] = useState<'title' | 'game'>('title');
  const [intake, setIntake] = useState<{ campaign: CampaignMeta; difficulty: string } | null>(null);
  const [starting, setStarting] = useState(false);
  const [tab, setTab] = useState<Tab>((load('curelab:tab') as Tab) ?? 'missions');
  const [mission, setMission] = useState<string | null>(null);
  const [focusPage, setFocusPage] = useState<string | null>(null);
  const [popups, setPopups] = useState<GameEvent[]>([]);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [flash, setFlash] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cursor = useRef(0);
  const seen = useRef(new Set<number>());

  const notify = useCallback((text: string, tone: Notice['tone'] = 'info') => {
    setNotices((n) => [...n.slice(-4), { id: noticeId++, text, tone }]);
  }, []);

  const apply = useCallback(
    (s: Snapshot, silent = false) => {
      // ignore a stale response for the same game that arrives after a newer one
      setSnap((prev) =>
        prev?.game && s.game && prev.game.started_at === s.game.started_at && s.cursor < prev.cursor
          ? { ...s, game: prev.game }
          : s,
      );
      const fresh = s.events.filter((e) => !seen.current.has(e.id));
      fresh.forEach((e) => seen.current.add(e.id));
      cursor.current = Math.max(cursor.current, s.cursor);
      if (silent) return;
      for (const e of fresh) {
        if (e.kind === 'trait') {
          setPopups((p) => [...p, e]);
          setFlash(true);
          setTimeout(() => setFlash(false), 900);
        } else if (e.kind === 'mission') notify(`✓ ${e.title}: cure +${e.data.points}%`, 'good');
        else if (e.kind === 'quiz') notify(`✓ Journal club: cure +${e.data.points}%`, 'good');
        else if (e.kind === 'rp') notify(`◆ ${e.title}: ${e.text}`, 'rp');
        else if (e.kind === 'stage') notify(e.text, 'warn');
      }
    },
    [notify],
  );

  const refreshMeta = () => api.meta().then(setMeta);

  // boot
  useEffect(() => {
    refreshMeta().catch((e) => setError(String(e)));
    api
      .state(0)
      .then((s) => {
        apply(s, true);
        if (s.game?.status === 'playing') setScreen('game');
      })
      .catch((e) => setError(String(e)));
  }, []);

  // heartbeat: the clock only runs while this tab is visible
  const playing = snap?.game?.status === 'playing' && screen === 'game';
  useEffect(() => {
    if (!playing) return;
    const beat = (visible: boolean) =>
      api
        .heartbeat(visible, cursor.current)
        .then((s) => apply(s))
        .catch(() => undefined);
    const onVisibility = () => beat(false); // resync without counting the time away
    document.addEventListener('visibilitychange', onVisibility);
    beat(false);
    const t = setInterval(() => {
      if (document.visibilityState === 'visible') beat(true);
    }, 1000);
    return () => {
      clearInterval(t);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [playing]);

  useEffect(() => save('curelab:tab', tab), [tab]);

  // pick the first open mission by default
  const game = snap?.game ?? null;
  useEffect(() => {
    if (!game) return;
    if (!mission || !game.missions.some((m) => m.id === mission)) {
      const open = game.missions.find((m) => m.status === 'available') ?? game.missions[game.missions.length - 1];
      setMission(open?.id ?? null);
    }
  }, [game?.campaign]);

  const begin = async () => {
    if (!intake) return;
    setStarting(true);
    try {
      seen.current.clear();
      cursor.current = 0;
      const s = await api.start(intake.campaign.id, intake.difficulty);
      apply(s, true);
      setMission(s.game?.missions[0]?.id ?? null);
      setTab('missions');
      setIntake(null);
      setScreen('game');
      refreshMeta();
    } catch (e) {
      notify(String(e), 'bad');
    } finally {
      setStarting(false);
    }
  };

  const toMenu = async () => {
    await refreshMeta();
    setScreen('title');
  };

  if (error) {
    return (
      <main class="fatal">
        <h1>Cure Lab can’t reach its engine</h1>
        <p>{error}</p>
        <p class="muted">Is the container running? Try reloading the page.</p>
      </main>
    );
  }
  if (!meta || !snap) return <main class="loading">Starting the lab…</main>;

  const difficultyLabel = meta.difficulties.find((d) => d.id === game?.difficulty)?.label ?? '';
  const patient = snap.patient;
  const openQuizzes = game?.quizzes.filter((q) => q.status === 'available').length ?? 0;
  const campaign = meta.campaigns.find((c) => c.id === game?.campaign);
  const unlocks = meta.campaigns.find((c) => c.unlock_after === game?.campaign)?.title ?? null;

  return (
    <>
      {screen === 'title' && (
        <TitleScreen
          meta={meta}
          activeEnded={!!game && game.status !== 'playing'}
          onStart={(c, difficulty) => setIntake({ campaign: c, difficulty })}
          onContinue={() => setScreen('game')}
        />
      )}
      {intake && (
        <IntakeModal campaign={intake.campaign} difficulty={intake.difficulty} busy={starting} onBegin={begin} onCancel={() => setIntake(null)} />
      )}

      {screen === 'game' && game && patient && (
        <div class="game">
          <TopBar game={game} difficultyLabel={difficultyLabel} onMenu={toMenu} />
          <div class="game__main">
            <PatientPanel game={game} patient={patient} flash={flash} onTalk={() => setTab('bedside')} />
            <section class="lab" aria-label="Lab">
              <nav class="tabs" role="tablist">
                {(
                  [
                    ['missions', 'Missions'],
                    ['journal', `Journal club${openQuizzes ? ` (${openQuizzes})` : ''}`],
                    ['notebook', 'Lab notebook'],
                    ['disease', 'Disease'],
                    ['consult', 'Consult'],
                    ['bedside', `Talk to ${patient.first_name}`],
                  ] as [Tab, string][]
                ).map(([id, label]) => (
                  <button role="tab" aria-selected={tab === id} class={`tab${tab === id ? ' is-active' : ''}`} onClick={() => setTab(id)} data-tab={id}>
                    {label}
                  </button>
                ))}
              </nav>
              <div class="lab__body">
                {tab === 'missions' && (
                  <div class="missions">
                    <MissionList missions={game.missions} quizzes={game.quizzes} selected={mission} onSelect={setMission} />
                    {mission && (
                      <MissionView
                        key={mission}
                        missionId={mission}
                        game={game}
                        cursor={() => cursor.current}
                        language={meta.pack.editor_mode}
                        onSnapshot={(s) => apply(s)}
                        onOpenPage={(id) => {
                          setFocusPage(id);
                          setTab('notebook');
                        }}
                        onConsult={() => setTab('consult')}
                        onNotice={notify}
                      />
                    )}
                  </div>
                )}
                {tab === 'journal' && <QuizPanel game={game} cursor={() => cursor.current} onSnapshot={(s) => apply(s)} />}
                {tab === 'notebook' && (
                  <NotebookPanel
                    game={game}
                    rules={meta.rules}
                    cursor={() => cursor.current}
                    focus={focusPage}
                    onSnapshot={(s) => apply(s)}
                    onNotice={notify}
                  />
                )}
                {tab === 'disease' && <DiseasePanel game={game} patient={patient} />}
                {tab === 'consult' && (
                  <ConsultPanel
                    game={game}
                    status={meta.consult}
                    missionId={mission}
                    cursor={() => cursor.current}
                    onSnapshot={(s) => apply(s)}
                    onNotice={notify}
                  />
                )}
                {tab === 'bedside' && (
                  <BedsidePanel
                    game={game}
                    patient={patient}
                    status={meta.consult}
                    cursor={() => cursor.current}
                    onSnapshot={(s) => apply(s)}
                    onNotice={notify}
                  />
                )}
              </div>
            </section>
          </div>
          <BottomBar game={game} />
          {game.status !== 'playing' && popups.length === 0 && campaign && (
            <EndScreen
              game={game}
              patient={patient}
              unlocks={game.status === 'won' ? unlocks : null}
              onAgain={() => setIntake({ campaign: meta.campaigns.find((c) => c.id === game.campaign)!, difficulty: game.difficulty })}
              onMenu={toMenu}
              onNotice={notify}
            />
          )}
        </div>
      )}

      {popups[0] && <TraitPopup event={popups[0]} onClose={() => setPopups((p) => p.slice(1))} />}
      <Toasts notices={notices} onDismiss={(id) => setNotices((n) => n.filter((x) => x.id !== id))} />
    </>
  );
}
