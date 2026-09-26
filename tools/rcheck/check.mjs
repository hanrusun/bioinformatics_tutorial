// Parse every R snippet of a pack and run the helper unit tests, in webR.
//   python3 tools/export_r_snippets.py > snippets.json && node check.mjs snippets.json
import { WebR } from 'webr';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..', '..');
const snippets = JSON.parse(readFileSync(process.argv[2] ?? 'snippets.json', 'utf8'));

const webR = new WebR({ interactive: false });
await webR.init();
let failures = 0;

// 1. every snippet parses
for (const s of snippets) {
  await webR.objs.globalEnv.bind('code_', s.code);
  const res = await webR.evalRString(
    'tryCatch({ invisible(parse(text = code_)); "ok" }, error = function(e) conditionMessage(e))'
  );
  if (res !== 'ok') {
    failures++;
    console.log(`PARSE ERROR in ${s.where}: ${res}`);
  }
}
console.log(`parsed ${snippets.length} R snippets`);

// 2. helper unit tests, then 3. the reference builder end to end on a mock pack
await webR.FS.writeFile('/helpers.R', readFileSync(path.join(root, 'packs/seurat/r/helpers.R')));
await webR.FS.writeFile('/helpers_test.R', readFileSync(path.join(here, 'helpers_test.R')));
await webR.FS.mkdir('/src');
await webR.FS.writeFile('/src/helpers.R', readFileSync(path.join(root, 'packs/seurat/r/helpers.R')));
await webR.FS.writeFile('/src/build_reference.R', readFileSync(path.join(root, 'packs/seurat/reference/build_reference.R')));
await webR.FS.writeFile('/builder_test.R', readFileSync(path.join(here, 'builder_test.R')));
const shelter = await new webR.Shelter();
for (const [name, script] of [
  ['helper', '/helpers_test.R'],
  ['builder', '/builder_test.R'],
]) {
  const res = await shelter.captureR(`source("${script}")`);
  const lines = res.output.map((o) => o.data).join('\n');
  if (!/^PASS /m.test(lines)) {
    failures++;
    console.log(`${name} tests did not run`);
  }
  for (const line of lines.split('\n')) {
    if (!line.trim()) continue;
    console.log(line);
    if (line.startsWith('FAIL') || line.startsWith('Error')) failures++;
  }
}
await webR.close();
console.log(failures ? `${failures} problem(s)` : 'R checks passed');
process.exit(failures ? 1 : 0);
