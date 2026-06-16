# MC Cleaner

Minecraft 存档轻量化清理工具。它会按区块 `InhabitedTime` 清理低停留时间区块，减少存档体积。

A lightweight Minecraft save cleanup tool. It removes low-`InhabitedTime` chunks to reduce save size.

## 版本

- `MC-Cleaner-GUI.exe`: 可视化版本，支持选择存档文件夹和自由填写删除阈值。
- `MC-Cleaner-Lite.exe`: 极简版本，把 exe 放进目标存档根目录，双击后自动清理停留时间小于 1 分钟的区块。
- `mc_cleaner.py`: 命令行版本，适合脚本化调用。

## Versions

- `MC-Cleaner-GUI.exe`: GUI version with save-folder selection and a configurable cleanup threshold.
- `MC-Cleaner-Lite.exe`: Minimal version. Put the exe in the target save folder and double-click it to clean chunks with less than 1 minute of inhabited time.
- `mc_cleaner.py`: Command-line version for scripted use.

## 功能特点

- 先扫描预览，再确认执行。
- 默认自动备份被修改的文件。
- 使用临时文件写入，成功后再替换原文件。
- 支持主世界、下界、末地。
- 同步处理 `region`、`entities`、`poi`。
- 可配置保留阈值。
- GUI 版通过勾选框选择是否备份。
- Lite 版运行时输入 `y/n` 选择是否备份。

## Features

- Preview scan before cleanup.
- Optional backup before writing modified files.
- Writes to temporary files first, then replaces originals after success.
- Supports the Overworld, Nether, and End.
- Cleans matching `region`, `entities`, and `poi` data together.
- Configurable inhabited-time threshold.
- GUI version uses a checkbox to choose whether to create backups.
- Lite version asks for `y/n` at runtime to choose whether to create backups.

## GUI 版

运行 `releases/MC-Cleaner-GUI.exe`：

- 点击“浏览”选择 Minecraft 存档文件夹。
- 填写“删除停留时间小于多少分钟的区块”。
- 勾选或取消“清理前创建备份”。
- 点击“预览扫描”查看预计删除数量和减少体积。
- 点击“开始清理”执行。

## GUI Version

Run `releases/MC-Cleaner-GUI.exe`:

- Click "Browse" to choose a Minecraft save folder.
- Enter the target threshold for chunks with inhabited time below the chosen number of minutes.
- Check or uncheck "Create backup before cleanup".
- Click "Preview Scan" to see the expected deleted chunks and reduced size.
- Click "Start Cleanup" to run the cleanup.

## Lite 版

把 `releases/MC-Cleaner-Lite.exe` 放在存档根目录，也就是有 `level.dat` 或 `region` 文件夹的位置，然后双击运行。

Lite 版固定清理停留时间小于 1 分钟的区块。清理前会询问是否创建备份，输入 `y` 创建备份，输入 `n` 则不生成任何备份文件。

## Lite Version

Put `releases/MC-Cleaner-Lite.exe` in the save root folder, where `level.dat` or the `region` folder exists, then double-click it.

The Lite version always cleans chunks with less than 1 minute of inhabited time. Before cleanup, it asks whether to create a backup: enter `y` to create one, or `n` to avoid generating any backup files.

## 命令行版

在命令行中运行：

```powershell
python mc_cleaner.py "C:\path\to\.minecraft\saves\你的存档"
```

只预览，不修改文件：

```powershell
python mc_cleaner.py "C:\path\to\world" --dry-run
```

保留停留时间达到 5 分钟的区块：

```powershell
python mc_cleaner.py "C:\path\to\world" --threshold-minutes 5
```

跳过确认直接执行：

```powershell
python mc_cleaner.py "C:\path\to\world" --yes
```

只处理主世界：

```powershell
python mc_cleaner.py "C:\path\to\world" --dimensions overworld
```

## Command-Line Version

Run from a terminal:

```powershell
python mc_cleaner.py "C:\path\to\.minecraft\saves\your-world"
```

Preview only, without modifying files:

```powershell
python mc_cleaner.py "C:\path\to\world" --dry-run
```

Keep chunks with at least 5 minutes of inhabited time:

```powershell
python mc_cleaner.py "C:\path\to\world" --threshold-minutes 5
```

Skip confirmation and run directly:

```powershell
python mc_cleaner.py "C:\path\to\world" --yes
```

Only process the Overworld:

```powershell
python mc_cleaner.py "C:\path\to\world" --dimensions overworld
```

## 注意事项

- 使用前请关闭 Minecraft 和服务器，避免存档正在被写入。
- 首次使用建议先加 `--dry-run` 看预览结果。
- 如果选择创建备份，工具会在存档目录创建 `mc_cleaner_backup_时间戳` 备份目录。
- 如果不选择备份，不会生成任何备份文件。
- 如果工具发现异常 `.mca` 表项，会跳过该文件以保护存档。

## Notes

- Close Minecraft or the server before using this tool so the save is not being written.
- For first use, run with `--dry-run` to review the preview result.
- If backup is enabled, the tool creates a `mc_cleaner_backup_timestamp` folder inside the save folder.
- If backup is disabled, no backup files are generated.
- If abnormal `.mca` table entries are detected, the file is skipped to protect the save.

## 打包

开发环境中安装 PyInstaller 后运行：

```powershell
.\build_exe.ps1
```

打包产物会生成在 `dist/`，发布用 exe 放在 `releases/`。

## Build

After installing PyInstaller in the development environment, run:

```powershell
.\build_exe.ps1
```

Build outputs are generated in `dist/`, and release executables are copied to `releases/`.
