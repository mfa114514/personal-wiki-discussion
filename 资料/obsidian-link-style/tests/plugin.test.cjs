const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor() {
    this.classes = new Set(); this.style = {}; this.attrs = {}; this.text = '';
    this.classList = {
      toggle: (name, selected) => selected ? this.classes.add(name) : this.classes.delete(name),
      remove: (...names) => names.forEach(name => this.classes.delete(name))
    };
  }
  setText(text) { this.text = text; }
  setAttribute(key, value) { this.attrs[key] = value; }
}
class TFile {
  constructor(name) { this.path = `${name}.md`; this.basename = name; this.extension = 'md'; }
}
class MarkdownView {
  constructor(file) { this.file = file; this.contentEl = new Element(); }
}
class Plugin {
  constructor(app, saved) { this.app = app; this.saved = saved; this.commands = []; this.eventRefs = []; }
  async loadData() { return this.saved; }
  async saveData(data) { this.saved = structuredClone(data); }
  addSettingTab() {}
  addCommand(command) { this.commands.push(command); }
  addStatusBarItem() { return new Element(); }
  registerDomEvent() {}
  registerEvent(ref) { this.eventRefs.push(ref); }
}
class PluginSettingTab {}
const notices = [];
const source = fs.readFileSync(path.join(__dirname, '../dist/natural-links/main.js'), 'utf8');
const moduleObject = { exports: {} };
vm.runInNewContext(source, {
  module: moduleObject, exports: moduleObject.exports,
  require: name => {
    assert.equal(name, 'obsidian');
    return { TFile, MarkdownView, Plugin, PluginSettingTab, Setting: class {}, Notice: class { constructor(text) { notices.push(text); } } };
  }, console
}, { filename: 'natural-links/main.js' });
const NaturalLinks = moduleObject.exports.default;

function emitter() {
  const events = new Map();
  return {
    on: (name, fn) => { if (!events.has(name)) events.set(name, []); events.get(name).push(fn); return { name, fn }; },
    emit: (name, ...args) => (events.get(name) ?? []).forEach(fn => fn(...args))
  };
}
async function setup(saved) {
  const a = new TFile('已选择'), b = new TFile('未选择');
  const frontmatter = new Map([[a.path, { 'natural-links': true, tags: ['原有标签'] }], [b.path, { title: '原有标题' }]]);
  const views = [new MarkdownView(a), new MarkdownView(a), new MarkdownView(b)];
  const workspace = Object.assign(emitter(), {
    getLeavesOfType: () => views.map(view => ({ view })),
    getActiveViewOfType: () => views[0],
    onLayoutReady: fn => fn()
  });
  const metadataCache = Object.assign(emitter(), { getFileCache: file => ({ frontmatter: frontmatter.get(file.path) }) });
  const app = { workspace, metadataCache, fileManager: {
    processFrontMatter: async (file, callback) => {
      const current = frontmatter.get(file.path); callback(current); metadataCache.emit('changed', file);
    }
  } };
  const plugin = new NaturalLinks(app, saved); await plugin.onload();
  return { a, b, views, plugin, frontmatter, workspace, metadataCache, app };
}

test('only opted-in notes are styled, including multiple tabs of the same file', async () => {
  const { views } = await setup();
  assert(views[0].contentEl.classes.has('nlf-note'));
  assert(views[1].contentEl.classes.has('nlf-note'));
  assert.equal(views[2].contentEl.classes.size, 0);
});

test('toggle persists each note choice and preserves unrelated properties', async () => {
  const { plugin, a, b, views, frontmatter } = await setup();
  await plugin.toggleNote(a);
  assert.equal(frontmatter.get(a.path)['natural-links'], false);
  assert.deepEqual(frontmatter.get(a.path).tags, ['原有标签']);
  assert.equal(views[0].contentEl.classes.size, 0);
  assert.equal(views[1].contentEl.classes.size, 0);
  await plugin.toggleNote(b);
  assert.equal(frontmatter.get(b.path).title, '原有标题');
  assert(views[2].contentEl.classes.has('nlf-note'));
  assert.equal(views[0].contentEl.classes.size, 0);
});

test('global pause restores views without erasing saved per-note decisions', async () => {
  const { plugin, a, views, frontmatter } = await setup();
  plugin.settings.enabled = false; await plugin.saveSettings();
  assert(views.every(v => v.contentEl.classes.size === 0));
  assert.equal(frontmatter.get(a.path)['natural-links'], true);
  plugin.settings.enabled = true; await plugin.saveSettings();
  assert(views[0].contentEl.classes.has('nlf-note'));
  assert.equal(views[2].contentEl.classes.size, 0);
});

test('cache changes and reused tabs follow the currently displayed note', async () => {
  const { views, a, b, frontmatter, metadataCache, workspace } = await setup();
  frontmatter.get(a.path)['natural-links'] = false; metadataCache.emit('changed', a);
  assert.equal(views[0].contentEl.classes.size, 0);
  frontmatter.get(a.path)['natural-links'] = true; metadataCache.emit('changed', a);
  views[0].file = b; workspace.emit('file-open', b);
  assert.equal(views[0].contentEl.classes.size, 0);
  assert(views[1].contentEl.classes.has('nlf-note'));
});

test('closing views and unloading remove all owned style classes', async () => {
  const { plugin, views, workspace } = await setup();
  const closed = views.pop();
  views[0].contentEl.classes.add('unrelated-theme-class');
  const styledClosed = views.splice(1, 1)[0]; workspace.emit('layout-change');
  assert.equal(styledClosed.contentEl.classes.size, 0);
  plugin.onunload();
  assert.deepEqual([...views[0].contentEl.classes], ['unrelated-theme-class']);
  assert.equal(closed.contentEl.classes.size, 0);
});

test('invalid stored settings and text-valued properties do not unexpectedly enable styling', async () => {
  const { plugin, frontmatter, a, views, metadataCache } = await setup({ enabled: 'false', internalLinks: null, underline: 'broken' });
  assert.equal(plugin.settings.enabled, true);
  assert.equal(plugin.settings.internalLinks, true);
  assert.equal(plugin.settings.underline, 'hover');
  frontmatter.get(a.path)['natural-links'] = 'true'; metadataCache.emit('changed', a);
  assert.equal(views[0].contentEl.classes.size, 0);
});
