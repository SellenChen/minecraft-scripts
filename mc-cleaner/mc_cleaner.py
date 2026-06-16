import argparse
import sys
from pathlib import Path
from typing import List

from mc_cleaner_core import DEFAULT_THRESHOLD_TICKS, DIMENSIONS, discover_world_path, execute_clean, minutes_to_ticks, plan_clean, summarize_lines


def parse_dimensions(value: str) -> List[str]:
    if value.lower() == "all":
        return list(DIMENSIONS)
    names = [item.strip().lower() for item in value.split(",") if item.strip()]
    invalid = [name for name in names if name not in DIMENSIONS]
    if invalid:
        raise argparse.ArgumentTypeError(f"未知维度: {', '.join(invalid)}")
    return names


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minecraft 存档轻量化清理工具")
    parser.add_argument("path", nargs="?", default=".", help="存档根目录，默认当前目录")
    parser.add_argument("--threshold-minutes", type=float, default=DEFAULT_THRESHOLD_TICKS / 20 / 60, help="保留停留时间达到多少分钟的区块")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写入文件")
    parser.add_argument("--yes", action="store_true", help="跳过确认，直接执行")
    parser.add_argument("--no-backup", action="store_true", help="不创建备份")
    parser.add_argument("--dimensions", type=parse_dimensions, default=list(DIMENSIONS), help="all 或 overworld,nether,end")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    print("=== Minecraft 存档清理工具 ===")
    print("会按 InhabitedTime 清理低停留时间区块，并同步处理 entities/poi。")

    try:
        world_path = discover_world_path(Path(args.path))
    except FileNotFoundError as exc:
        print(f"\n[错误] {exc}")
        if getattr(sys, "frozen", False):
            input("\n按回车键退出...")
        return 1

    threshold_ticks = minutes_to_ticks(args.threshold_minutes)
    print(f"\n存档目录: {world_path}")
    print(f"保留阈值: {args.threshold_minutes:g} 分钟 ({threshold_ticks} ticks)")

    summary = plan_clean(world_path, threshold_ticks, args.dimensions)
    print("\n扫描结果")
    print("-" * 40)
    print("\n".join(summarize_lines(summary)))

    if not summary.write_plans:
        print("\n没有需要清理的内容。")
        if getattr(sys, "frozen", False):
            input("\n按回车键退出...")
        return 0

    if args.dry_run:
        print("\n当前是预览模式，没有修改任何文件。")
        return 0

    if not args.yes:
        answer = input("\n确认开始清理？输入 YES 继续: ").strip()
        if answer != "YES":
            print("已取消，没有修改任何文件。")
            return 0

    backup_root = execute_clean(world_path, summary, make_backup=not args.no_backup)
    print("\n清理完成。")
    if backup_root:
        print(f"备份位置: {backup_root}")
    print(f"删除区块: {summary.deleted_chunks}")

    if getattr(sys, "frozen", False):
        input("\n按回车键退出...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
