import argparse
import datetime as dt
import gzip
import os
import shutil
import sys
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple

SECTOR_SIZE = 4096
HEADER_SIZE = 8192
DEFAULT_THRESHOLD_TICKS = 20 * 60
CHUNK_COUNT = 1024

DIMENSIONS = {
    "overworld": Path("."),
    "nether": Path("DIM-1"),
    "end": Path("DIM1"),
}


@dataclass
class ChunkRecord:
    idx: int
    timestamp: int
    raw_data: bytes
    inhabited_time: Optional[int] = None


@dataclass
class RegionPlan:
    region_path: Path
    dimension_root: Path
    relative_region_path: Path
    kept_indices: Set[int]
    deleted_indices: Set[int]
    original_size: int
    new_size: int
    invalid_entries: int = 0

    @property
    def saved_bytes(self) -> int:
        return max(0, self.original_size - self.new_size)


@dataclass
class FileWritePlan:
    path: Path
    kept_indices: Set[int]
    reason: str


@dataclass
class ScanSummary:
    region_plans: List[RegionPlan]
    write_plans: List[FileWritePlan]
    skipped_files: List[Tuple[Path, str]]

    @property
    def deleted_chunks(self) -> int:
        return sum(len(plan.deleted_indices) for plan in self.region_plans)

    @property
    def saved_bytes(self) -> int:
        return sum(plan.saved_bytes for plan in self.region_plans)


def format_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def skip_tag_data(data: bytes, ptr: int, tag_type: int) -> Optional[int]:
    try:
        if tag_type == 0x01:
            return ptr + 1
        if tag_type == 0x02:
            return ptr + 2
        if tag_type == 0x03:
            return ptr + 4
        if tag_type == 0x04:
            return ptr + 8
        if tag_type == 0x05:
            return ptr + 4
        if tag_type == 0x06:
            return ptr + 8
        if tag_type == 0x07:
            arr_len = int.from_bytes(data[ptr : ptr + 4], "big", signed=True)
            return ptr + 4 + arr_len
        if tag_type == 0x08:
            str_len = int.from_bytes(data[ptr : ptr + 2], "big")
            return ptr + 2 + str_len
        if tag_type == 0x09:
            list_type = data[ptr]
            list_len = int.from_bytes(data[ptr + 1 : ptr + 5], "big", signed=True)
            ptr += 5
            for _ in range(max(0, list_len)):
                ptr = skip_tag_data(data, ptr, list_type)
                if ptr is None or ptr > len(data):
                    return None
            return ptr
        if tag_type == 0x0A:
            while ptr < len(data):
                sub_type = data[ptr]
                ptr += 1
                if sub_type == 0x00:
                    return ptr
                name_len = int.from_bytes(data[ptr : ptr + 2], "big")
                ptr += 2 + name_len
                ptr = skip_tag_data(data, ptr, sub_type)
                if ptr is None or ptr > len(data):
                    return None
            return None
        if tag_type == 0x0B:
            arr_len = int.from_bytes(data[ptr : ptr + 4], "big", signed=True)
            return ptr + 4 + arr_len * 4
        if tag_type == 0x0C:
            arr_len = int.from_bytes(data[ptr : ptr + 4], "big", signed=True)
            return ptr + 4 + arr_len * 8
        return None
    except (IndexError, ValueError, OverflowError):
        return None


def get_inhabited_time(compressed_data: bytes, compression_type: int, safe_value: int) -> int:
    try:
        if compression_type == 1:
            nbt_data = gzip.decompress(compressed_data)
        elif compression_type == 2:
            nbt_data = zlib.decompress(compressed_data)
        elif compression_type == 3:
            nbt_data = compressed_data
        else:
            return safe_value

        if not nbt_data or nbt_data[0] != 0x0A:
            return safe_value

        ptr = 1
        root_name_len = int.from_bytes(nbt_data[ptr : ptr + 2], "big")
        ptr += 2 + root_name_len

        while ptr < len(nbt_data):
            tag_type = nbt_data[ptr]
            ptr += 1
            if tag_type == 0x00:
                break

            name_len = int.from_bytes(nbt_data[ptr : ptr + 2], "big")
            ptr += 2
            tag_name = nbt_data[ptr : ptr + name_len].decode("utf-8", "ignore")
            ptr += name_len

            if tag_type == 0x04 and tag_name == "InhabitedTime":
                return int.from_bytes(nbt_data[ptr : ptr + 8], "big", signed=True)

            ptr = skip_tag_data(nbt_data, ptr, tag_type)
            if ptr is None:
                break

        return 0
    except (OSError, EOFError, zlib.error, ValueError, IndexError):
        return safe_value


def read_mca_records(file_path: Path, threshold_ticks: Optional[int] = None) -> Tuple[List[Optional[ChunkRecord]], int]:
    content = file_path.read_bytes()
    if len(content) < HEADER_SIZE:
        return [None] * CHUNK_COUNT, 1

    loc_table = content[:4096]
    ts_table = content[4096:8192]
    records: List[Optional[ChunkRecord]] = []
    invalid_entries = 0
    safe_value = (threshold_ticks or DEFAULT_THRESHOLD_TICKS) + 1

    for idx in range(CHUNK_COUNT):
        entry = loc_table[idx * 4 : (idx + 1) * 4]
        offset = int.from_bytes(entry[:3], "big")
        sector_count = entry[3]
        if offset == 0:
            records.append(None)
            continue
        if sector_count == 0:
            records.append(None)
            invalid_entries += 1
            continue

        byte_offset = offset * SECTOR_SIZE
        raw_end = byte_offset + sector_count * SECTOR_SIZE
        if byte_offset + 5 > len(content) or raw_end > len(content):
            records.append(None)
            invalid_entries += 1
            continue

        data_len = int.from_bytes(content[byte_offset : byte_offset + 4], "big")
        if data_len <= 1 or data_len > sector_count * SECTOR_SIZE - 4:
            records.append(None)
            invalid_entries += 1
            continue

        compression_type = content[byte_offset + 4]
        compressed_start = byte_offset + 5
        compressed_end = compressed_start + data_len - 1
        if compressed_end > raw_end:
            records.append(None)
            invalid_entries += 1
            continue

        inhabited_time = None
        if threshold_ticks is not None:
            inhabited_time = get_inhabited_time(
                content[compressed_start:compressed_end],
                compression_type,
                safe_value,
            )

        records.append(
            ChunkRecord(
                idx=idx,
                timestamp=int.from_bytes(ts_table[idx * 4 : (idx + 1) * 4], "big"),
                raw_data=content[byte_offset:raw_end],
                inhabited_time=inhabited_time,
            )
        )

    return records, invalid_entries


def build_mca_bytes(records: List[Optional[ChunkRecord]], kept_indices: Set[int]) -> bytes:
    new_loc_table = bytearray(4096)
    new_ts_table = bytearray(4096)
    new_body = bytearray()
    current_sector = 2

    for record in records:
        if record is None or record.idx not in kept_indices:
            continue

        sector_count = len(record.raw_data) // SECTOR_SIZE
        new_loc_table[record.idx * 4 : record.idx * 4 + 3] = current_sector.to_bytes(3, "big")
        new_loc_table[record.idx * 4 + 3] = sector_count
        new_ts_table[record.idx * 4 : record.idx * 4 + 4] = record.timestamp.to_bytes(4, "big")
        new_body.extend(record.raw_data)
        current_sector += sector_count

    return bytes(new_loc_table + new_ts_table + new_body)


def discover_world_path(path: Path) -> Path:
    path = path.expanduser().resolve()
    if (path / "level.dat").exists():
        return path
    if (path / "region").is_dir():
        return path
    raise FileNotFoundError(f"未找到 Minecraft 存档结构: {path}")


def dimension_roots(world_path: Path, names: List[str]) -> List[Tuple[str, Path]]:
    roots = []
    for name in names:
        rel = DIMENSIONS[name]
        root = world_path / rel
        if root.exists():
            roots.append((name, root))
    return roots


def plan_clean(world_path: Path, threshold_ticks: int, dimensions: List[str]) -> ScanSummary:
    region_plans: List[RegionPlan] = []
    write_plans: List[FileWritePlan] = []
    skipped_files: List[Tuple[Path, str]] = []

    for _dimension_name, dim_root in dimension_roots(world_path, dimensions):
        region_dir = dim_root / "region"
        if not region_dir.is_dir():
            continue

        for region_path in sorted(region_dir.glob("*.mca")):
            records, invalid_entries = read_mca_records(region_path, threshold_ticks)
            if invalid_entries:
                skipped_files.append((region_path, f"发现 {invalid_entries} 个异常区块表项，已跳过以保护存档"))
                continue

            existing_indices = {record.idx for record in records if record is not None}
            kept_indices = {
                record.idx
                for record in records
                if record is not None and (record.inhabited_time or 0) >= threshold_ticks
            }
            deleted_indices = existing_indices - kept_indices
            if not deleted_indices:
                continue

            new_size = len(build_mca_bytes(records, kept_indices))
            relative_region_path = region_path.relative_to(region_dir)
            plan = RegionPlan(
                region_path=region_path,
                dimension_root=dim_root,
                relative_region_path=relative_region_path,
                kept_indices=kept_indices,
                deleted_indices=deleted_indices,
                original_size=region_path.stat().st_size,
                new_size=new_size,
            )
            region_plans.append(plan)
            write_plans.append(FileWritePlan(region_path, kept_indices, "region"))

            for companion_folder in ("entities", "poi"):
                companion_path = dim_root / companion_folder / relative_region_path
                if companion_path.exists():
                    companion_records, companion_invalid = read_mca_records(companion_path)
                    if companion_invalid:
                        skipped_files.append((companion_path, f"发现 {companion_invalid} 个异常区块表项，已跳过"))
                        continue
                    companion_existing = {record.idx for record in companion_records if record is not None}
                    companion_kept = companion_existing - deleted_indices
                    if companion_existing != companion_kept:
                        write_plans.append(FileWritePlan(companion_path, companion_kept, companion_folder))

    return ScanSummary(region_plans, write_plans, skipped_files)


def backup_file(file_path: Path, world_path: Path, backup_root: Path) -> None:
    relative_path = file_path.relative_to(world_path)
    target = backup_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file_path, target)


def write_mca_safely(file_path: Path, kept_indices: Set[int]) -> None:
    records, invalid_entries = read_mca_records(file_path)
    if invalid_entries:
        raise RuntimeError(f"{file_path} 出现异常区块表项，取消写入")

    new_content = build_mca_bytes(records, kept_indices)
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=file_path.parent, suffix=".tmp") as tmp:
        tmp.write(new_content)
        tmp_path = Path(tmp.name)

    try:
        os.replace(tmp_path, file_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def execute_clean(world_path: Path, summary: ScanSummary, make_backup: bool) -> Optional[Path]:
    backup_root = None
    if make_backup and summary.write_plans:
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_root = world_path / f"mc_cleaner_backup_{stamp}"
        for plan in summary.write_plans:
            backup_file(plan.path, world_path, backup_root)

    for plan in summary.write_plans:
        write_mca_safely(plan.path, plan.kept_indices)

    return backup_root


def print_summary(summary: ScanSummary) -> None:
    print("\n扫描结果")
    print("-" * 40)
    print(f"需要清理的 region 文件: {len(summary.region_plans)}")
    print(f"将删除区块数量: {summary.deleted_chunks}")
    print(f"预计减少体积: {format_size(summary.saved_bytes)}")
    print(f"实际会写入的文件: {len(summary.write_plans)} (包含 region/entities/poi)")

    if summary.skipped_files:
        print("\n已跳过的文件:")
        for path, reason in summary.skipped_files:
            print(f"  - {path}: {reason}")

    if summary.region_plans:
        print("\n前 10 个清理目标:")
        for plan in summary.region_plans[:10]:
            print(
                f"  - {plan.region_path.name}: 删除 {len(plan.deleted_indices)} 个区块，"
                f"约减少 {format_size(plan.saved_bytes)}"
            )
        if len(summary.region_plans) > 10:
            print(f"  ... 还有 {len(summary.region_plans) - 10} 个文件")


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
    parser.add_argument("--threshold-minutes", type=float, default=1.0, help="保留停留时间达到多少分钟的区块")
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

    threshold_ticks = max(0, int(args.threshold_minutes * 60 * 20))
    print(f"\n存档目录: {world_path}")
    print(f"保留阈值: {args.threshold_minutes:g} 分钟 ({threshold_ticks} ticks)")

    summary = plan_clean(world_path, threshold_ticks, args.dimensions)
    print_summary(summary)

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
    print(f"预计减少体积: {format_size(summary.saved_bytes)}")

    if getattr(sys, "frozen", False):
        input("\n按回车键退出...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
