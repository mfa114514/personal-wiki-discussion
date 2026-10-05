# 自然链接 · Natural Links for Obsidian

让链接融入正文：**每篇笔记独立选择**，链接使用周围文字的颜色与字体，仍然可以加粗、斜体、粗斜体、高亮、删除线，也仍然可以点击跳转。

没有开启的笔记继续使用主题原来的链接显示。适合希望正文阅读更自然，又想保留双向链接的人。

[下载安装包](https://github.com/mfa114514/obsidian-natural-links/releases/latest) · [更新记录](CHANGELOG.md) · [反馈问题](https://github.com/mfa114514/obsidian-natural-links/issues)

## 安装

当前通过 GitHub 发布，支持 BRAT 和手动安装。尚未提交到 Obsidian 社区插件目录，因此直接在社区插件搜索中不会出现。

### 方法一：使用 BRAT

[BRAT](https://github.com/TfTHacker/obsidian42-brat) 是从 GitHub 安装和更新 Obsidian 插件的工具。

1. 打开 Obsidian 的**设置 → 第三方插件**，关闭安全模式或受限模式（如有），浏览社区插件，搜索并安装 **BRAT**，然后启用它。
2. 打开 BRAT 的设置，点击 **Add Beta plugin**（添加插件）。也可以在命令面板搜索 BRAT 的添加插件命令。
3. 填入仓库地址：`https://github.com/mfa114514/obsidian-natural-links`。
4. 选择最新版本并添加，按界面提示启用插件；如果没有自动启用，在第三方插件列表中启用**自然链接**。

仓库是公开的，安装本插件无需 GitHub 账号或访问令牌。后续可通过 BRAT 检查更新。

### 方法二：手动安装

无需安装开发工具。

1. 打开 [Releases](https://github.com/mfa114514/obsidian-natural-links/releases/latest)，在 **Assets** 中下载 `natural-links-版本号.zip`。不要选择 GitHub 自动提供的 `Source code`，那是源码。
2. 解压后得到 `natural-links` 文件夹，里面有 `main.js`、`manifest.json`、`styles.css`。
3. 将整个文件夹复制到知识库目录的 `.obsidian/plugins/` 下，最终目录应如下所示。`.obsidian` 是隐藏文件夹，必要时在文件管理器里打开“显示隐藏项目”。

   ```text
   你的知识库/
   └── .obsidian/
       └── plugins/
           └── natural-links/
               ├── main.js
               ├── manifest.json
               └── styles.css
   ```

4. 回到**设置 → 第三方插件**，重新加载插件列表（或重新启动 Obsidian），启用**自然链接**。

手动更新时，停用插件，用新版的三个文件替换上述文件，再启用。各篇笔记的选择会保留。

## 每篇笔记如何开启

安装后，默认不会改变已有笔记。打开需要调整的笔记，任选一种方式：

- 点击桌面窗口右下角的**自然链接：关**，变为**自然链接：开**。
- 打开命令面板（Windows/Linux `Ctrl+P`，macOS `Cmd+P`），搜索“自然链接”，执行**切换当前笔记的自然链接**。
- 在文件列表中右键点击笔记，选择**开启本篇的自然链接**。

再次操作即可关闭。手机端没有桌面状态栏，可以使用命令面板或笔记文件菜单；手机端效果尚未实测。

选择由插件自动保存为笔记顶部的布尔属性，无需手写：

```yaml
---
natural-links: true
---
```

`true` 表示开启；`false` 或没有该属性表示关闭。同一篇笔记在多个标签页打开时使用同一选择。该属性随笔记同步到其他设备；其他设备也需要安装并启用本插件，才会应用显示调整。

## 加粗、斜体和其他格式

继续使用 Obsidian 原有的 Markdown 写法。下面以内部链接为例，外部链接也可以放在这些格式中：

| 显示方式 | 写法 |
| --- | --- |
| 普通链接 | `[[笔记名]]` |
| 显示别名 | `[[笔记名\|显示文字]]` |
| 加粗 | `**[[笔记名]]**` |
| 斜体 | `*[[笔记名]]*` |
| 粗斜体 | `***[[笔记名]]***` |
| 高亮 | `==[[笔记名]]==` |
| 删除线 | `~~[[笔记名]]~~` |

例如：`**重要概念：[[机器学习]]**`，链接会和旁边“重要概念”一样加粗。标题和引用里的链接也会跟随所在文字。

针对 Blue Topaz，插件还处理了粗斜体内部链接覆盖主题渐变的问题。插件只调整 Obsidian 已经解析好的链接样式，可用的格式和别名语法仍遵循 Obsidian 自身规则。

点击跳转沿用 Obsidian 当前模式的规则，例如阅读视图直接点击、编辑视图按需要使用 `Ctrl`/`Cmd` + 点击。

可以把 [examples](examples/) 中的两篇笔记一起复制到知识库，再开启、关闭示例笔记的开关，比较显示并测试跳转。

## 设置

打开**设置 → 第三方插件 → 自然链接**：

| 设置 | 默认 | 用途 |
| --- | --- | --- |
| 启用显示调整 | 开 | 临时暂停所有显示调整，保留每篇笔记已经保存的选择 |
| 调整内部链接 | 开 | 调整指向知识库笔记的链接 |
| 调整外部链接 | 开 | 调整网页链接 |
| 隐藏外部链接图标 | 开 | 隐藏选中笔记内网页链接旁的小箭头 |
| 链接下划线 | 悬停时显示 | 可改为始终隐藏或保持主题设置 |

这些设置只影响开启自然链接的笔记。它们保存在插件自己的设置中，不要求你逐篇维护额外属性。

## 兼容性、数据与恢复

- 最低 Obsidian 版本声明为 `1.5.0`。已实际验证的是 **Obsidian 1.13.7 + Blue Topaz**，包括实时预览和阅读视图；旧版、其他主题、手机端、独立悬浮预览及画布尚未实测。
- 已验证普通链接、加粗、斜体、粗斜体、高亮、删除线、标题、引用、未创建笔记的链接，以及按篇关闭和内部跳转。
- 样式作用于已开启笔记的正文视图；正文里的嵌入内容会跟随宿主笔记的显示选择。
- 插件运行时不联网、不收集数据、不上传笔记。切换开关只由 Obsidian 保存 `natural-links` 属性，插件设置保存在知识库的插件配置中。
- 关闭该篇笔记的开关、暂停显示调整或停用插件，都会恢复主题原来的显示。卸载后可以保留或自行删除 `natural-links` 属性，正文和链接目标仍可正常使用。

若遇到主题冲突，请在 [Issues](https://github.com/mfa114514/obsidian-natural-links/issues) 提供 Obsidian 版本、主题名称、出现问题的 Markdown 写法及所在视图。示例无需包含私人笔记内容。

## 开发与发布

需要 Node.js 22 或更新版本；自动检查使用 Node.js 24。

```sh
npm ci
npm run build
npm test
```

构建产物在 `dist/natural-links/`，包含安装所需的三个文件。

| 入口 | 用途 |
| --- | --- |
| `src/main.ts` | 按篇开关、视图生命周期、命令和设置 |
| `styles.css` | 阅读视图与编辑视图的链接显示规则 |
| `tests/plugin.test.cjs` | 使用模拟 Obsidian API 检查按篇隔离、属性保存、暂停、切换及清理 |
| `examples/` | 可复制到知识库的格式与跳转示例 |
| `manifest.json`、`versions.json` | 插件身份、版本及最低 Obsidian 版本 |
| `.github/workflows/` | 构建检查和版本发布 |

这些自动检查验证插件逻辑，不代替真实 Obsidian 的主题显示检查。修改样式后，应在实际应用中分别查看实时预览和阅读视图。

发布新版本时，同步修改 `manifest.json` 与 `package.json` 的版本，在 `versions.json` 添加对应最低版本，并补充 `CHANGELOG.md`。通过检查后，将提交和同名标签推送到 GitHub（例如 `0.1.1`，不加 `v` 前缀）。发布工作流会再次检查、编译并生成公开 Release，附上三个单独的运行文件、安装 ZIP 和 SHA-256 校验文件，供 BRAT 及手动安装使用。

欢迎通过 Issues 或 Pull Requests 反馈和改进。本项目采用 [MIT 许可证](LICENSE)。

## English quick start

Natural Links makes links follow the surrounding text while preserving bold, italic, combined emphasis, highlighting, strikethrough and navigation. **Enable it separately for each note**; existing notes keep their normal appearance by default. The current plugin UI is in Chinese.

Install with [BRAT](https://github.com/TfTHacker/obsidian42-brat) using `https://github.com/mfa114514/obsidian-natural-links`, or download the plugin ZIP from [Releases](https://github.com/mfa114514/obsidian-natural-links/releases/latest), extract the `natural-links` folder into your vault's `.obsidian/plugins/`, and enable it in Community plugins. No GitHub account is required to download the public release.

Click **自然链接：关** in the desktop status bar, use the **切换当前笔记的自然链接** command, or set the note's Boolean property `natural-links: true`. Use normal Markdown such as `***[[Note]]***` for bold italic links. The plugin runs locally and does not send notes or usage data anywhere. Tested on Obsidian 1.13.7 with Blue Topaz; mobile and other themes have not been tested. Licensed under MIT.
