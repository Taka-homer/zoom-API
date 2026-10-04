"""実行するとボタン付きのウィンドウを開く。押すたびに新しい会議リンクを作る。"""

import queue
import threading
import tkinter as tk
from tkinter import ttk

from create_meeting import ZoomError, create_zoom_meeting


def invitation_text(meeting: dict) -> str:
    return "\n".join(
        [
            f"会議 ID: {meeting['meeting_id']}",
            f"パスワード: {meeting['password']}",
            f"参加リンク: {meeting['join_url']}",
        ]
    )


class MeetingWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.results: queue.Queue = queue.Queue()
        self.meeting: dict | None = None
        self.previous_url = ""

        root.title("Zoom 会議を作成")
        root.geometry("680x460")
        root.minsize(560, 420)
        root.configure(bg="#eef3f8")

        style = ttk.Style()
        style.configure("Title.TLabel", font=("Yu Gothic UI", 18, "bold"), background="#eef3f8")
        style.configure("Lead.TLabel", font=("Yu Gothic UI", 10), background="#eef3f8", foreground="#5c6b7a")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Field.TLabel", font=("Yu Gothic UI", 10), background="#ffffff", foreground="#5c6b7a")
        style.configure("Status.TLabel", font=("Yu Gothic UI", 10), background="#ffffff")
        style.configure("Create.TButton", font=("Yu Gothic UI", 12, "bold"))
        style.configure("Copy.TButton", font=("Yu Gothic UI", 10))

        outer = ttk.Frame(root, padding=24, style="Card.TFrame")
        outer.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(outer, text="Zoom 会議を作成", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="ボタンを押すたびに、別の会議 ID と参加リンクが新しく作られます。",
            style="Lead.TLabel",
        ).pack(anchor="w", pady=(4, 16))

        self.create_button = ttk.Button(
            outer,
            text="会議を作成する",
            style="Create.TButton",
            command=self.start_create,
        )
        self.create_button.pack(fill="x", ipady=8)

        self.status = ttk.Label(outer, text="", style="Status.TLabel")
        self.status.pack(anchor="w", pady=(12, 0))

        self.result = ttk.Frame(outer, style="Card.TFrame")
        self.id_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.url_var = tk.StringVar()
        self._add_row(self.result, "会議 ID", self.id_var)
        self._add_row(self.result, "パスワード", self.password_var)
        self._add_row(self.result, "参加リンク", self.url_var)

        self.copy_all = ttk.Button(
            self.result,
            text="ID・パスワード・参加リンクをコピー",
            style="Copy.TButton",
            command=self.copy_all_fields,
        )
        self.copy_all.pack(fill="x", pady=(12, 0), ipady=6)

        root.lift()
        root.attributes("-topmost", True)
        root.after(800, lambda: root.attributes("-topmost", False))

    def _add_row(self, parent: ttk.Frame, label: str, variable: tk.StringVar) -> None:
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x", pady=(10, 0))
        ttk.Label(row, text=label, style="Field.TLabel", width=12).pack(side="left")
        entry = ttk.Entry(row, textvariable=variable, state="readonly")
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(
            row,
            text="コピー",
            style="Copy.TButton",
            command=lambda: self.copy_value(variable.get()),
        ).pack(side="right")

    def start_create(self) -> None:
        self.create_button.state(["disabled"])
        self.status.configure(text="作成中... 新しい参加リンクを発行しています。")
        threading.Thread(target=self._create, daemon=True).start()
        self.root.after(200, self._poll)

    def _create(self) -> None:
        try:
            meeting = create_zoom_meeting()
        except ZoomError as exc:
            self.results.put(exc)
            return
        except Exception as exc:
            self.results.put(ZoomError(f"予期しないエラーが発生しました。\n{exc}"))
            return
        self.results.put(meeting)

    def _poll(self) -> None:
        try:
            item = self.results.get_nowait()
        except queue.Empty:
            self.root.after(200, self._poll)
            return

        self.create_button.state(["!disabled"])
        if isinstance(item, Exception):
            self.status.configure(text=str(item))
            return

        if item.get("join_url") and item["join_url"] == self.previous_url:
            self.status.configure(text="同じ参加リンクが返されました。もう一度ボタンを押してください。")
            return

        self.meeting = item
        self.previous_url = item["join_url"]
        self.id_var.set(item["meeting_id"])
        self.password_var.set(item["password"])
        self.url_var.set(item["join_url"])
        self.result.pack(fill="x", pady=(8, 0))
        self.status.configure(
            text=f"新しい会議を作成しました。{item['topic']} / {item['start_time']}（{item['duration']}分）"
        )
        print("新しい参加リンクを作成しました。")
        print(invitation_text(item))
        print()

    def copy_value(self, value: str) -> None:
        if not value:
            return
        self._copy(value)
        self.status.configure(text="コピーしました。")

    def copy_all_fields(self) -> None:
        if not self.meeting:
            return
        self._copy(invitation_text(self.meeting))
        self.status.configure(text="ID・パスワード・参加リンクをコピーしました。")

    def _copy(self, value: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update()


def run() -> None:
    root = tk.Tk()
    MeetingWindow(root)
    root.mainloop()
