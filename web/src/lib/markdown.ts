import { marked } from 'marked';
import DOMPurify from 'dompurify';

marked.setOptions({ gfm: true, breaks: false });

/** Render Markdown to sanitized HTML (briefings, hints, the learner's notes). */
export function renderMarkdown(src: string): string {
  const html = marked.parse(src ?? '', { async: false }) as string;
  return DOMPurify.sanitize(html, { ADD_ATTR: ['target', 'rel'] });
}
