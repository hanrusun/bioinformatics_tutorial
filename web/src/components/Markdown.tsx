import { renderMarkdown } from '../lib/markdown';

export function Markdown({ src, class: cls }: { src: string; class?: string }) {
  return <div class={`md ${cls ?? ''}`} dangerouslySetInnerHTML={{ __html: renderMarkdown(src) }} />;
}
