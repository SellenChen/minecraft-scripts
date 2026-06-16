import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from mc_cleaner_core import DIMENSIONS, discover_world_path, execute_clean, minutes_to_ticks, plan_clean, summarize_lines


class CleanerGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MC Cleaner")
        self.geometry("860x620")
        self.minsize(780, 560)
        self.configure(bg="#0f1117")

        self.result_queue: queue.Queue = queue.Queue()
        self.current_summary = None
        self.current_world = None
        self.world_path = tk.StringVar()
        self.threshold_minutes = tk.StringVar(value="1")
        self.make_backup = tk.BooleanVar(value=True)
        self.dimension_vars = {
            "overworld": tk.BooleanVar(value=True),
            "nether": tk.BooleanVar(value=True),
            "end": tk.BooleanVar(value=True),
        }

        self._build_styles()
        self._build_layout()
        self.after(100, self._poll_queue)

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#0f1117")
        style.configure("Panel.TFrame", background="#171a23", borderwidth=0)
        style.configure("Title.TLabel", background="#0f1117", foreground="#f4f6fb", font=("Segoe UI", 21, "bold"))
        style.configure("Subtle.TLabel", background="#0f1117", foreground="#9ba3b4", font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background="#171a23", foreground="#e7eaf1", font=("Segoe UI", 10))
        style.configure("Hint.TLabel", background="#171a23", foreground="#8c95a8", font=("Segoe UI", 9))
        style.configure("Metric.TLabel", background="#171a23", foreground="#f4f6fb", font=("Segoe UI", 18, "bold"))
        style.configure("TCheckbutton", background="#171a23", foreground="#dfe3ec", font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[("active", "#171a23")], foreground=[("active", "#ffffff")])
        style.configure("Primary.TButton", background="#5b8cff", foreground="#ffffff", borderwidth=0, focusthickness=0, font=("Segoe UI", 10, "bold"), padding=(14, 10))
        style.map("Primary.TButton", background=[("active", "#6d9aff"), ("disabled", "#38415c")])
        style.configure("Ghost.TButton", background="#232938", foreground="#e9edf6", borderwidth=0, focusthickness=0, font=("Segoe UI", 10), padding=(14, 10))
        style.map("Ghost.TButton", background=[("active", "#2c3345"), ("disabled", "#202431")])
        style.configure("TEntry", fieldbackground="#0f1117", foreground="#f3f5f9", insertcolor="#f3f5f9", bordercolor="#31384a", lightcolor="#31384a", darkcolor="#31384a", padding=(10, 8))

    def _build_layout(self) -> None:
        shell = ttk.Frame(self, padding=28)
        shell.pack(fill=tk.BOTH, expand=True)

        ttk.Label(shell, text="MC Cleaner", style="Title.TLabel").pack(anchor="w")
        ttk.Label(shell, text="选择存档、预览可清理区块，然后安全写入并自动备份。", style="Subtle.TLabel").pack(anchor="w", pady=(4, 22))

        config = ttk.Frame(shell, style="Panel.TFrame", padding=18)
        config.pack(fill=tk.X)

        ttk.Label(config, text="存档文件夹", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        path_row = ttk.Frame(config, style="Panel.TFrame")
        path_row.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 16))
        path_row.columnconfigure(0, weight=1)
        ttk.Entry(path_row, textvariable=self.world_path).grid(row=0, column=0, sticky="ew", ipady=3)
        ttk.Button(path_row, text="浏览", style="Ghost.TButton", command=self._choose_folder).grid(row=0, column=1, padx=(10, 0))

        ttk.Label(config, text="删除目标", style="Panel.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(config, text="删除停留时间小于", style="Hint.TLabel").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(config, textvariable=self.threshold_minutes, width=10).grid(row=3, column=1, sticky="w", padx=(8, 6), pady=(8, 0))
        ttk.Label(config, text="分钟的区块", style="Hint.TLabel").grid(row=3, column=2, sticky="w", pady=(8, 0))

        dims = ttk.Frame(config, style="Panel.TFrame")
        dims.grid(row=4, column=0, columnspan=4, sticky="w", pady=(14, 4))
        ttk.Checkbutton(dims, text="主世界", variable=self.dimension_vars["overworld"]).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(dims, text="下界", variable=self.dimension_vars["nether"]).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(dims, text="末地", variable=self.dimension_vars["end"]).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(dims, text="执行前备份", variable=self.make_backup).pack(side=tk.LEFT)

        config.columnconfigure(3, weight=1)

        metrics = ttk.Frame(shell, style="Panel.TFrame", padding=18)
        metrics.pack(fill=tk.X, pady=(16, 0))
        metrics.columnconfigure((0, 1, 2), weight=1)

        self.metric_files = self._metric(metrics, "待清理文件", "0", 0)
        self.metric_chunks = self._metric(metrics, "将删除区块", "0", 1)
        self.metric_size = self._metric(metrics, "预计减少", "0 B", 2)

        actions = ttk.Frame(shell)
        actions.pack(fill=tk.X, pady=(16, 0))
        self.scan_button = ttk.Button(actions, text="预览扫描", style="Ghost.TButton", command=self.scan)
        self.scan_button.pack(side=tk.LEFT)
        self.clean_button = ttk.Button(actions, text="开始清理", style="Primary.TButton", command=self.clean, state=tk.DISABLED)
        self.clean_button.pack(side=tk.LEFT, padx=(10, 0))
        self.status = ttk.Label(actions, text="准备就绪", style="Subtle.TLabel")
        self.status.pack(side=tk.RIGHT)

        log_panel = ttk.Frame(shell, style="Panel.TFrame", padding=12)
        log_panel.pack(fill=tk.BOTH, expand=True, pady=(16, 0))
        self.log = tk.Text(
            log_panel,
            bg="#10131a",
            fg="#dce3ef",
            insertbackground="#dce3ef",
            relief=tk.FLAT,
            bd=0,
            font=("Consolas", 10),
            wrap=tk.WORD,
        )
        self.log.pack(fill=tk.BOTH, expand=True)
        self._append_log("选择一个 Minecraft 存档文件夹开始。")

    def _metric(self, parent: ttk.Frame, title: str, value: str, column: int) -> ttk.Label:
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 12, 0))
        ttk.Label(frame, text=title, style="Hint.TLabel").pack(anchor="w")
        label = ttk.Label(frame, text=value, style="Metric.TLabel")
        label.pack(anchor="w", pady=(4, 0))
        return label

    def _choose_folder(self) -> None:
        selected = filedialog.askdirectory(title="选择 Minecraft 存档文件夹")
        if selected:
            self.world_path.set(selected)
            self.current_summary = None
            self.current_world = None
            self.clean_button.configure(state=tk.DISABLED)
            self._append_log(f"已选择: {selected}")

    def _selected_dimensions(self) -> list:
        return [name for name, var in self.dimension_vars.items() if var.get()]

    def _validate_inputs(self) -> tuple:
        if not self.world_path.get().strip():
            raise ValueError("请先选择存档文件夹。")
        try:
            minutes = float(self.threshold_minutes.get().strip())
        except ValueError as exc:
            raise ValueError("停留时间必须是数字。") from exc
        if minutes < 0:
            raise ValueError("停留时间不能小于 0。")
        dimensions = self._selected_dimensions()
        if not dimensions:
            raise ValueError("至少选择一个维度。")
        return Path(self.world_path.get()), minutes, dimensions

    def scan(self) -> None:
        try:
            folder, minutes, dimensions = self._validate_inputs()
        except ValueError as exc:
            messagebox.showerror("无法扫描", str(exc))
            return

        self._set_busy(True, "正在扫描...")
        self.current_summary = None
        self.current_world = None
        self.clean_button.configure(state=tk.DISABLED)
        self._append_log("")
        self._append_log("开始扫描...")
        threading.Thread(target=self._scan_worker, args=(folder, minutes, dimensions), daemon=True).start()

    def _scan_worker(self, folder: Path, minutes: float, dimensions: list) -> None:
        try:
            world = discover_world_path(folder)
            summary = plan_clean(world, minutes_to_ticks(minutes), dimensions)
            self.result_queue.put(("scan_ok", world, summary))
        except Exception as exc:
            self.result_queue.put(("error", str(exc)))

    def clean(self) -> None:
        if self.current_summary is None:
            messagebox.showinfo("需要先扫描", "请先预览扫描。")
            return
        if not self.current_summary.write_plans:
            messagebox.showinfo("没有可清理内容", "当前扫描结果没有需要写入的文件。")
            return
        if not messagebox.askyesno("确认清理", "将修改存档文件。建议关闭 Minecraft 后继续。是否开始？"):
            return

        self._set_busy(True, "正在清理...")
        self._append_log("")
        self._append_log("开始清理...")
        threading.Thread(target=self._clean_worker, daemon=True).start()

    def _clean_worker(self) -> None:
        try:
            backup_root = execute_clean(self.current_world, self.current_summary, self.make_backup.get())
            self.result_queue.put(("clean_ok", backup_root))
        except Exception as exc:
            self.result_queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                event = self.result_queue.get_nowait()
                kind = event[0]
                if kind == "scan_ok":
                    _world, summary = event[1], event[2]
                    self.current_world = _world
                    self.current_summary = summary
                    self.metric_files.configure(text=str(len(summary.region_plans)))
                    self.metric_chunks.configure(text=str(summary.deleted_chunks))
                    self.metric_size.configure(text=summarize_lines(summary)[2].split(": ", 1)[1])
                    self.clean_button.configure(state=tk.NORMAL if summary.write_plans else tk.DISABLED)
                    self._append_log("\n".join(summarize_lines(summary)))
                    self._set_busy(False, "扫描完成")
                elif kind == "clean_ok":
                    backup_root = event[1]
                    if backup_root:
                        self._append_log(f"备份位置: {backup_root}")
                    self._append_log("清理完成。")
                    self._set_busy(False, "清理完成")
                    messagebox.showinfo("完成", "清理完成。")
                elif kind == "error":
                    self._set_busy(False, "发生错误")
                    self._append_log(f"[错误] {event[1]}")
                    messagebox.showerror("错误", event[1])
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _append_log(self, text: str) -> None:
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)

    def _set_busy(self, busy: bool, text: str) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        self.scan_button.configure(state=state)
        if busy:
            self.clean_button.configure(state=tk.DISABLED)
        elif self.current_summary and self.current_summary.write_plans:
            self.clean_button.configure(state=tk.NORMAL)
        self.status.configure(text=text)


def main() -> None:
    app = CleanerGui()
    app.mainloop()


if __name__ == "__main__":
    main()
