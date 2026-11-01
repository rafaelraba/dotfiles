import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const dir = new URL('./', import.meta.url);
const keys = JSON.parse(fs.readFileSync(new URL('../../keys.json', dir), 'utf8'));
const source = fs.readFileSync(new URL('main.js', dir), 'utf8');
let calls = [];
const sandbox = {
  View: class {}, div: () => {}, v_flex: () => {}, theme: () => ({}),
  props: () => ({ overlay: 'test-overlay' }),
  focused: () => ({ terminal: 'remote/t1' }),
  spaces: () => [{ active: true, tabs: [{ id: 'a', index: 1 }, { id: 'b', index: 2, active: true }] }],
  agents: () => [{ address: 'remote/t2' }],
  run: (name, args = {}) => calls.push(['run', name, JSON.parse(JSON.stringify(args))]),
  closeOverlay: id => calls.push(['close', id]),
  hc: async args => calls.push(['hc', JSON.parse(JSON.stringify(args))]),
  nextCommand: () => new Promise(() => {}),
};
vm.createContext(sandbox);
vm.runInContext(source.replace(/^import .*;\n/gm, '').replace('export default class', 'globalThis.Prefix = class'), sandbox);
const prefix = new sandbox.Prefix();
const cx = { stop_propagation() {}, spawn(fn) { fn(this); }, focus_handle: () => ({ focus() {} }) };
prefix.init({}, cx);
const rules = [
  ['c', 'tab.new', {}], ['r', 'tab.rename', {}],
  ['shift-c', 'space.new', {}], ['shift-r', 'space.rename', {}],
  ['shift-k', 'space.close', {}], ['shift-x', 'tab.close', {}],
  ['-', 'pane.split', { direction: 'down' }], ['v', 'pane.split', { direction: 'right' }],
  ['x', 'pane.close', {}], ['z', 'pane.zoom', {}],
  ['h', 'pane.go', { direction: 'left' }], ['j', 'pane.go', { direction: 'down' }],
  ['k', 'pane.go', { direction: 'up' }], ['l', 'pane.go', { direction: 'right' }],
  ['p', 'tab.prev', {}], ['n', 'tab.next', {}],
  ['shift-p', 'space.prev', {}], ['shift-n', 'space.next', {}],
];
for (let n = 1; n <= 9; n++) rules.push([String(n), 'tab.select', { index: n }]);
for (const [chord, command, args] of rules) {
  calls = [];
  prefix.key({ keystroke: chord, key: chord, modifiers: {} }, cx);
  assert.deepEqual(calls, [['close', 'test-overlay'], ['run', command, args]], chord);
}
calls = [];
prefix.command('literal', cx);
assert.deepEqual(calls, [['close', 'test-overlay'], ['hc', ['keys', 'remote/t1', 'ctrl+a']]]);
calls = [];
prefix.command('agent-1', cx);
assert.deepEqual(calls, [['close', 'test-overlay'], ['run', 'agent.focus', { terminal: 'remote/t2' }]]);
for (const chord of ['escape', 'd', '[', 'ctrl-left', ';', 'shift-o', 'unknown']) {
  calls = [];
  prefix.key({ keystroke: chord, key: chord, modifiers: {} }, cx);
  assert.deepEqual(calls, [['close', 'test-overlay']], chord);
}
assert.equal(keys.global['ctrl-a'], 'mod.open:tui-prefix');
assert.equal(keys.terminal['ctrl-a'], 'mod.open:tui-prefix');
assert.equal(keys['mod:tui-prefix']['ctrl-a'], 'tui-prefix.literal');
for (let n = 1; n <= 9; n++) {
  assert.equal(keys.global[`alt-${n}`], `tab.select:${n}`);
  assert.equal(keys['mod:tui-prefix'][`alt-${n}`], `tui-prefix.agent-${n}`);
}
for (const [key, action] of Object.entries({
  'alt-left': 'tab.prev', 'alt-right': 'tab.next', 'alt-up': 'space.prev', 'alt-down': 'space.next',
  'ctrl-alt-left': 'agent.prev', 'ctrl-alt-right': 'agent.next',
  'alt-enter': 'pane.split:down', 'alt-shift-enter': 'pane.split:right', 'alt-escape': 'pane.close',
  'ctrl-shift-t': 'tab.new', 'ctrl-shift-p': 'app.palette',
})) assert.equal(keys.global[key], action, key);
for (const [key, action] of Object.entries({
  'ctrl-shift-c': 'terminal.copy', 'ctrl-shift-v': 'terminal.paste',
  'ctrl-v': 'terminal.paste_image', 'ctrl-left': 'send:\u001bb', 'ctrl-right': 'send:\u001bf',
})) assert.equal(keys.terminal[key], action, key);
const manifest = JSON.parse(fs.readFileSync(new URL('mod.json', dir), 'utf8'));
assert.equal(manifest.overlay.kind, 'popup');
assert.equal(manifest.overlay.frame, 'none');
assert.equal(manifest.overlay.width, 1);
assert.equal(manifest.overlay.height, 1);
const rendered = [];
const element = new Proxy({}, { get: (_, name) => (...args) => {
  rendered.push([name, ...args]);
  return element;
} });
sandbox.div = () => element;
prefix.render();
assert.ok(rendered.some(([name]) => name === 'track_focus'), 'silent prefix must keep keyboard focus');
assert.ok(rendered.some(([name]) => name === 'on_key_down'), 'silent prefix must keep its key handler');
assert.ok(!rendered.some(([name]) => ['child', 'children', 'bg', 'border', 'shadow'].includes(name)), 'no hint text or painted panel');
console.log(`PASS: ${rules.length} prefix rules, literal prefix, agents, exceptions, existing shortcuts and invisible prefix rendering`);
