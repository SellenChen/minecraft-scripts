# Minecraft Scripts

这个仓库用于存放 Minecraft 相关脚本。目前包含一个存档清理工具：

- `mc_cleaner.py`: 按区块 `InhabitedTime` 清理低停留时间区块，减少存档体积。

## mc_cleaner.py

功能特点：

- 先扫描预览，再确认执行。
- 默认自动备份被修改的文件。
- 使用临时文件写入，成功后再替换原文件。
- 支持主世界、下界、末地。
- 同步处理 `region`、`entities`、`poi`。
- 可配置保留阈值。

## 使用方式

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

## 注意事项

- 使用前请关闭 Minecraft 和服务器，避免存档正在被写入。
- 首次使用建议先加 `--dry-run` 看预览结果。
- 默认会在存档目录创建 `mc_cleaner_backup_时间戳` 备份目录。
- 如果工具发现异常 `.mca` 表项，会跳过该文件以保护存档。
