import { useState } from 'preact/hooks';
import { api, bedsideSay } from '../api';
import type { BedsideData, ConsultStatus, GameView, PatientInfo, Snapshot } from '../types';
import { ChatActions, ChatThread, useChat } from './Chat';
import { ChatSettings } from './ChatSettings';
import { ChatSetup } from './ConsultPanel';

interface Props {
  game: GameView;
  patient: PatientInfo;
  status: ConsultStatus;
  cursor: () => number;
  onSnapshot: (s: Snapshot) => void;
  onNotice: (text: string, tone?: 'info' | 'bad') => void;
  /** the chats' model and effort changed in the game */
  onStatus: (s: ConsultStatus) => void;
}

/** Talk to the patient, who answers in character from their chart. */
export function BedsidePanel({ game, patient, status, cursor, onSnapshot, onNotice, onStatus }: Props) {
  const [info, setInfo] = useState<BedsideData | null>(null);
  const chat = useChat(
    {
      cursor,
      onSnapshot,
      onNotice,
      history: () => api.bedsideHistory().then((d) => (setInfo(d), d)),
      clear: api.bedsideClear,
      save: api.bedsideSave,
    },
    [game.started_at, status.enabled],
  );
  const name = patient.first_name;

  if (!status.enabled)
    return (
      <ChatSetup
        id="bedside"
        title={`Talk to ${name}`}
        what={`Sit with ${name} and ask how things are going. A chatbot plays ${name}, in character, from the chart.`}
      />
    );

  const toddler = info?.toddler ?? false;
  const examples = toddler
    ? [`How are you feeling, ${name}?`, 'Can I listen to your heart?', "What's your favorite toy?"]
    : ['How are you feeling?', 'Did you manage to sleep?', 'Is anything worrying you?'];

  return (
    <div class="consult consult--bedside" data-testid="bedside">
      <header class="consult__head">
        <div>
          <h3>Talk to {name}</h3>
          <p class="muted" data-testid="bedside-model-line">
            {status.label} ({status.bedside_model}
            {status.bedside_effort ? `, ${status.bedside_effort} effort` : ''}) plays {name} · free, but the clock
            keeps running
          </p>
        </div>
        <ChatActions chat={chat} id="bedside" whole="whole chat" />
        <ChatSettings chat="bedside" onStatus={onStatus} onNotice={onNotice} />
      </header>

      <p class="consult__context muted">
        {toddler
          ? `${name} is ${patient.age}: expect babble and emojis. ${info?.companion || 'Family'} is sometimes in the room and may chime in.`
          : `${name} knows what a patient would: how the illness feels and what the doctors have said, not the lab work.`}
      </p>

      <ChatThread
        chat={chat}
        id="bedside"
        tone="patient"
        who={name}
        meta={(m) => `You · day ${m.day}`}
        empty={
          game.status === 'lost'
            ? ''
            : game.status === 'won'
              ? `${name} is getting ready to go home. Say goodbye, for example:`
              : `${name} is on the ward. Say hello, for example:`
        }
        examples={examples}
        thinking={toddler ? `${name} looks up at you…` : `${name} is thinking…`}
        placeholder={`Say something to ${name}…`}
        sendLabel="Say"
        onSend={() => chat.ask(bedsideSay)}
        closed={game.status === 'lost' ? `${name} has died. Your conversations are kept here to read.` : undefined}
      />
    </div>
  );
}
