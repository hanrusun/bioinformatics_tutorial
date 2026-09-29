import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';

// Drives the real engine (python -m curelab) with the Python fixture pack
// through a whole campaign: admission, a wrong answer, reading the notebook,
// writing notes, buying a hint, passing missions, the journal club, exporting
// the notebook and winning.

async function setCode(page: Page, code: string) {
  await page.click('.cm-content');
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Backspace');
  await page.keyboard.type(code);
}

async function submitAndWait(page: Page) {
  const before = await page.locator('[data-testid="submit-result"]').count();
  await page.click('.btn--submit');
  await expect(page.locator('[data-testid="submit-result"]')).toHaveCount(before + 1);
}

test('a full campaign: learn, fail, read, write, hint, pass, export, win', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('/', { waitUntil: 'domcontentloaded' });

  // title -> intake -> game
  await expect(page.getByRole('heading', { name: 'CURE LAB' })).toBeVisible();
  await expect(page.locator('[data-campaign="demo-two"] button')).toBeDisabled(); // locked until demo-one is won
  await page.click('[data-testid="start-demo-one"]');
  await expect(page.getByRole('dialog')).toContainText('Walter Brandt');
  await page.click('[data-testid="begin"]');
  await expect(page.locator('.patient-panel h2')).toHaveText('Walter Brandt');
  await expect(page.locator('.scene')).toBeVisible();
  await expect(page.locator('[data-mission-view="demo-m01-list"]')).toBeVisible();
  await expect(page.locator('.banner--info', { hasText: 'Bench ready' })).toBeVisible();

  // free run never counts as a mistake
  await setCode(page, 'print(countz)');
  await page.click('.btn--run');
  await expect(page.locator('.entry--run .out--error')).toBeVisible();
  await expect(page.locator('.entry--run .out--help')).toContainText('variable or function');
  await expect(page.locator('[data-testid="lethality"] .meter__value')).toHaveText('0%');

  // wrong submission -> the disease evolves
  await setCode(page, 'counts = [1, 3, 4]');
  await submitAndWait(page);
  await expect(page.locator('[data-testid="trait-popup"]')).toBeVisible();
  await page.click('.popup--trait .btn');
  await expect(page.locator('[data-testid="lethality"] .meter__detail')).toContainText('1 mistakes');
  // a mistake either evolves the disease or (sometimes) triggers a ward event
  await expect(page.locator('.chart .note--trait, .chart .note--event')).toHaveCount(1);

  // no RP yet -> hints are locked
  await expect(page.locator('.btn--hint')).toBeDisabled();

  // notebook: read a page (scroll to the end, wait) -> +2 RP
  await page.click('[data-tab="notebook"]');
  const pageView = page.locator('[data-page="demo-nb01"]');
  await expect(pageView).toBeVisible();
  await pageView.evaluate((el) => el.scrollTo(0, el.scrollHeight));
  await expect(page.locator('[data-testid="mark-read"]')).toBeEnabled({ timeout: 10_000 });
  await page.click('[data-testid="mark-read"]');
  await expect(page.locator('[data-testid="page-read"]')).toBeVisible();
  await expect(page.locator('[data-testid="rp"]')).toContainText('2 RP');

  // own notes: 40+ words after a mission attempt -> +1 RP
  await page.click('[data-testid="new-note"]');
  await page.fill('[data-testid="note-body"]', 'A list keeps values in order and is written with square brackets. '.repeat(5));
  await expect(page.locator('[data-testid="word-count"]')).toHaveClass(/words--ok/);
  await expect(page.locator('[data-testid="rp"]')).toContainText('3 RP');

  // copy my notes to the clipboard, download them as Markdown
  await page.click('[data-testid="copy-notes"]');
  await expect(page.locator('.toast', { hasText: 'clipboard' })).toBeVisible();
  const clip = await page.evaluate(() => navigator.clipboard.readText());
  expect(clip).toContain('A list keeps values in order');
  const [download] = await Promise.all([page.waitForEvent('download'), page.click('[data-testid="download-all"]')]);
  expect(download.suggestedFilename()).toBe('curelab-demo-one-notebook.md');
  const md = readFileSync((await download.path())!, 'utf8');
  expect(md).toContain('# Reference pages');
  expect(md).toContain('A list keeps values in order');

  // spend 1 RP on a hint, then pass the mission
  await page.click('[data-tab="missions"]');
  await page.click('.btn--hint');
  await expect(page.locator('.hint')).toContainText('square brackets');
  await expect(page.locator('[data-testid="rp"]')).toContainText('2 RP');
  await setCode(page, 'counts = [3, 1, 4]');
  await submitAndWait(page);
  await expect(page.locator('[data-testid="submit-result"]').last()).toHaveClass(/banner--good/);
  await expect(page.locator('[data-testid="cure"] .meter__value')).toHaveText('30%');

  // missions 2 and 3
  for (const [id, code] of [
    ['demo-m02-sum', 'total = sum(counts)'],
    ['demo-m03-sort', 'ranked = sorted(counts)'],
  ]) {
    await page.click(`[data-mission="${id}"]`);
    await expect(page.locator(`[data-mission-view="${id}"] .banner--info`, { hasText: 'Bench ready' })).toBeVisible();
    await setCode(page, code);
    await submitAndWait(page);
    await expect(page.locator('[data-testid="submit-result"]').last()).toHaveClass(/banner--good/);
  }
  await expect(page.locator('[data-testid="cure"] .meter__value')).toHaveText('90%');

  // journal club: a wrong answer is struck out, the right one explains itself
  await page.click('[data-tab="journal"]');
  await page.locator('[data-quiz="demo-q01"] .choice').nth(0).click();
  await expect(page.locator('[data-testid="trait-popup"]')).toBeVisible();
  await page.click('.popup--trait .btn');
  await expect(page.locator('[data-quiz="demo-q01"] .choice').nth(0)).toHaveClass(/choice--wrong/);
  await page.locator('[data-quiz="demo-q01"] .choice').nth(1).click();
  await expect(page.locator('[data-quiz="demo-q01"] .quiz__why')).toBeVisible();
  await page.locator('[data-quiz="demo-q02"] .choice').nth(1).click();

  // cured
  await expect(page.locator('[data-testid="end-won"]')).toBeVisible();
  await expect(page.locator('[data-testid="end-won"]')).toContainText('Walter is going home');
  await expect(page.locator('[data-testid="end-won"]')).toContainText('New campaign unlocked');
  await page.screenshot({ path: 'test-results/won.png' });

  // the end screen offers the mission script: briefings as comments, then the passing code
  const [script] = await Promise.all([
    page.waitForEvent('download'),
    page.click('[data-testid="end-won"] [data-testid="download-script"]'),
  ]);
  expect(script.suggestedFilename()).toBe('curelab-demo-one.py');
  const py = readFileSync((await script.path())!, 'utf8');
  expect(py).toContain('# Mission 1:');
  expect(py).toContain('ranked = sorted(counts)');
  expect(py).not.toContain('# (not passed yet)');

  await page.getByRole('button', { name: 'Campaigns' }).click();
  await expect(page.locator('[data-testid="start-demo-two"]')).toBeEnabled();
});

test('the disease tab shows the trait tree', async ({ page }) => {
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.click('[data-testid="start-demo-one"]');
  await page.click('[data-testid="begin"]');
  await page.click('[data-tab="disease"]');
  await expect(page.locator('.disease-panel h2')).toHaveText('Non-small cell lung cancer');
  // traits that haven't evolved stay hidden until the player asks
  await expect(page.locator('.trait--on')).toHaveCount(0);
  await expect(page.locator('[data-trait="cough"]')).toHaveCount(0);
  await expect(page.locator('.tier:not(.tier--events) .trait--hidden').first()).toBeVisible();
  await page.click('[data-testid="reveal-tree"]');
  await expect(page.locator('[data-trait="cough"]')).toBeVisible();
  await expect(page.locator('.tier:not(.tier--events) .trait--hidden')).toHaveCount(0);
  await page.click('[data-testid="reveal-tree"]');
  await expect(page.locator('[data-trait="cough"]')).toHaveCount(0);
});

test('consult another doctor at any point and keep the answer in the notebook', async ({ page }) => {
  await page.request.post('/api/game/abandon'); // an earlier test may have left a game running
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.click('[data-testid="start-demo-one"]');
  await page.click('[data-testid="begin"]');

  // straight from a mission, before any mistake
  await page.click('[data-mission="demo-m01-list"]');
  await page.click('[data-testid="open-consult"]');
  await expect(page.locator('[data-testid="consult-about"]')).toHaveValue('demo-m01-list');
  await page.fill('[data-testid="consult-input"]', 'What is UMAP, mathematically?');
  await page.click('[data-testid="consult-ask"]');
  await expect(page.locator('[data-testid="consult-answer"]')).toContainText('What is UMAP, mathematically?');
  await expect(page.locator('[data-testid="consult-input"]')).toHaveValue('');

  // the conversation is saved with the game
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('[data-testid="consult-answer"]')).toHaveCount(1);

  // adding it to the lab notebook earns no research points
  const rp = await page.locator('[data-testid="rp"]').textContent();
  await page.click('[data-testid="consult-save"]');
  await expect(page.locator('.toast', { hasText: 'no RP' })).toBeVisible();
  await expect(page.locator('[data-testid="rp"]')).toHaveText(rp!);
  await page.click('[data-tab="notebook"]');
  await page.locator('.nb-item', { hasText: 'Consult: What is UMAP' }).click();
  await expect(page.locator('[data-testid="word-count"]')).toContainText('earns no RP');

  // clearing takes a second click
  await page.click('[data-tab="consult"]');
  await page.click('[data-testid="consult-clear"]');
  await expect(page.locator('[data-testid="consult-answer"]')).toHaveCount(1);
  await page.click('[data-testid="consult-clear"]');
  await expect(page.locator('[data-testid="consult-answer"]')).toHaveCount(0);
});

test('talk to the patient in a chat of their own', async ({ page }) => {
  await page.request.post('/api/game/abandon');
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.click('[data-testid="start-demo-one"]');
  await page.click('[data-testid="begin"]');

  // from the patient panel, with its own conversation next to the doctor's
  await page.click('[data-testid="open-bedside"]');
  await expect(page.locator('[data-tab="bedside"]')).toHaveText('Talk to Walter');
  await page.fill('[data-testid="bedside-input"]', 'How are you feeling?');
  await page.click('[data-testid="bedside-ask"]');
  const answer = page.locator('[data-testid="bedside-answer"]');
  await expect(answer).toContainText('How are you feeling?');
  await expect(answer).toContainText('Walter');
  await page.click('[data-tab="consult"]');
  await expect(page.locator('[data-testid="consult-answer"]')).toHaveCount(0);

  // the patient's model and effort can be changed in the game, without a restart
  await page.click('[data-tab="bedside"]');
  const header = page.locator('[data-testid="bedside-model-line"]');
  await expect(header).toContainText('(echo, low effort)');
  await page.click('[data-testid="bedside-settings"]');
  await page.fill('[data-testid="bedside-model"]', 'echo-2');
  await page.selectOption('[data-testid="bedside-effort"]', 'high');
  await page.click('[data-testid="bedside-settings-save"]');
  await expect(header).toContainText('(echo-2, high effort)');
  await page.click('[data-tab="consult"]');
  await expect(page.locator('[data-testid="consult-model-line"]')).toContainText('(echo, medium effort)');

  // kept with the game, and it can go into the notebook (no RP)
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.click('[data-tab="bedside"]');
  await expect(answer).toHaveCount(1);
  await expect(header).toContainText('(echo-2, high effort)');
  await page.click('[data-testid="bedside-save-all"]');
  await page.click('[data-tab="notebook"]');
  await page.locator('.nb-item', { hasText: 'Bedside chats with Walter' }).click();
  await expect(page.locator('[data-testid="word-count"]')).toContainText('Bedside chat · earns no RP');
});
