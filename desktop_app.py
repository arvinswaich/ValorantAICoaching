import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from analyzer.video_analyzer import analyze_video


APP_NAME = "Valorant VOD Coach"
SUPPORTED_VIDEO_TYPES = (
    ("Video files", "*.mp4 *.mov *.mkv *.avi *.webm"),
    ("All files", "*.*"),
)


class Palette:
    WINDOW = "#0b0e14"
    SIDEBAR = "#111620"
    SURFACE = "#171d28"
    SURFACE_ALT = "#1d2532"
    BORDER = "#2c3544"
    TEXT = "#f4f7fb"
    MUTED = "#98a4b7"
    RED = "#ff4655"
    RED_DARK = "#d63848"
    TEAL = "#2bc4ad"
    AMBER = "#f1bd57"
    BLUE = "#6e9cff"
    GREEN = "#66d19e"


class ScrollableFrame(tk.Frame):
    def __init__(self, parent, background):
        super().__init__(parent, bg=background)
        self.canvas = tk.Canvas(
            self,
            bg=background,
            highlightthickness=0,
            borderwidth=0,
        )
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.content = tk.Frame(self.canvas, bg=background)
        self.window_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.content.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._sync_content_width)
        self.canvas.bind("<Enter>", self._enable_wheel)
        self.canvas.bind("<Leave>", self._disable_wheel)

    def _sync_scroll_region(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_content_width(self, event):
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _enable_wheel(self, _event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _disable_wheel(self, _event=None):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def reset_to_top(self):
        self.canvas.yview_moveto(0)


class ValorantCoachApp:
    def __init__(self, root):
        self.root = root
        self.selected_video = None
        self.current_report = None
        self.result_queue = queue.Queue()

        self.root.title(APP_NAME)
        self.root.geometry("1180x780")
        self.root.minsize(1000, 680)
        self.root.configure(bg=Palette.WINDOW)
        self._configure_styles()
        self._build_layout()
        self._show_empty_state()

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Coach.Horizontal.TProgressbar",
            troughcolor=Palette.SURFACE_ALT,
            background=Palette.RED,
            bordercolor=Palette.SURFACE_ALT,
            lightcolor=Palette.RED,
            darkcolor=Palette.RED,
            thickness=5,
        )
        style.configure(
            "Coach.Vertical.TScrollbar",
            troughcolor=Palette.WINDOW,
            background=Palette.BORDER,
            bordercolor=Palette.WINDOW,
            arrowcolor=Palette.MUTED,
        )

    def _build_layout(self):
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        self.sidebar = tk.Frame(self.root, bg=Palette.SIDEBAR, width=260)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        main = tk.Frame(self.root, bg=Palette.WINDOW)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self._build_sidebar()
        self._build_header(main)

        self.scroll_area = ScrollableFrame(main, Palette.WINDOW)
        self.scroll_area.grid(row=1, column=0, sticky="nsew", padx=(28, 20), pady=(0, 18))

        status_bar = tk.Frame(main, bg=Palette.SIDEBAR, height=34)
        status_bar.grid(row=2, column=0, sticky="ew")
        status_bar.grid_propagate(False)
        self.status_label = tk.Label(
            status_bar,
            text="Ready",
            bg=Palette.SIDEBAR,
            fg=Palette.MUTED,
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.status_label.pack(fill="both", expand=True, padx=18)

    def _build_sidebar(self):
        brand = tk.Frame(self.sidebar, bg=Palette.SIDEBAR)
        brand.pack(fill="x", padx=22, pady=(26, 32))

        mark = tk.Label(
            brand,
            text="VC",
            bg=Palette.RED,
            fg="white",
            width=3,
            height=1,
            font=("Segoe UI Semibold", 13),
        )
        mark.pack(side="left")

        brand_text = tk.Frame(brand, bg=Palette.SIDEBAR)
        brand_text.pack(side="left", padx=(11, 0))
        tk.Label(
            brand_text,
            text="VOD COACH",
            bg=Palette.SIDEBAR,
            fg=Palette.TEXT,
            font=("Segoe UI Semibold", 13),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            brand_text,
            text="DESKTOP",
            bg=Palette.SIDEBAR,
            fg=Palette.TEAL,
            font=("Segoe UI Semibold", 8),
            anchor="w",
        ).pack(anchor="w")

        tk.Label(
            self.sidebar,
            text="CURRENT VOD",
            bg=Palette.SIDEBAR,
            fg=Palette.MUTED,
            font=("Segoe UI Semibold", 9),
            anchor="w",
        ).pack(fill="x", padx=22)

        self.file_label = tk.Label(
            self.sidebar,
            text="No video selected",
            bg=Palette.SIDEBAR,
            fg=Palette.TEXT,
            font=("Segoe UI", 10),
            justify="left",
            wraplength=210,
            anchor="w",
        )
        self.file_label.pack(fill="x", padx=22, pady=(8, 17))

        self.select_button = self._button(
            self.sidebar,
            "Choose video",
            self.choose_video,
            Palette.SURFACE_ALT,
            Palette.TEXT,
            Palette.BORDER,
        )
        self.select_button.pack(fill="x", padx=22, ipady=5)

        self.analyze_button = self._button(
            self.sidebar,
            "Analyze VOD",
            self.start_analysis,
            Palette.RED,
            "white",
            Palette.RED_DARK,
        )
        self.analyze_button.pack(fill="x", padx=22, pady=(10, 0), ipady=6)
        self.analyze_button.configure(state="disabled")

        self.progress = ttk.Progressbar(
            self.sidebar,
            mode="indeterminate",
            style="Coach.Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x", padx=22, pady=(18, 0))

        privacy = tk.Frame(self.sidebar, bg=Palette.SIDEBAR)
        privacy.pack(side="bottom", fill="x", padx=22, pady=22)
        tk.Frame(privacy, bg=Palette.BORDER, height=1).pack(fill="x", pady=(0, 16))
        tk.Label(
            privacy,
            text="LOCAL ANALYSIS",
            bg=Palette.SIDEBAR,
            fg=Palette.GREEN,
            font=("Segoe UI Semibold", 8),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            privacy,
            text="Your VOD stays on this computer.",
            bg=Palette.SIDEBAR,
            fg=Palette.MUTED,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

    def _build_header(self, parent):
        header = tk.Frame(parent, bg=Palette.WINDOW)
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 20))
        header.grid_columnconfigure(0, weight=1)

        title_block = tk.Frame(header, bg=Palette.WINDOW)
        title_block.grid(row=0, column=0, sticky="w")
        tk.Label(
            title_block,
            text="SESSION REVIEW",
            bg=Palette.WINDOW,
            fg=Palette.RED,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w")
        self.header_title = tk.Label(
            title_block,
            text="Valorant VOD Coach",
            bg=Palette.WINDOW,
            fg=Palette.TEXT,
            font=("Segoe UI Semibold", 24),
        )
        self.header_title.pack(anchor="w")

        self.export_button = self._button(
            header,
            "Export report",
            self.export_report,
            Palette.SURFACE_ALT,
            Palette.TEXT,
            Palette.BORDER,
        )
        self.export_button.grid(row=0, column=1, sticky="e", padx=(16, 0), ipadx=8, ipady=4)
        self.export_button.configure(state="disabled")

    def _button(self, parent, text, command, background, foreground, active_background):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=background,
            fg=foreground,
            activebackground=active_background,
            activeforeground=foreground,
            disabledforeground="#667080",
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
            padx=14,
            pady=8,
        )

    def choose_video(self):
        selected = filedialog.askopenfilename(title="Choose a Valorant VOD", filetypes=SUPPORTED_VIDEO_TYPES)
        if not selected:
            return

        self.selected_video = Path(selected)
        self.file_label.configure(text=self.selected_video.name)
        self.analyze_button.configure(state="normal")
        self.status_label.configure(text=f"Selected: {self.selected_video.name}")
        self._show_selected_state()

    def start_analysis(self):
        if not self.selected_video or not self.selected_video.exists():
            messagebox.showerror(APP_NAME, "Choose a valid video file before analyzing.")
            return

        self._set_busy(True)
        self.status_label.configure(text=f"Analyzing {self.selected_video.name}...")
        self._show_loading_state()
        worker = threading.Thread(target=self._run_analysis, daemon=True)
        worker.start()
        self.root.after(120, self._poll_result)

    def _run_analysis(self):
        try:
            report = analyze_video(str(self.selected_video))
            self.result_queue.put(("success", report))
        except Exception as exc:
            self.result_queue.put(("error", str(exc)))

    def _poll_result(self):
        try:
            result_type, payload = self.result_queue.get_nowait()
        except queue.Empty:
            self.root.after(120, self._poll_result)
            return

        self._set_busy(False)
        if result_type == "error" or payload.get("error"):
            error_message = payload if result_type == "error" else payload.get("error")
            if result_type != "error" and payload.get("error_code") == "not_valorant":
                self.status_label.configure(text="Clip rejected: Valorant HUD not detected")
                self._show_rejected_state(payload)
            else:
                self.status_label.configure(text="Analysis failed")
                messagebox.showerror(APP_NAME, error_message)
                self._show_selected_state()
            return

        self.current_report = payload
        self.export_button.configure(state="normal")
        self.status_label.configure(text=f"Review ready: {self.selected_video.name}")
        self._render_report(payload)

    def _set_busy(self, busy):
        if busy:
            self.progress.start(10)
            self.select_button.configure(state="disabled")
            self.analyze_button.configure(state="disabled")
            self.export_button.configure(state="disabled")
        else:
            self.progress.stop()
            self.select_button.configure(state="normal")
            self.analyze_button.configure(state="normal" if self.selected_video else "disabled")

    def _clear_content(self):
        for child in self.scroll_area.content.winfo_children():
            child.destroy()
        self.scroll_area.reset_to_top()

    def _show_empty_state(self):
        self._clear_content()
        panel = tk.Frame(
            self.scroll_area.content,
            bg=Palette.SURFACE,
            highlightbackground=Palette.BORDER,
            highlightthickness=1,
            height=360,
        )
        panel.pack(fill="both", expand=True, pady=(4, 0))
        panel.pack_propagate(False)

        center = tk.Frame(panel, bg=Palette.SURFACE)
        center.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(
            center,
            text="NO VOD SELECTED",
            bg=Palette.SURFACE,
            fg=Palette.MUTED,
            font=("Segoe UI Semibold", 10),
        ).pack()
        tk.Label(
            center,
            text="Ready for your next review",
            bg=Palette.SURFACE,
            fg=Palette.TEXT,
            font=("Segoe UI Semibold", 20),
        ).pack(pady=(8, 18))
        button = self._button(center, "Choose video", self.choose_video, Palette.RED, "white", Palette.RED_DARK)
        button.pack(ipadx=10, ipady=4)

    def _show_selected_state(self):
        self._clear_content()
        panel = tk.Frame(
            self.scroll_area.content,
            bg=Palette.SURFACE,
            highlightbackground=Palette.BORDER,
            highlightthickness=1,
        )
        panel.pack(fill="x", pady=(4, 0))

        tk.Label(
            panel,
            text="VOD READY",
            bg=Palette.SURFACE,
            fg=Palette.TEAL,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", padx=28, pady=(28, 7))
        tk.Label(
            panel,
            text=self.selected_video.name,
            bg=Palette.SURFACE,
            fg=Palette.TEXT,
            font=("Segoe UI Semibold", 19),
            wraplength=700,
            justify="left",
        ).pack(anchor="w", padx=28)
        tk.Label(
            panel,
            text=self._file_metadata(self.selected_video),
            bg=Palette.SURFACE,
            fg=Palette.MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=28, pady=(7, 28))

    def _show_loading_state(self):
        self._clear_content()
        panel = tk.Frame(self.scroll_area.content, bg=Palette.SURFACE, height=300)
        panel.pack(fill="both", expand=True, pady=(4, 0))
        panel.pack_propagate(False)
        center = tk.Frame(panel, bg=Palette.SURFACE)
        center.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(
            center,
            text="ANALYZING",
            bg=Palette.SURFACE,
            fg=Palette.RED,
            font=("Segoe UI Semibold", 10),
        ).pack()
        tk.Label(
            center,
            text=self.selected_video.name,
            bg=Palette.SURFACE,
            fg=Palette.TEXT,
            font=("Segoe UI Semibold", 19),
            wraplength=620,
        ).pack(pady=(8, 7))
        tk.Label(
            center,
            text="Verifying Valorant HUD, contacts, and crosshair placement...",
            bg=Palette.SURFACE,
            fg=Palette.MUTED,
            font=("Segoe UI", 10),
        ).pack()

    def _show_rejected_state(self, result):
        self._clear_content()
        panel = tk.Frame(
            self.scroll_area.content,
            bg=Palette.SURFACE,
            highlightbackground=Palette.RED,
            highlightthickness=1,
        )
        panel.pack(fill="x", pady=(4, 0))
        tk.Label(
            panel,
            text="CLIP REJECTED",
            bg=Palette.SURFACE,
            fg=Palette.RED,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", padx=28, pady=(28, 8))
        tk.Label(
            panel,
            text="Supported Valorant gameplay was not detected",
            bg=Palette.SURFACE,
            fg=Palette.TEXT,
            font=("Segoe UI Semibold", 19),
            wraplength=700,
            justify="left",
        ).pack(anchor="w", padx=28)
        tk.Label(
            panel,
            text=result.get("error"),
            bg=Palette.SURFACE,
            fg=Palette.MUTED,
            font=("Segoe UI", 10),
            wraplength=720,
            justify="left",
        ).pack(anchor="w", padx=28, pady=(9, 6))
        confidence = result.get("validation", {}).get("confidence", 0)
        tk.Label(
            panel,
            text=f"Valorant confidence: {round(confidence)}%",
            bg=Palette.SURFACE,
            fg=Palette.AMBER,
            font=("Segoe UI Semibold", 10),
        ).pack(anchor="w", padx=28, pady=(0, 28))

    def _render_report(self, report):
        self._clear_content()
        self.header_title.configure(text=report.get("video_name") or "Session Review")

        overview = tk.Frame(self.scroll_area.content, bg=Palette.WINDOW)
        overview.pack(fill="x", pady=(2, 20))
        overview.grid_columnconfigure(1, weight=1)

        score_frame = tk.Frame(
            overview,
            bg=Palette.SURFACE,
            width=180,
            height=164,
            highlightbackground=Palette.BORDER,
            highlightthickness=1,
        )
        score_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        score_frame.grid_propagate(False)
        self._draw_score(score_frame, report.get("overall_score", 0))

        summary = tk.Frame(
            overview,
            bg=Palette.SURFACE,
            highlightbackground=Palette.BORDER,
            highlightthickness=1,
        )
        summary.grid(row=0, column=1, sticky="nsew")
        tk.Label(
            summary,
            text="REVIEW SUMMARY",
            bg=Palette.SURFACE,
            fg=Palette.RED,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", padx=24, pady=(22, 7))
        tk.Label(
            summary,
            text=self._summary_line(report),
            bg=Palette.SURFACE,
            fg=Palette.TEXT,
            font=("Segoe UI Semibold", 16),
            wraplength=610,
            justify="left",
        ).pack(anchor="w", padx=24)
        metadata = (
            f"{self._format_duration(report.get('duration_seconds', 0))}  |  "
            f"{report.get('sampled_frames', 0)} samples  |  {report.get('fps', 0)} FPS  |  "
            f"Valorant {round(report.get('valorant_validation', {}).get('confidence', 0))}%"
        )
        tk.Label(
            summary,
            text=metadata,
            bg=Palette.SURFACE,
            fg=Palette.MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=24, pady=(10, 22))

        tk.Label(
            self.scroll_area.content,
            text="CORE METRICS",
            bg=Palette.WINDOW,
            fg=Palette.MUTED,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", pady=(0, 9))

        metrics_frame = tk.Frame(self.scroll_area.content, bg=Palette.WINDOW)
        metrics_frame.pack(fill="x", pady=(0, 21))
        metrics = [
            ("Placement", report["metrics"].get("crosshair_placement_score", 0), Palette.RED),
            ("Head level", report["metrics"].get("head_level_score", 0), Palette.TEAL),
            ("Angle readiness", report["metrics"].get("angle_readiness_score", 0), Palette.AMBER),
            ("Stability", report["metrics"].get("crosshair_stability_score", 0), Palette.BLUE),
        ]
        if report["metrics"].get("contact_aim_score") is not None:
            metrics.append(("Contact aim", report["metrics"]["contact_aim_score"], Palette.GREEN))
        for column, metric in enumerate(metrics):
            metrics_frame.grid_columnconfigure(column, weight=1, uniform="metric")
            self._metric_card(metrics_frame, column, column == len(metrics) - 1, *metric)

        self._combat_summary(report.get("combat_summary", {}))
        self._section("WHAT LOOKED GOOD", report.get("strengths", []), Palette.GREEN)
        self._section("PRIORITY ISSUES", report.get("mistakes", []), Palette.RED)
        self._section("COACHING FIXES", report.get("fixes", []), Palette.TEAL)
        self._moment_section("PLACEMENT TIMELINE", report.get("specific_moments", []))
        self._moment_section("OPPONENT CONTACTS", report.get("combat_moments", []))
        self._section("PRACTICE PLAN", report.get("focus_drills", []), Palette.AMBER)
        self._section("ANALYSIS CONFIDENCE", [report.get("analysis_note")], Palette.MUTED)

    def _draw_score(self, parent, score):
        canvas = tk.Canvas(parent, width=150, height=122, bg=Palette.SURFACE, highlightthickness=0)
        canvas.pack(pady=(13, 0))
        canvas.create_arc(27, 8, 123, 104, start=90, extent=-359, style="arc", width=9, outline=Palette.BORDER)
        extent = -359 * max(0, min(100, score)) / 100
        canvas.create_arc(27, 8, 123, 104, start=90, extent=extent, style="arc", width=9, outline=self._score_color(score))
        canvas.create_text(75, 52, text=str(round(score)), fill=Palette.TEXT, font=("Segoe UI Semibold", 27))
        canvas.create_text(75, 77, text="/ 100", fill=Palette.MUTED, font=("Segoe UI", 9))
        tk.Label(
            parent,
            text="OVERALL SCORE",
            bg=Palette.SURFACE,
            fg=Palette.MUTED,
            font=("Segoe UI Semibold", 8),
        ).pack()

    def _metric_card(self, parent, column, is_last, label, value, color):
        card = tk.Frame(
            parent,
            bg=Palette.SURFACE,
            highlightbackground=Palette.BORDER,
            highlightthickness=1,
        )
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 5, 0 if is_last else 5))
        tk.Label(
            card,
            text=label.upper(),
            bg=Palette.SURFACE,
            fg=Palette.MUTED,
            font=("Segoe UI Semibold", 8),
        ).pack(anchor="w", padx=16, pady=(15, 3))
        tk.Label(
            card,
            text=f"{round(value)}",
            bg=Palette.SURFACE,
            fg=Palette.TEXT,
            font=("Segoe UI Semibold", 22),
        ).pack(anchor="w", padx=16)
        bar = tk.Canvas(card, height=5, bg=Palette.SURFACE, highlightthickness=0)
        bar.pack(fill="x", padx=16, pady=(8, 16))
        bar.bind("<Configure>", lambda event, c=bar, v=value, accent=color: self._draw_metric_bar(c, event.width, v, accent))

    @staticmethod
    def _draw_metric_bar(canvas, width, value, color):
        canvas.delete("all")
        canvas.create_rectangle(0, 0, width, 5, fill=Palette.BORDER, outline="")
        canvas.create_rectangle(0, 0, width * max(0, min(100, value)) / 100, 5, fill=color, outline="")

    def _combat_summary(self, summary):
        frame = tk.Frame(self.scroll_area.content, bg=Palette.WINDOW)
        frame.pack(fill="x", pady=(0, 21))
        values = [
            ("Opponent contacts", summary.get("opponent_contact_count", 0), Palette.BLUE),
            ("Estimated kills", summary.get("estimated_kill_count", 0), Palette.GREEN),
            ("Estimated deaths", summary.get("estimated_death_count", 0), Palette.RED),
            (
                "Average head offset",
                f"{round(summary['average_crosshair_to_head_pixels'])} px"
                if summary.get("average_crosshair_to_head_pixels") is not None
                else "No contact",
                Palette.AMBER,
            ),
        ]
        for column, (label, value, accent) in enumerate(values):
            frame.grid_columnconfigure(column, weight=1, uniform="combat")
            card = tk.Frame(
                frame,
                bg=Palette.SURFACE_ALT,
                highlightbackground=Palette.BORDER,
                highlightthickness=1,
            )
            card.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 5, 0 if column == len(values) - 1 else 5),
            )
            tk.Label(
                card,
                text=label.upper(),
                bg=Palette.SURFACE_ALT,
                fg=Palette.MUTED,
                font=("Segoe UI Semibold", 8),
            ).pack(anchor="w", padx=15, pady=(13, 3))
            tk.Label(
                card,
                text=str(value),
                bg=Palette.SURFACE_ALT,
                fg=accent,
                font=("Segoe UI Semibold", 17),
            ).pack(anchor="w", padx=15, pady=(0, 13))

    def _section(self, title, items, accent):
        if not items:
            return
        frame = tk.Frame(
            self.scroll_area.content,
            bg=Palette.SURFACE,
            highlightbackground=Palette.BORDER,
            highlightthickness=1,
        )
        frame.pack(fill="x", pady=(0, 14))
        tk.Frame(frame, bg=accent, width=4).pack(side="left", fill="y")
        body = tk.Frame(frame, bg=Palette.SURFACE)
        body.pack(side="left", fill="both", expand=True, padx=20, pady=18)
        tk.Label(
            body,
            text=title,
            bg=Palette.SURFACE,
            fg=accent,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", pady=(0, 9))
        for item in items:
            row = tk.Frame(body, bg=Palette.SURFACE)
            row.pack(fill="x", pady=3)
            tk.Label(row, text="-", bg=Palette.SURFACE, fg=accent, font=("Segoe UI Semibold", 11)).pack(side="left", anchor="n")
            tk.Label(
                row,
                text=item,
                bg=Palette.SURFACE,
                fg=Palette.TEXT,
                font=("Segoe UI", 10),
                justify="left",
                wraplength=760,
            ).pack(side="left", fill="x", expand=True, padx=(8, 0), anchor="w")

    def _moment_section(self, title, moments):
        if not moments:
            return
        frame = tk.Frame(
            self.scroll_area.content,
            bg=Palette.SURFACE,
            highlightbackground=Palette.BORDER,
            highlightthickness=1,
        )
        frame.pack(fill="x", pady=(0, 14))
        tk.Label(
            frame,
            text=title,
            bg=Palette.SURFACE,
            fg=Palette.BLUE,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", padx=22, pady=(18, 10))

        for index, moment in enumerate(moments):
            row = tk.Frame(frame, bg=Palette.SURFACE_ALT)
            row.pack(fill="x", padx=22, pady=(0, 8 if index < len(moments) - 1 else 18))
            timestamp = tk.Label(
                row,
                text=self._format_timestamp(moment.get("timestamp_seconds", 0)),
                bg=Palette.BLUE,
                fg="white",
                font=("Segoe UI Semibold", 9),
                width=7,
            )
            timestamp.pack(side="left", fill="y")
            text_frame = tk.Frame(row, bg=Palette.SURFACE_ALT)
            text_frame.pack(side="left", fill="both", expand=True, padx=14, pady=11)
            tk.Label(
                text_frame,
                text=moment.get("issue", "Placement issue"),
                bg=Palette.SURFACE_ALT,
                fg=Palette.TEXT,
                font=("Segoe UI Semibold", 10),
            ).pack(anchor="w")
            detail = f"{moment.get('detail', '')} {moment.get('tip', '')}".strip()
            tk.Label(
                text_frame,
                text=detail,
                bg=Palette.SURFACE_ALT,
                fg=Palette.MUTED,
                font=("Segoe UI", 9),
                justify="left",
                wraplength=680,
            ).pack(anchor="w", pady=(3, 0))

    def export_report(self):
        if not self.current_report:
            return
        default_name = f"{Path(self.current_report.get('video_name', 'vod')).stem}_review.txt"
        output_path = filedialog.asksaveasfilename(
            title="Export coaching report",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=(("Text report", "*.txt"),),
        )
        if not output_path:
            return
        Path(output_path).write_text(self._report_text(self.current_report), encoding="utf-8")
        self.status_label.configure(text=f"Report exported: {Path(output_path).name}")

    @staticmethod
    def _report_text(report):
        lines = [
            APP_NAME,
            "=" * len(APP_NAME),
            f"VOD: {report.get('video_name')}",
            f"Overall score: {report.get('overall_score')}/100",
            f"Duration: {ValorantCoachApp._format_duration(report.get('duration_seconds', 0))}",
            "",
            "METRICS",
        ]
        labels = {
            "crosshair_placement_score": "Crosshair placement",
            "head_level_score": "Head level",
            "angle_readiness_score": "Angle readiness",
            "crosshair_stability_score": "Crosshair stability",
            "contact_aim_score": "Contact aim",
        }
        for key, label in labels.items():
            value = report.get("metrics", {}).get(key)
            if value is not None:
                lines.append(f"- {label}: {value}/100")

        combat = report.get("combat_summary", {})
        lines.extend((
            "",
            "COMBAT EVIDENCE",
            f"- Opponent contacts: {combat.get('opponent_contact_count', 0)}",
            f"- Estimated kills: {combat.get('estimated_kill_count', 0)}",
            f"- Estimated deaths: {combat.get('estimated_death_count', 0)}",
            f"- Average estimated head offset: {combat.get('average_crosshair_to_head_pixels')} px",
        ))

        sections = (
            ("WHAT LOOKED GOOD", report.get("strengths", [])),
            ("PRIORITY ISSUES", report.get("mistakes", [])),
            ("COACHING FIXES", report.get("fixes", [])),
            ("PRACTICE PLAN", report.get("focus_drills", [])),
        )
        for title, items in sections:
            lines.extend(("", title))
            lines.extend(f"- {item}" for item in items)

        moments = report.get("specific_moments", [])
        if moments:
            lines.extend(("", "REVIEW TIMELINE"))
            for moment in moments:
                timestamp = ValorantCoachApp._format_timestamp(moment.get("timestamp_seconds", 0))
                lines.append(f"- {timestamp} | {moment.get('issue')}: {moment.get('detail')} {moment.get('tip')}")
        combat_moments = report.get("combat_moments", [])
        if combat_moments:
            lines.extend(("", "OPPONENT CONTACTS"))
            for moment in combat_moments:
                timestamp = ValorantCoachApp._format_timestamp(moment.get("timestamp_seconds", 0))
                lines.append(f"- {timestamp} | {moment.get('issue')}: {moment.get('detail')} {moment.get('tip')}")
        lines.extend(("", "ANALYSIS NOTE", report.get("analysis_note", "")))
        return "\n".join(lines) + "\n"

    @staticmethod
    def _summary_line(report):
        score = report.get("overall_score", 0)
        if score >= 80:
            return "Strong placement foundation with only small refinements needed."
        if score >= 60:
            return "Solid baseline, with a few repeatable habits to tighten up."
        if score >= 40:
            return "Inconsistent placement is adding extra work before your first shot."
        return "Crosshair preparation is the clearest priority for this session."

    @staticmethod
    def _score_color(score):
        if score >= 75:
            return Palette.GREEN
        if score >= 50:
            return Palette.AMBER
        return Palette.RED

    @staticmethod
    def _format_duration(seconds):
        seconds = int(round(seconds or 0))
        minutes, remainder = divmod(seconds, 60)
        return f"{minutes}:{remainder:02d}"

    @staticmethod
    def _format_timestamp(seconds):
        seconds = int(round(seconds or 0))
        minutes, remainder = divmod(seconds, 60)
        return f"{minutes}:{remainder:02d}"

    @staticmethod
    def _file_metadata(path):
        size_mb = path.stat().st_size / (1024 * 1024)
        return f"{path.suffix.upper().lstrip('.')}  |  {size_mb:.1f} MB"


def main():
    root = tk.Tk()
    ValorantCoachApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
