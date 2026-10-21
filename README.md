# 更多迭代器 / MoreIterators

MoreIterators 是为《雨世界》制作的免费开源 OC 创作工具。通过本地网页调整迭代器的外观、编写剧情、制作珍珠与广播、编辑投影动画，再到游戏中检查效果。完成的作品可以导出为独立游玩模组。

当前版本：**0.1.3**。模组面向 Rain World **v1.11.8**；目前仍在开发与测试中。

[Steam 创意工坊](https://steamcommunity.com/sharedfiles/filedetails/?id=3823802510) · [必要依赖：Warp Menu](https://steamcommunity.com/sharedfiles/filedetails/?id=2920446893) · [Rained 房间编辑器](https://github.com/pkhead/rained/releases) · [Discord](https://discord.gg/JBNxgz7E4h)

## 主要功能

- **外观与贴图**：调整人偶、眼睛、天线、手臂、袖子、长袍与演算环；支持非对称部件、分层绘画和撤销重做。
- **剧情对话**：编排初见、后续多次见面与循环对话，设置珍珠和物品相关回应，并为台词绑定眼睛、动作与投影表现。
- **珍珠文本**：制作珍珠外观、指定读取者、编写正文与好感差分，配置重复读取回应和生成位置。
- **广播编辑**：按页编写广播，统一调整播放样式；根据说话角色绑定颜色，支持导入 RainocTool 导出的广播 JSON。
- **投影动画**：导入透明 PNG，设置轨道与关键帧，选择匀速、平滑或阶梯过渡；替换图片时保留轨道与关键帧。
- **房间与导出**：管理演算室、等待房间及连接，配合 Rained 制作自定义房间，将选定的作品内容导出为独立游玩模组。
- **本地预览与管理**：提供网页预览、游戏内测试入口、保存历史及关联内容迁移。迭代器语音属于实验性功能。

## 0.1.3 更新

- 演算珍珠的堆积位置按室内可活动区域定位，修复贴墙堆积和恢复零重力后不归位的问题。
- 撤销和重做绘画时保留当前部件、画布视角和面板滚动位置，包括切换部件后的第一笔。
- 选择绘画部件后，自动展开并定位左侧对应参数。
- 投影图片可直接替换并撤销替换，保留已有轨道和关键帧；整理素材操作与轨道参数布局。
- 支持从画布外起笔，笔划在图像边缘自然裁切；完全未碰到图像的操作不留下编辑记录。

## 下载与反馈

目前工坊仍为好友可见测试；无法打开工坊条目时，请先联系作者。

游玩和创作请使用 [Steam 创意工坊版本](https://steamcommunity.com/sharedfiles/filedetails/?id=3823802510)，并启用必要依赖 [Warp Menu](https://steamcommunity.com/sharedfiles/filedetails/?id=2920446893)。制作自定义房间可使用 [Rained 官方版本](https://github.com/pkhead/rained/releases)。

欢迎在 [Discord](https://discord.gg/JBNxgz7E4h) 讨论和反馈。反馈问题时请附上模组版本、复现步骤，以及相关报错或截图；分享前请确认日志和作品文件中没有不想公开的内容。

## 感谢

感谢测试与协助：粉笔、LL77、DESANTA、steelmachine、timerteo、匿名测试者。

## 许可

本项目代码采用 [MIT License](LICENSE)。第三方素材保留其原有权利：Fusion Pixel 字体遵循 [SIL OFL 1.1](editor/fonts/Fusion-Pixel-OFL.txt)，[来源说明](editor/fonts/SOURCE.txt)随包保留；原版参考预览中的 Rain World 素材不由本项目的 MIT 许可证重新授权。游戏与依赖程序集不包含在本仓库中，构建时从你自己的游戏安装读取。

Copyright (c) 2026 Rey544

## 首次配置教程（Windows）

适用于 Windows 10/11 的普通 64 位电脑与 Steam 工坊版。外观、对话、珍珠和投影编辑需要 Python；只有要修改房间地形时才需要 Rained。
工坊：https://steamcommunity.com/sharedfiles/filedetails/?id=3823802510
依赖 Warp Menu：https://steamcommunity.com/sharedfiles/filedetails/?id=2920446893
在游戏 Remix / 拓展菜单启用这两个模组并应用。

#### 1. 安装 Python

打开 https://www.python.org/downloads/windows/ ，下载并安装官方 Python install manager。然后重新打开 PowerShell，执行：

```powershell
py install 3.13
```

如果旧版 py 启动器把 install 当成文件名，而你确实已安装 manager，改用：

```powershell
pymanager install 3.13
```

已经有 Python 3.13 的人可以跳过安装。已有可用的 Python 3.10+ 也可继续用；下面的命令统一用 3.13，如果沿用其他版本，把所有 -3.13 一起改成自己的版本。
另一种安装方式是从提供安装器的 3.13 发布页面选择 Windows installer (64-bit)，运行普通 .exe 时勾选 Add python.exe to PATH，并保留 pip 和 Launcher。不要选 embeddable package；不是每个 3.13.x 发布页都提供传统安装器。

安装结束后重新打开终端，运行：

```powershell
py -3.13 --version
```

应显示 Python 3.13.x。

#### 2. 找到 MI 工坊文件夹，安装图片依赖

在 Steam 库右键 Rain World → 管理 → 浏览本地文件，记下包含 RainWorld.exe 的文件夹地址，后面要用。
MI 通常在同一 Steam 库的 steamapps\workshop\content\312520\3823802510。找到含 modinfo.json、editor 文件夹和“创建桌面快捷方式.cmd”的这一层；不要进入 editor 后再执行下面的相对路径命令。

在这个文件夹的地址栏输入 powershell 并回车。在弹出的 PS ...> 窗口依次执行：

```powershell
py -3.13 -m pip install -r .\editor\requirements.txt
py -3.13 -c "import sys, PIL; print(sys.executable); print('Pillow', PIL.__version__)"
```

第二行显示 Python 路径和 Pillow 版本且没有报错，即依赖已就绪。请按包内 requirements 安装，不要另行安装无版本上限的最新版 Pillow。

所有代码都粘贴到 PowerShell，不是网页，不是 Python 的 >>>，也不是运行中程序的 server>。本文不直接运行 server.py；启动器会在后台启动服务，不会占用后续代码的输入。

#### 3. 配置雨世界路径

先保存网页和 Rained 中的工作。如果 MI 后台已经开着，配置完成后还要按第 6 节重新启动它。
在同一个 PowerShell 中完整粘贴下面这一块，按回车执行。包括第一行 function 和最后一个 }；这一步只定义配置工具，不改文件。

```powershell
function Set-MIPath {
    param([string]$Name, [string]$Value)
    @'
import json, os, sys, uuid
from pathlib import Path
k, v = sys.argv[1], sys.argv[2].strip().strip('"')
q = Path(v)
assert q.is_absolute(), 'Use a full absolute path.'
if k == 'gameRoot':
    assert (q/'RainWorld.exe').is_file(), 'RainWorld.exe not found.'
elif k == 'rainedExecutable':
    assert q.name.lower() == 'rained.exe' and q.is_file(), 'Rained.exe not found.'
    assert (q.parent/'Data').is_dir(), 'Rained Data folder missing.'
else:
    raise ValueError('Unknown setting.')
d = Path(os.environ.get('MORE_ITERATORS_DATA') or Path.home()/'AppData/LocalLow/Videocult/Rain World/MoreIterators/data')
assert d.is_absolute(), 'Invalid data path.'
p = d/'config.json'
before = p.read_bytes() if p.exists() else None
def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('Duplicate JSON key: '+key)
        result[key] = value
    return result
s = json.loads(before.decode('utf-8-sig'), object_pairs_hook=unique) if before is not None else {}
assert isinstance(s, dict), 'Config must be an object.'
v = str(q)
if s.get(k) == v and before and not before.startswith(b'\xef\xbb\xbf'):
    print('Already configured:', p)
    sys.exit(0)
s[k] = v
data = (json.dumps(s, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8')
d.mkdir(parents=True, exist_ok=True)
t = d/('.config-'+uuid.uuid4().hex+'.tmp')
try:
    t.write_bytes(data)
    if (p.read_bytes() if p.exists() else None) != before: raise RuntimeError('Config changed; retry.')
    if before is not None:
        backup = d/('config.before-setup-'+uuid.uuid4().hex+'.bak')
        backup.write_bytes(before)
        print('Backup:', backup)
    os.replace(t, p)
    print('OK:', k, '=', v, '\nConfig:', p)
finally:
    t.unlink(missing_ok=True)
'@ | py -3.13 - $Name $Value
    if ($LASTEXITCODE -ne 0) { throw 'Setup failed. Keep this error.' }
}
```

然后完整粘贴下面这一块，按回车，再按提示粘贴包含 RainWorld.exe 的文件夹完整路径。不是 RainWorld.exe 文件本身；带空格或中文的路径也可以。

```powershell
& {
    $miGame = Read-Host 'Full Rain World folder path (contains RainWorld.exe)'
    Set-MIPath gameRoot $miGame
}
```

成功显示 OK 和 Config 路径；已有配置会保留其他字段，并生成 config.before-setup-*.bak。Already configured 表示无需重复修改。报错就先停在这一步，不要删掉 config.json 或项目重来。
工坊版的项目和配置通常位于：
%USERPROFILE%\AppData\LocalLow\Videocult\Rain World\MoreIterators\data
如果你主动设置了 MORE_ITERATORS_DATA，代码会使用该目录。普通新用户无需设置它。

#### 4. 创建桌面快捷方式并打开网页

回到 3823802510 文件夹，双击“创建桌面快捷方式.cmd”。桌面会出现“MI 外观编辑器”；双击它打开网页。
网页默认地址是 http://127.0.0.1:18747 ，但已有配置可能使用别的端口，以实际打开的地址为准。

若提示找不到 Python/Pillow，但第 2 节验证已经成功，在同一文件夹打开 PowerShell，执行下面这一块：

```powershell
& {
    $miPython = py -3.13 -c "import sys, PIL; print(sys.executable)"
    if ($LASTEXITCODE -ne 0) { throw 'Check Python and Pillow first.' }
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\editor\launch_studio.ps1 -PythonExe $miPython -CreateShortcut
}
```

它会使用刚验证过的 Python 生成快捷方式，适合安装了多个 Python 或使用 install manager 的情况。以后更新 Python 安装位置或移动模组目录时，再生成一次快捷方式。

#### 5. 首次应用自己的作品

在网页新建项目 → 保存 → 应用到游戏。保存只保存网页项目；应用才会生成游戏需要的本地内容。
首次应用会生成“更多迭代器 · 本地作品”（moreiterators.local）。回游戏 Remix / 拓展菜单启用它并应用；若当前菜单还看不到，重启游戏后再启用。MI 核心与自己的本地作品是两个模组。启用后按游戏提示重启；新增房间后也要重启游戏，再进入检查。

#### 6. 配置改完后，重新启动正确的 MI 后台

仅关闭浏览器不会停止后台。最简单的方法是保存工作后重启 Windows，再打开快捷方式。
也可以在当前网页地址上打开 /api/health（保留原端口），确认 service 为 more-iterators-studio、editorDirectory 是正在使用的 MI，记下 pid。在任务管理器“详细信息”里，只结束这个 PID 对应的 Python 进程，再双击快捷方式。不要结束所有 Python 进程。
如果提示“另一个编辑器目录正在使用端口”，也按这个方法检查；不要通过删除项目解决。

#### 7. 可选：安装和连接 Rained

下载完整 Windows 发布压缩包：https://github.com/pkhead/rained/releases
不要选 Source code，也不要只取一个 exe。完整解压到固定位置，例如 D:\Tools\Rained，先确认 Rained.exe 能自行打开，并完成首次素材安装。

MI 当前会使用 Rained.exe 同级的 Data 目录。请把完整素材放在那里，并让 Rained 自身使用同一个目录：File → Preferences → Data Path；也可在 Tools → Asset Manager 管理素材。例如：
D:\Tools\Rained\Rained.exe
D:\Tools\Rained\Data\Graphics
D:\Tools\Rained\Data\Props
D:\Tools\Rained\Data\Levels
演算室原版源工程还需要对应的 Data\LevelEditorProjects 内容。Data 不是雨世界的 RainWorld_Data，也不能只是空文件夹。

回到刚才的 PowerShell；如果是新开的窗口，先重新执行第 3 节以 function Set-MIPath 开头的完整代码块。然后执行：

```powershell
& {
    $miRained = Read-Host 'Full path to Rained.exe'
    Set-MIPath rainedExecutable $miRained
}
```

按提示粘贴真正 Rained.exe 的完整文件路径（可用右键“复制为路径”）。不要填文件夹、.lnk 快捷方式或 Rained.Console.exe。之后按第 6 节重启 MI 后台。

#### 8. 打开房间、编辑、同步

在 MI 外观调整页面选择项目，展开左侧“房间工程”。
等待室：打开等待房间 → 在 Rained 修改并 Ctrl+S 保存原工程 → 回 MI 点同步等待房间。
演算室：打开演算室 → 修改并保存 → 同步演算室。

同步按钮会自动渲染已保存的源工程并应用到游戏；等待成功提示后，再到游戏重新进入该房间检查。正常流程不用再手动渲染。不要先把工程另存为其他文件名或目录，否则 MI 仍会同步原工程。
“区域连接”编辑的是房间连接；它不替代这里的地形同步。外部已有房间也不能通过当前项目覆盖地形。

#### 常见问题

- py 不存在：重新开 PowerShell；仍不行就修复官方 Python install manager 的安装。若用传统安装器，则检查 Launcher 是否启用。不要在终端里反复输入 python 后进入 >>>。
- No module named PIL：对启动 MI 的同一个 Python 重跑第 2 节的 requirements 命令，再用第 4 节的代码重新创建快捷方式。
- 缺 modinfo.json / requirements.txt / studio.ico：目录选错或包不完整；回到含 editor 的模组根目录。不要只复制启动脚本。
- 网页依旧提示 Rained 不存在：确认重启的是后台，并比较 /api/health 的 dataDirectory 与代码打印的 Config 目录。
- Rained 能开但同步失败：核对同级 Data 的完整素材。在 Rained 的 File → Render（Ctrl+R）手动试渲染查看具体错误，修好后回 MI 同步。自动渲染超过 180 秒会报超时，不算同步成功。
- 缺 Rained 源工程：房间游戏导出的 .txt 不能代替可编辑源工程；新等待室有配套源，演算室需要对应 SS_AI 可编辑源素材。保留完整报错，不要把另一种文件重命名顶替。
- 启动失败：弹窗会给日志路径。通常可在 data\archive\logs 查看 studio-launch-error.log、server-startup.log。不要删除 data 来修复启动。

GitHub 源码使用者注意：本教程主要面向工坊发行包。公开源码副本保留 release-layout.json 时，与工坊版一样使用上述用户数据目录；只有不带该文件的原开发目录才默认用仓库下 data。配置代码默认写用户数据目录。不要同时启动两份编辑器或混用快捷方式，也不要把自己的项目、config、日志或导出作品提交到源码仓库。

## 从源码构建

普通创作者使用上面的工坊配置流程即可。这个仓库是 0.1.3 源码，不附带已编译 DLL；不要把 GitHub 的 Source code ZIP 当作可直接安装的工坊包。

开发者需要 Windows 的 .NET Framework C# 编译器，以及自己的 Rain World v1.11.8 安装和其自带 BepInEx/游戏程序集。在仓库根目录打开 PowerShell，运行下面整段后输入包含 RainWorld.exe 的文件夹：

```powershell
& {
    $miGame = (Read-Host 'Full Rain World folder path (contains RainWorld.exe)').Trim().Trim('"')
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\build.ps1 -GameRoot $miGame
}
```

输出为 `mod/plugins/MoreIterators.dll`。仅编译，不自动替换游戏文件。检查编译器的成功提示后，再关闭游戏并将 DLL 放入用于测试的 MI 核心模组的 `plugins` 目录。源码中的网页、模板和语言文件分别位于 `editor`、`templates`、`localization`；引用库从游戏目录读取，不要提交到仓库。

公开源码保留 `release-layout.json`，网页默认仍使用用户数据目录。版本信息以 `version.json` 为准。

---

## English
MoreIterators is a free, open-source OC creation tool for **Rain World**. Use its local web editor to customize iterators, write dialogue, create pearls and broadcasts, and animate projections, then check the results in the game. Finished creations can be exported as standalone playable mods.

Current version: **0.1.3**. The mod targets Rain World **v1.11.8** and is still in development and testing.

[Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3823802510) · [Required: Warp Menu](https://steamcommunity.com/sharedfiles/filedetails/?id=2920446893) · [Rained room editor](https://github.com/pkhead/rained/releases) · [Discord](https://discord.gg/JBNxgz7E4h)

### Features

- **Appearance and textures:** Customize the puppet, eyes, antennae, arms, sleeves, robe, and halo, with asymmetric parts, layered painting, and undo/redo.
- **Dialogue:** Write first meetings, later meetings, and looping dialogue; configure pearl and item responses; bind eye expressions, movement, and projections to dialogue lines.
- **Pearl text:** Design pearl appearances, assign readers, write text and affinity variations, and configure repeat-reading responses and spawn locations.
- **Broadcasts:** Write broadcasts page by page with shared playback settings. Assign colors by speaker and import broadcast JSON exported from RainocTool.
- **Projection animation:** Import transparent PNGs, edit tracks and keyframes, and choose linear, smooth, or step transitions. Replace images without rebuilding their tracks or keyframes.
- **Rooms and export:** Manage iterator chambers, waiting rooms, and their connections. Use Rained for custom rooms and export selected creations as standalone playable mods.
- **Local preview and project management:** Use browser previews, in-game testing, save history, and tools for transferring associated content. Iterator voice is an experimental feature.

### What's new in 0.1.3

- Align work-pearl pile positions with the chamber’s usable interior and fix pearls collecting against walls or failing to return after zero gravity resumes.
- Keep the selected part, canvas view and panel scroll positions when undoing or redoing paint, including the first stroke after switching parts.
- Selecting a paint part automatically expands and scrolls to its corresponding settings on the left.
- Replace projection images and undo replacements while preserving tracks and keyframes; tidy asset actions and track controls.
- Start strokes outside the canvas and clip them at the image edges; gestures that never touch the image do not create edit history.

### Download and feedback

The Workshop item is currently in friends-only testing. Contact the author if you cannot access it.

For playing and creating, use the [Steam Workshop version](https://steamcommunity.com/sharedfiles/filedetails/?id=3823802510) and enable its required dependency, [Warp Menu](https://steamcommunity.com/sharedfiles/filedetails/?id=2920446893). For custom rooms, download [Rained from its official releases](https://github.com/pkhead/rained/releases).

Join our [Discord](https://discord.gg/JBNxgz7E4h) to discuss ideas and report problems. Please include the mod version, reproduction steps, and relevant errors or screenshots. Before sharing logs or project files, check for anything you want to keep private.

### Thanks

Thanks for testing and assistance: 粉笔, LL77, DESANTA, steelmachine, timerteo, and Anonymous Tester.

### License

The project code is licensed under the [MIT License](LICENSE). Third-party assets retain their original rights: Fusion Pixel fonts use [SIL OFL 1.1](editor/fonts/Fusion-Pixel-OFL.txt), with their [source notice](editor/fonts/SOURCE.txt) included. Rain World assets in the reference preview are not relicensed under this project’s MIT license. Game and dependency assemblies are not included; builds use your own game installation.

Copyright (c) 2026 Rey544

### First-time setup (Windows)

For ordinary 64-bit Windows 10/11 PCs using the Steam Workshop release. Python is needed for the local editors; Rained is only needed if you want to edit room terrain.
Workshop: https://steamcommunity.com/sharedfiles/filedetails/?id=3823802510
Required Warp Menu: https://steamcommunity.com/sharedfiles/filedetails/?id=2920446893
Enable both mods in the game's Remix menu and apply the changes.

#### 1. Install Python

Visit https://www.python.org/downloads/windows/ and install the official Python install manager. Reopen PowerShell and run:

```powershell
py install 3.13
```

If an older py launcher treats install as a filename and you have installed the manager, use:

```powershell
pymanager install 3.13
```

Skip installation if Python 3.13 is already installed. An existing working Python 3.10+ is also supported; if you keep another version, change every -3.13 argument in this guide accordingly.
Alternatively, select Windows installer (64-bit) from a 3.13 release page that offers it. In the regular .exe installer, select Add python.exe to PATH and keep pip and Launcher enabled. Do not choose the embeddable package. Not every 3.13.x release includes a traditional installer.

Reopen your terminal after installation and run:

```powershell
py -3.13 --version
```

It should print Python 3.13.x.

#### 2. Find MI's Workshop folder and install the image dependency

In your Steam library, right-click Rain World → Manage → Browse local files. Keep the address of the folder containing RainWorld.exe for the next step.
MI is usually under steamapps\workshop\content\312520\3823802510 in the same Steam library. Open the folder containing modinfo.json, editor, and 创建桌面快捷方式.cmd. Do not enter editor before running these relative-path commands.

Type powershell into that folder's address bar and press Enter. In the PS ...> window, run:

```powershell
py -3.13 -m pip install -r .\editor\requirements.txt
py -3.13 -c "import sys, PIL; print(sys.executable); print('Pillow', PIL.__version__)"
```

The second command should show a Python path and Pillow version without an error. Use MI's requirements file; do not install an unrestricted latest Pillow version separately.

Paste commands into PowerShell, not the webpage, Python's >>> prompt, or a running program's server> prompt. This guide does not run server.py directly: the launcher starts the service in the background, so later commands cannot be swallowed by the server's input.

#### 3. Configure the Rain World path

Save your webpage and Rained work first. If MI's backend is already running, restart it after configuration as described in step 6.
In the same PowerShell window, paste this entire block and press Enter. Include the first function line and the final }. It only defines the configuration helper; it does not change any files.

```powershell
function Set-MIPath {
    param([string]$Name, [string]$Value)
    @'
import json, os, sys, uuid
from pathlib import Path
k, v = sys.argv[1], sys.argv[2].strip().strip('"')
q = Path(v)
assert q.is_absolute(), 'Use a full absolute path.'
if k == 'gameRoot':
    assert (q/'RainWorld.exe').is_file(), 'RainWorld.exe not found.'
elif k == 'rainedExecutable':
    assert q.name.lower() == 'rained.exe' and q.is_file(), 'Rained.exe not found.'
    assert (q.parent/'Data').is_dir(), 'Rained Data folder missing.'
else:
    raise ValueError('Unknown setting.')
d = Path(os.environ.get('MORE_ITERATORS_DATA') or Path.home()/'AppData/LocalLow/Videocult/Rain World/MoreIterators/data')
assert d.is_absolute(), 'Invalid data path.'
p = d/'config.json'
before = p.read_bytes() if p.exists() else None
def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('Duplicate JSON key: '+key)
        result[key] = value
    return result
s = json.loads(before.decode('utf-8-sig'), object_pairs_hook=unique) if before is not None else {}
assert isinstance(s, dict), 'Config must be an object.'
v = str(q)
if s.get(k) == v and before and not before.startswith(b'\xef\xbb\xbf'):
    print('Already configured:', p)
    sys.exit(0)
s[k] = v
data = (json.dumps(s, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8')
d.mkdir(parents=True, exist_ok=True)
t = d/('.config-'+uuid.uuid4().hex+'.tmp')
try:
    t.write_bytes(data)
    if (p.read_bytes() if p.exists() else None) != before: raise RuntimeError('Config changed; retry.')
    if before is not None:
        backup = d/('config.before-setup-'+uuid.uuid4().hex+'.bak')
        backup.write_bytes(before)
        print('Backup:', backup)
    os.replace(t, p)
    print('OK:', k, '=', v, '\nConfig:', p)
finally:
    t.unlink(missing_ok=True)
'@ | py -3.13 - $Name $Value
    if ($LASTEXITCODE -ne 0) { throw 'Setup failed. Keep this error.' }
}
```

Then paste this entire block, press Enter, and enter the full folder path containing RainWorld.exe when prompted. Enter the folder, not the executable itself. Spaces and non-English characters in the path are supported.

```powershell
& {
    $miGame = Read-Host 'Full Rain World folder path (contains RainWorld.exe)'
    Set-MIPath gameRoot $miGame
}
```

Success prints OK and the Config path. Existing settings are preserved and a config.before-setup-*.bak backup is created when needed. Already configured means no rewrite is necessary. If there is an error, stop here; do not delete config.json or your projects.
Workshop projects and configuration normally live in:
%USERPROFILE%\AppData\LocalLow\Videocult\Rain World\MoreIterators\data
If you deliberately set MORE_ITERATORS_DATA, the helper uses that directory. New users do not need to set it.

#### 4. Create a desktop shortcut and open the editor

Return to the 3823802510 folder and double-click 创建桌面快捷方式.cmd (Create desktop shortcut). It creates MI 外观编辑器 on your desktop. Double-click that shortcut to open the webpage.
The default address is http://127.0.0.1:18747, but an existing configuration may use another port; use the address actually opened.

If the shortcut creator cannot find Python/Pillow even though step 2 succeeded, open PowerShell in the same folder and run this block:

```powershell
& {
    $miPython = py -3.13 -c "import sys, PIL; print(sys.executable)"
    if ($LASTEXITCODE -ne 0) { throw 'Check Python and Pillow first.' }
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\editor\launch_studio.ps1 -PythonExe $miPython -CreateShortcut
}
```

 This explicitly uses the verified Python, including setups with multiple Python versions or the install manager. Recreate the shortcut after moving the mod directory or changing the Python installation location.

#### 5. Apply your first creation

Create a project in the webpage → Save → Apply to game. Save stores the author project; Apply generates the local game content.
The first application creates 更多迭代器 · 本地作品 (moreiterators.local). Enable this generated local content mod in Remix and apply. If it is not listed yet, restart the game, then enable it. MI's core and your local creations are separate mods. Restart when the game requests it after enabling the mod; newly added rooms also require a game restart before testing.

#### 6. Restart the correct MI backend after configuration

Closing the browser does not stop the backend. The simplest option is to save your work, restart Windows, then use the shortcut again.
Alternatively, open /api/health at the current editor's address, keeping its port. Check that service is more-iterators-studio and editorDirectory points to your intended MI copy; note the pid. In Task Manager's Details tab, end only the Python process with that PID, then reopen the shortcut. Do not end every Python process.
Use this check if another editor directory is using the port. Deleting your projects will not fix that conflict.

#### 7. Optional: install and connect Rained

Download a complete Windows release archive: https://github.com/pkhead/rained/releases
Do not download Source code or copy only the executable. Extract the full archive to a permanent location, such as D:\Tools\Rained. Confirm that Rained.exe opens normally and complete its initial asset setup.

MI currently uses the Data folder beside Rained.exe. Put the complete assets there and point Rained itself to the same folder in File → Preferences → Data Path; Tools → Asset Manager also manages assets. For example:
D:\Tools\Rained\Rained.exe
D:\Tools\Rained\Data\Graphics
D:\Tools\Rained\Data\Props
D:\Tools\Rained\Data\Levels
The vanilla chamber source also needs the appropriate Data\LevelEditorProjects assets. Data is not Rain World's RainWorld_Data folder and must not be an empty placeholder.

Return to the same PowerShell window. If it is a new window, first rerun the complete block beginning with function Set-MIPath in step 3. Then run:

```powershell
& {
    $miRained = Read-Host 'Full path to Rained.exe'
    Set-MIPath rainedExecutable $miRained
}
```

When prompted, paste the full path to the real Rained.exe, for example using Copy as path in File Explorer. Do not enter a folder, .lnk shortcut, or Rained.Console.exe. Then restart the MI backend as in step 6.

#### 8. Open, edit, and synchronize a room

Select your project on MI's Appearance page and expand Room projects on the left.
Waiting room: Open waiting room → edit in Rained and Ctrl+S to save the opened source → return to MI and select Sync waiting room.
Iterator chamber: Open chamber → edit and save → Sync iterator chamber.

Sync automatically renders the saved source and applies the result to the game. Wait for the success message, then re-enter the room in-game to check it. The normal workflow does not need a separate manual render. Do not rename or save the source elsewhere first, because MI will still synchronize the original project file.
Region connections edits room links; it does not replace terrain synchronization here. An existing external room cannot be overwritten by this project.

#### Common problems

- py is missing: reopen PowerShell. If it is still missing, repair the official Python install manager installation. For a traditional installer, check that Launcher is enabled. Do not repeatedly enter python and continue at the >>> prompt.
- No module named PIL: install requirements with the same Python that starts MI, then recreate the shortcut using the block in step 4.
- Missing modinfo.json, requirements.txt, or studio.ico: check the folder and complete package. Use the mod root containing editor; do not copy just the startup scripts.
- Rained still cannot be found: restart the backend, not just the browser. Compare /api/health's dataDirectory with the Config path printed by the helper.
- Rained opens but sync fails: check the full assets in its adjacent Data folder. Try File → Render (Ctrl+R) in Rained to see the actual rendering error; after fixing it, synchronize from MI. An automatic render exceeding 180 seconds reports a timeout, not success.
- Missing editable source: a rendered game-room .txt is not a Rained source project. The new waiting room includes its source; the chamber requires the appropriate editable SS_AI source assets. Keep the full error instead of renaming an incompatible file to replace it.
- Startup failure: the error dialog provides a log path. Normally check studio-launch-error.log and server-startup.log under data\archive\logs. Do not delete data to fix startup.

For GitHub source users: this guide primarily covers the Workshop package. The public source copy retains release-layout.json and therefore uses the same user data directory as the release. Only the original development layout without that file defaults to a repository-local data directory. The configuration helper defaults to the user data directory. Do not run two editor copies simultaneously, mix their shortcuts, or commit your projects, configuration, logs, or exported creations to the source repository.

### Build from source

Creators can use the Workshop setup above. This repository contains the 0.1.3 source without a precompiled DLL; GitHub’s Source code ZIP is not a ready-to-install Workshop package.

Developers need the Windows .NET Framework C# compiler, their own Rain World v1.11.8 installation, and its BepInEx/game assemblies. Open PowerShell in the repository root, paste this block, and enter the folder containing RainWorld.exe:

```powershell
& {
    $miGame = (Read-Host 'Full Rain World folder path (contains RainWorld.exe)').Trim().Trim('"')
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\build.ps1 -GameRoot $miGame
}
```

The output is `mod/plugins/MoreIterators.dll`. Building does not install it. After a successful build, close the game and place the DLL in the `plugins` directory of the MI core mod used for testing. Web files, templates, and translations are in `editor`, `templates`, and `localization`. Reference assemblies are read from your game installation; do not commit them to this repository.

The public source retains `release-layout.json`, so the web editor defaults to the user data directory. `version.json` is the version source.
