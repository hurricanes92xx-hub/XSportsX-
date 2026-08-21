import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const pkg = JSON.parse(fs.readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
const gateway = fs.readFileSync(new URL('../render-entry-v528.js', import.meta.url), 'utf8');

 test('uses the canonical Render gateway entrypoint', () => {
  assert.equal(pkg.scripts.start, 'node render-entry-v528.js');
  assert.ok(!pkg.scripts.start.includes('stable-boot'));
});

test('Render gateway uses the platform PORT and public bind address', () => {
  assert.match(gateway, /process\.env\.PORT/);
  assert.match(gateway, /0\.0\.0\.0/);
});
