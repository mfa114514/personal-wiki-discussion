import { App, MarkdownView, Notice, Plugin, PluginSettingTab, Setting, TFile } from 'obsidian';

const NOTE_PROPERTY = 'natural-links';
const STYLE_CLASSES = ['nlf-note', 'nlf-internal', 'nlf-external', 'nlf-hide', 'nlf-hover', 'nlf-hide-icon', 'nlf-gradient-strong-em'];

interface NaturalLinksSettings {
  enabled: boolean;
  internalLinks: boolean;
  externalLinks: boolean;
  underline: 'hide' | 'hover' | 'theme';
  hideExternalIcon: boolean;
}

const DEFAULT_SETTINGS: NaturalLinksSettings = {
  enabled: true,
  internalLinks: true,
  externalLinks: true,
  underline: 'hover',
  hideExternalIcon: true
};

export default class NaturalLinksPlugin extends Plugin {
  settings: NaturalLinksSettings = { ...DEFAULT_SETTINGS };
  private styledContainers = new Set<HTMLElement>();
  private statusEl?: HTMLElement;

  async onload(): Promise<void> {
    const saved = await this.loadData();
    for (const key of ['enabled', 'internalLinks', 'externalLinks', 'hideExternalIcon'] as const) {
      if (typeof saved?.[key] === 'boolean') this.settings[key] = saved[key];
    }
    if (['hide', 'hover', 'theme'].includes(saved?.underline)) this.settings.underline = saved.underline;

    this.addSettingTab(new NaturalLinksSettingTab(this.app, this));
    this.addCommand({
      id: 'toggle-current-note',
      name: '切换当前笔记的自然链接',
      checkCallback: (checking) => {
        const file = this.app.workspace.getActiveViewOfType(MarkdownView)?.file;
        if (!file) return false;
        if (!checking) void this.toggleNote(file);
        return true;
      }
    });

    this.registerEvent(this.app.workspace.on('file-menu', (menu, file) => {
      if (!(file instanceof TFile) || file.extension !== 'md') return;
      const selected = this.noteSelected(file);
      menu.addItem(item => item
        .setTitle(selected ? '关闭本篇的自然链接' : '开启本篇的自然链接')
        .setIcon('link')
        .onClick(() => { void this.toggleNote(file); }));
    }));

    this.statusEl = this.addStatusBarItem();
    this.statusEl.setAttribute('aria-label', '切换当前笔记的自然链接');
    this.statusEl.setAttribute('role', 'button');
    this.statusEl.tabIndex = 0;
    const toggleCurrent = () => {
      const file = this.app.workspace.getActiveViewOfType(MarkdownView)?.file;
      if (file) void this.toggleNote(file);
    };
    this.registerDomEvent(this.statusEl, 'click', toggleCurrent);
    this.registerDomEvent(this.statusEl, 'keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggleCurrent();
      }
    });

    const refresh = () => this.updateViews();
    this.registerEvent(this.app.workspace.on('file-open', refresh));
    this.registerEvent(this.app.workspace.on('layout-change', refresh));
    this.registerEvent(this.app.workspace.on('active-leaf-change', refresh));
    this.registerEvent(this.app.workspace.on('css-change', refresh));
    this.registerEvent(this.app.metadataCache.on('changed', () => this.updateViews()));
    this.registerEvent(this.app.metadataCache.on('resolved', () => this.updateViews()));
    this.app.workspace.onLayoutReady(() => this.updateViews());
  }

  noteSelected(file: TFile | null): boolean {
    return !!file && this.app.metadataCache.getFileCache(file)?.frontmatter?.[NOTE_PROPERTY] === true;
  }

  async toggleNote(file: TFile): Promise<void> {
    try {
      let selected = false;
      await this.app.fileManager.processFrontMatter(file, frontmatter => {
        selected = frontmatter[NOTE_PROPERTY] !== true;
        frontmatter[NOTE_PROPERTY] = selected;
      });
      this.updateViews(file, selected);
      new Notice(`${file.basename}：自然链接已${selected ? '开启' : '关闭'}${this.settings.enabled ? '' : '（插件总开关目前关闭）'}`);
    } catch (error) {
      console.error('[自然链接] 无法保存笔记开关', error);
      new Notice('自然链接：无法保存这篇笔记的选择，请检查笔记是否可写。');
    }
  }

  updateViews(changedFile?: TFile, selected?: boolean): void {
    const currentContainers = new Set<HTMLElement>();
    for (const leaf of this.app.workspace.getLeavesOfType('markdown')) {
      const view = leaf.view;
      if (!(view instanceof MarkdownView)) continue;
      const container = view.contentEl;
      currentContainers.add(container);
      const noteEnabled = view.file?.path === changedFile?.path && selected !== undefined
        ? selected : this.noteSelected(view.file);
      const active = this.settings.enabled && noteEnabled;
      container.classList.toggle('nlf-note', active);
      container.classList.toggle('nlf-internal', active && this.settings.internalLinks);
      container.classList.toggle('nlf-external', active && this.settings.externalLinks);
      container.classList.toggle('nlf-hide', active && this.settings.underline === 'hide');
      container.classList.toggle('nlf-hover', active && this.settings.underline === 'hover');
      container.classList.toggle('nlf-hide-icon', active && this.settings.hideExternalIcon);
      // Blue Topaz paints strong+em with a gradient, but explicitly resets the
      // fill on internal links. Detect its variables so other themes stay safe.
      const themeStyle = active ? container.ownerDocument?.defaultView?.getComputedStyle(container) : undefined;
      const hasGradient = !!themeStyle?.getPropertyValue('--strong-em-color-1').trim()
        && !!themeStyle?.getPropertyValue('--strong-em-color-2').trim();
      container.classList.toggle('nlf-gradient-strong-em', active && hasGradient);
      if (active) this.styledContainers.add(container);
      else this.styledContainers.delete(container);
    }
    for (const container of this.styledContainers) {
      if (!currentContainers.has(container)) {
        container.classList.remove(...STYLE_CLASSES);
        this.styledContainers.delete(container);
      }
    }
    const currentFile = this.app.workspace.getActiveViewOfType(MarkdownView)?.file;
    if (this.statusEl) {
      this.statusEl.style.display = currentFile ? '' : 'none';
      const chosen = currentFile?.path === changedFile?.path && selected !== undefined
        ? selected : this.noteSelected(currentFile ?? null);
      this.statusEl.setText(`自然链接：${this.settings.enabled ? (chosen ? '开' : '关') : '已暂停'}`);
      this.statusEl.setAttribute('title', '点击切换当前笔记；每篇笔记单独记住选择');
      this.statusEl.setAttribute('aria-pressed', String(chosen));
    }
  }

  async saveSettings(): Promise<void> {
    this.updateViews();
    await this.saveData(this.settings);
  }

  onunload(): void {
    for (const container of this.styledContainers) container.classList.remove(...STYLE_CLASSES);
    this.styledContainers.clear();
  }
}

class NaturalLinksSettingTab extends PluginSettingTab {
  constructor(app: App, private plugin: NaturalLinksPlugin) { super(app, plugin); }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.createEl('p', { text: '每篇笔记单独选择。打开笔记后，点击底部“自然链接”，或按 Ctrl+P 搜索“自然链接”。文件列表右键菜单也有开关。默认保留已有笔记的显示。' });

    const toggles: [keyof Pick<NaturalLinksSettings, 'enabled' | 'internalLinks' | 'externalLinks' | 'hideExternalIcon'>, string, string][] = [
      ['enabled', '启用显示调整', '总开关。关闭后全部恢复主题显示，各篇笔记的选择仍会保留。'],
      ['internalLinks', '调整内部链接', '让指向知识库内笔记的链接跟随周围文字。'],
      ['externalLinks', '调整外部链接', '让网页链接跟随周围文字。'],
      ['hideExternalIcon', '隐藏外部链接图标', '在已选择的笔记中，隐藏外部链接旁的小箭头。']
    ];
    for (const [key, name, description] of toggles) {
      new Setting(containerEl).setName(name).setDesc(description).addToggle(toggle => toggle
        .setValue(this.plugin.settings[key])
        .onChange(async value => { this.plugin.settings[key] = value; await this.plugin.saveSettings(); }));
    }
    new Setting(containerEl).setName('链接下划线').setDesc('悬停显示可以让正文保持简洁，同时方便识别链接；不影响删除线。')
      .addDropdown(dropdown => dropdown
        .addOptions({ hide: '始终隐藏', hover: '悬停时显示', theme: '保持主题设置' })
        .setValue(this.plugin.settings.underline)
        .onChange(async value => {
          this.plugin.settings.underline = value as NaturalLinksSettings['underline'];
          await this.plugin.saveSettings();
        }));
    containerEl.createEl('p', { text: '开关自动保存在笔记的 natural-links 属性中。加粗、斜体、高亮、删除线和链接跳转继续使用 Obsidian 原有操作。' });
  }
}
