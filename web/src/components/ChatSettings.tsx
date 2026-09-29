import { useEffect, useState } from 'preact/hooks';
import { api } from '../api';
import type { ChatSettingsData, ConsultStatus } from '../types';

interface Props {
  /** "consult" (the doctor) or "bedside" (the patient) */
  chat: 'consult' | 'bedside';
  onStatus: (s: ConsultStatus) => void;
  onNotice: (text: string, tone?: 'info' | 'bad') => void;
}

/** The chat status the rest of the page reads (without the settings extras). */
function status(d: ChatSettingsData): ConsultStatus {
  const { enabled, provider, label, model, bedside_model, effort, bedside_effort } = d;
  return { enabled, provider, label, model, bedside_model, effort, bedside_effort };
}

/**
 * Choose this chat's model and effort in the game. Saved with the profile and
 * used from the next message; empty values keep the defaults from .env. Keys
 * and tokens stay in .env: this page never sees them.
 */
export function ChatSettings({ chat, onStatus, onNotice }: Props) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<ChatSettingsData | null>(null);
  const [model, setModel] = useState('');
  const [effort, setEffort] = useState('');
  const [busy, setBusy] = useState(false);

  const show = (d: ChatSettingsData) => {
    setData(d);
    setModel(d.choices[chat].model);
    setEffort(d.choices[chat].effort);
  };

  useEffect(() => {
    if (open) api.chatSettings().then(show).catch((e) => onNotice(String(e), 'bad'));
  }, [open]);

  const save = async (next: { model: string; effort: string }) => {
    setBusy(true);
    try {
      const d = await api.saveChatSettings({ [chat]: next });
      show(d);
      onStatus(status(d));
      onNotice(next.model || next.effort ? 'Chat settings saved.' : 'Back to the default model and effort.', 'info');
    } catch (err) {
      onNotice((err as Error).message, 'bad');
    } finally {
      setBusy(false);
    }
  };

  const fallback = data?.defaults[chat];
  const listId = `${chat}-model-suggestions`;
  return (
    <div class="chat-settings">
      <button class="btn btn--ghost" onClick={() => setOpen(!open)} aria-expanded={open} data-testid={`${chat}-settings`}>
        ⚙ Model &amp; effort
      </button>
      {open && data && (
        <form
          class="chat-settings__form"
          onSubmit={(e) => {
            e.preventDefault();
            save({ model: model.trim(), effort });
          }}
        >
          <label>
            Model{' '}
            <input
              list={listId}
              value={model}
              placeholder={fallback?.model ? `default: ${fallback.model}` : "default: your plan's model"}
              onInput={(e) => setModel((e.target as HTMLInputElement).value)}
              spellcheck={false}
              data-testid={`${chat}-model`}
            />
          </label>
          <datalist id={listId}>
            {data.suggestions.models.map((m) => (
              <option value={m} />
            ))}
          </datalist>
          <label>
            Effort{' '}
            <select value={effort} onChange={(e) => setEffort((e.target as HTMLSelectElement).value)} data-testid={`${chat}-effort`}>
              <option value="">{fallback?.effort ? `default (${fallback.effort})` : "default (the model's own)"}</option>
              {data.suggestions.efforts.map((level) => (
                <option value={level}>{level}</option>
              ))}
            </select>
          </label>
          <button class="btn btn--primary btn--tiny" type="submit" disabled={busy} data-testid={`${chat}-settings-save`}>
            Save
          </button>
          <button class="btn btn--ghost btn--tiny" type="button" disabled={busy} onClick={() => save({ model: '', effort: '' })}>
            Reset to defaults
          </button>
          <p class="muted chat-settings__note">
            Pick a suggestion or type any model name {data.label} offers. More effort means more careful answers, but
            slower and, on a paid API, dearer. Saved with your profile and used from the next message; the defaults
            come from your .env file, and your key stays there.
          </p>
        </form>
      )}
    </div>
  );
}
