import { useEffect, useRef } from 'preact/hooks';
import { EditorState } from '@codemirror/state';
import { EditorView, keymap, lineNumbers, highlightActiveLine, drawSelection } from '@codemirror/view';
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands';
import {
  StreamLanguage,
  bracketMatching,
  indentOnInput,
  syntaxHighlighting,
  HighlightStyle,
} from '@codemirror/language';
import { closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete';
import { tags as t } from '@lezer/highlight';
import { r } from '@codemirror/legacy-modes/mode/r';
import { python } from '@codemirror/legacy-modes/mode/python';

const highlight = HighlightStyle.define([
  { tag: t.keyword, color: '#c792ea' },
  { tag: [t.string, t.special(t.string)], color: '#c3e88d' },
  { tag: t.number, color: '#f78c6c' },
  { tag: t.comment, color: '#6b7f8f', fontStyle: 'italic' },
  { tag: [t.variableName, t.name], color: '#e6edf3' },
  { tag: [t.function(t.variableName), t.propertyName], color: '#82aaff' },
  { tag: [t.operator, t.punctuation], color: '#89ddff' },
  { tag: [t.atom, t.bool], color: '#ffcb6b' },
]);

const theme = EditorView.theme(
  {
    '&': { backgroundColor: '#0b1117', color: '#e6edf3', fontSize: '13.5px', height: '100%' },
    '.cm-content': { fontFamily: 'var(--mono)', caretColor: '#3ecfb0', padding: '10px 0' },
    '.cm-gutters': { backgroundColor: '#0b1117', color: '#4b5b68', border: 'none' },
    '.cm-activeLine': { backgroundColor: '#111b24' },
    '.cm-activeLineGutter': { backgroundColor: '#111b24' },
    '&.cm-focused .cm-cursor': { borderLeftColor: '#3ecfb0' },
    '&.cm-focused .cm-selectionBackground, ::selection': { backgroundColor: '#1f3b4d' },
    '.cm-scroller': { overflow: 'auto' },
  },
  { dark: true },
);

interface Props {
  /** Text to load into the editor. Only applied when `version` changes, so
   * echoes of the learner's own typing never get written back (that feedback
   * loop can ping-pong stale values forever when typing fast). */
  value: string;
  version: number;
  language: string;
  onChange: (value: string) => void;
  onRun: () => void;
  onSubmit: () => void;
}

export function CodeEditor({ value, version, language, onChange, onRun, onSubmit }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const handlers = useRef({ onChange, onRun, onSubmit });
  handlers.current = { onChange, onRun, onSubmit };

  useEffect(() => {
    if (!host.current) return;
    const lang = StreamLanguage.define(language === 'python' ? python : r);
    const state = EditorState.create({
      doc: value,
      extensions: [
        lineNumbers(),
        history(),
        drawSelection(),
        highlightActiveLine(),
        indentOnInput(),
        bracketMatching(),
        closeBrackets(),
        lang,
        syntaxHighlighting(highlight),
        theme,
        EditorView.lineWrapping,
        keymap.of([
          { key: 'Mod-Enter', run: () => (handlers.current.onRun(), true) },
          { key: 'Shift-Mod-Enter', run: () => (handlers.current.onSubmit(), true) },
          ...closeBracketsKeymap,
          ...defaultKeymap,
          ...historyKeymap,
          indentWithTab,
        ]),
        EditorView.updateListener.of((u) => {
          if (u.docChanged) handlers.current.onChange(u.state.doc.toString());
        }),
        EditorView.contentAttributes.of({ 'aria-label': 'Code editor' }),
      ],
    });
    view.current = new EditorView({ state, parent: host.current });
    return () => view.current?.destroy();
  }, [language]);

  // explicit replacements only (mission loaded, starter code restored)
  useEffect(() => {
    const v = view.current;
    if (v && v.state.doc.toString() !== value) {
      v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value } });
    }
  }, [version]);

  return <div class="editor" ref={host} />;
}
