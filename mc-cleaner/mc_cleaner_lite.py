import sys
from pathlib import Path

from mc_cleaner_core import DEFAULT_THRESHOLD_TICKS, DIMENSIONS, discover_world_path, execute_clean, plan_clean, summarize_lines


def app_folder() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main() -> int:
    print("=== MC Cleaner Lite ===")
    print("自动清理当前存档中停留时间小于 1 分钟的区块。")

    try:
        world_path = discover_world_path(app_folder())
    except FileNotFoundError as exc:
        print(f"\n[错误] {exc}")
        input("\n请把 Lite 版 exe 放在存档根目录后再运行。按回车退出...")
        return 1

    print(f"\n存档目录: {world_path}")
    print("保留阈值: 1 分钟 (1200 ticks)")
    summary = plan_clean(world_path, DEFAULT_THRESHOLD_TICKS, list(DIMENSIONS))
    print("\n".join(summarize_lines(summary)))

    if not summary.write_plans:
        print("\n没有需要清理的内容。")
        input("\n按回车退出...")
        return 0

    backup_root = execute_clean(world_path, summary, make_backup=True)
    print("\n清理完成。")
    print(f"删除区块: {summary.deleted_chunks}")
    if backup_root:
        print(f"备份位置: {backup_root}")
    input("\n按回车退出...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
