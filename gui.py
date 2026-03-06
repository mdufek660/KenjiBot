"""
KenjiBot Control Panel
A simple GUI for the streamer to start/stop the bot and toggle settings.
"""
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext
import asyncio
import logging
import queue

import config


# ── Custom log handler that pushes records to a queue for the GUI ──
class QueueLogHandler(logging.Handler):
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put(msg)
        except Exception:
            pass


class KenjiBotGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("KenjiBot Control Panel")
        self.root.geometry("700x620")
        self.root.resizable(False, False)
        self.root.configure(bg="#1a1a2e")

        self.bot = None
        self.bot_thread = None
        self.bot_running = False
        self.log_queue = queue.Queue()

        self._build_ui()
        self._setup_logging()
        self._poll_log_queue()
        self._tick_countdowns()

    # ── UI ──────────────────────────────────────────────────────────
    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#1a1a2e")
        style.configure("TLabel", background="#1a1a2e", foreground="#e0e0e0",
                         font=("Segoe UI", 10))
        style.configure("Header.TLabel", background="#1a1a2e", foreground="#ffcc00",
                         font=("Segoe UI", 16, "bold"))
        style.configure("TCheckbutton", background="#1a1a2e", foreground="#e0e0e0",
                         font=("Segoe UI", 10))
        style.map("TCheckbutton",
                  background=[("active", "#1a1a2e")],
                  foreground=[("active", "#ffcc00")])

        # ── Header ──
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill="x", padx=15, pady=(15, 5))
        ttk.Label(header_frame, text="🤓 KenjiBot Control Panel",
                  style="Header.TLabel").pack(side="left")

        # ── Status indicator ──
        self.status_var = tk.StringVar(value="⬤ Stopped")
        self.status_label = ttk.Label(header_frame, textvariable=self.status_var,
                                       foreground="#ff4444", font=("Segoe UI", 10, "bold"))
        self.status_label.pack(side="right")

        # ── Toggles frame ──
        toggles_frame = ttk.Frame(self.root)
        toggles_frame.pack(fill="x", padx=15, pady=10)

        # TTS toggle
        self.tts_var = tk.BooleanVar(value=config.TTS_ENABLED)
        tts_check = ttk.Checkbutton(
            toggles_frame, text="🔊 TTS Enabled",
            variable=self.tts_var, command=self._toggle_tts
        )
        tts_check.grid(row=0, column=0, sticky="w", padx=10, pady=3)

        # Stream listener toggle
        self.listen_var = tk.BooleanVar(value=config.STREAM_LISTEN_ENABLED)
        listen_check = ttk.Checkbutton(
            toggles_frame, text="🎧 Stream Listener Enabled",
            variable=self.listen_var, command=self._toggle_listener
        )
        listen_check.grid(row=0, column=1, sticky="w", padx=10, pady=3)

        # Chat replies toggle (debug)
        self.chat_var = tk.BooleanVar(value=True)
        chat_check = ttk.Checkbutton(
            toggles_frame, text="💬 Chat Replies (Debug)",
            variable=self.chat_var, command=self._toggle_chat
        )
        chat_check.grid(row=1, column=0, sticky="w", padx=10, pady=3)

        # ── Cooldown inputs ──
        cooldown_frame = ttk.Frame(self.root)
        cooldown_frame.pack(fill="x", padx=15, pady=5)

        # Reply cooldown
        ttk.Label(cooldown_frame, text="⏱ Reply Cooldown (seconds):").grid(
            row=0, column=0, sticky="w", padx=10, pady=3)
        self.cooldown_var = tk.IntVar(value=config.KENJI_COOLDOWN)
        cooldown_spin = ttk.Spinbox(
            cooldown_frame, from_=10, to=3600, increment=10,
            textvariable=self.cooldown_var, width=8,
            command=self._update_cooldown
        )
        cooldown_spin.grid(row=0, column=1, sticky="w", padx=5, pady=3)
        cooldown_spin.bind("<Return>", self._update_cooldown)
        cooldown_spin.bind("<FocusOut>", self._update_cooldown)
        self.cooldown_label = ttk.Label(cooldown_frame, text=self._format_time(config.KENJI_COOLDOWN))
        self.cooldown_label.grid(row=0, column=2, sticky="w", padx=5, pady=3)

        # Listen interval
        ttk.Label(cooldown_frame, text="🎧 Listen Interval (seconds):").grid(
            row=1, column=0, sticky="w", padx=10, pady=3)
        self.listen_interval_var = tk.IntVar(value=config.LISTEN_INTERVAL)
        listen_spin = ttk.Spinbox(
            cooldown_frame, from_=30, to=3600, increment=10,
            textvariable=self.listen_interval_var, width=8,
            command=self._update_listen_interval
        )
        listen_spin.grid(row=1, column=1, sticky="w", padx=5, pady=3)
        listen_spin.bind("<Return>", self._update_listen_interval)
        listen_spin.bind("<FocusOut>", self._update_listen_interval)
        self.listen_interval_label = ttk.Label(cooldown_frame, text=self._format_time(config.LISTEN_INTERVAL))
        self.listen_interval_label.grid(row=1, column=2, sticky="w", padx=5, pady=3)

        # Listen duration
        ttk.Label(cooldown_frame, text="⏺ Listen Duration (seconds):").grid(
            row=2, column=0, sticky="w", padx=10, pady=3)
        self.listen_duration_var = tk.IntVar(value=config.LISTEN_DURATION)
        duration_spin = ttk.Spinbox(
            cooldown_frame, from_=5, to=60, increment=5,
            textvariable=self.listen_duration_var, width=8,
            command=self._update_listen_duration
        )
        duration_spin.grid(row=2, column=1, sticky="w", padx=5, pady=3)
        duration_spin.bind("<Return>", self._update_listen_duration)
        duration_spin.bind("<FocusOut>", self._update_listen_duration)

        # ── Countdown timers ──
        countdown_frame = ttk.Frame(self.root)
        countdown_frame.pack(fill="x", padx=15, pady=5)

        ttk.Label(countdown_frame, text="⏱ Reply cooldown:").grid(
            row=0, column=0, sticky="w", padx=10, pady=2)
        self.reply_countdown_var = tk.StringVar(value="Ready")
        self.reply_countdown_label = ttk.Label(
            countdown_frame, textvariable=self.reply_countdown_var,
            foreground="#2ecc71", font=("Segoe UI", 10, "bold"))
        self.reply_countdown_label.grid(row=0, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(countdown_frame, text="🎧 Next listen in:").grid(
            row=1, column=0, sticky="w", padx=10, pady=2)
        self.listen_countdown_var = tk.StringVar(value="—")
        self.listen_countdown_label = ttk.Label(
            countdown_frame, textvariable=self.listen_countdown_var,
            foreground="#e0e0e0", font=("Segoe UI", 10, "bold"))
        self.listen_countdown_label.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        # ── Start / Stop buttons ──
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill="x", padx=15, pady=10)

        self.start_btn = tk.Button(
            button_frame, text="▶  Start Bot", font=("Segoe UI", 11, "bold"),
            bg="#2ecc71", fg="white", activebackground="#27ae60",
            relief="flat", padx=20, pady=8, command=self._start_bot
        )
        self.start_btn.pack(side="left", padx=10)

        self.stop_btn = tk.Button(
            button_frame, text="⏹  Stop Bot", font=("Segoe UI", 11, "bold"),
            bg="#e74c3c", fg="white", activebackground="#c0392b",
            relief="flat", padx=20, pady=8, command=self._stop_bot,
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=10)

        # ── Log output ──
        log_frame = ttk.Frame(self.root)
        log_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        ttk.Label(log_frame, text="📋 Log:").pack(anchor="w", padx=5)
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=12, bg="#0d1117", fg="#c9d1d9",
            font=("Consolas", 9), insertbackground="#c9d1d9",
            state="disabled", wrap="word"
        )
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

    # ── Logging ─────────────────────────────────────────────────────
    def _setup_logging(self):
        handler = QueueLogHandler(self.log_queue)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s  %(name)-18s  %(levelname)-8s  %(message)s",
            datefmt="%H:%M:%S"
        ))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

    def _poll_log_queue(self):
        """Pull log messages from the queue and display them in the GUI."""
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(100, self._poll_log_queue)

    def _tick_countdowns(self):
        """Update countdown displays every second."""
        if self.bot_running and self.bot:
            try:
                now = time.time()

                # Reply cooldown
                last_reply = getattr(self.bot, '_last_reply_time', 0.0)
                if last_reply == 0.0:
                    self.reply_countdown_var.set("✅ Ready")
                    self.reply_countdown_label.configure(foreground="#2ecc71")
                else:
                    reply_remaining = config.KENJI_COOLDOWN - (now - last_reply)
                    if reply_remaining <= 0:
                        self.reply_countdown_var.set("✅ Ready")
                        self.reply_countdown_label.configure(foreground="#2ecc71")
                    else:
                        mins, secs = divmod(int(reply_remaining), 60)
                        self.reply_countdown_var.set(f"{mins}m {secs}s")
                        self.reply_countdown_label.configure(foreground="#ffcc00")

                # Listen countdown
                if config.STREAM_LISTEN_ENABLED:
                    last_listen = getattr(self.bot, '_last_listen_time', 0.0)
                    bot_start = getattr(self.bot, '_bot_start_time', 0.0)
                    # Use bot start time as baseline if we haven't listened yet
                    baseline = last_listen if last_listen > 0.0 else bot_start
                    if baseline == 0.0:
                        self.listen_countdown_var.set("⏳ Starting...")
                        self.listen_countdown_label.configure(foreground="#666666")
                    else:
                        listen_remaining = config.LISTEN_INTERVAL - (now - baseline)
                        if listen_remaining <= 0:
                            self.listen_countdown_var.set("🔴 Listening soon...")
                            self.listen_countdown_label.configure(foreground="#e74c3c")
                        else:
                            mins, secs = divmod(int(listen_remaining), 60)
                            self.listen_countdown_var.set(f"{mins}m {secs}s")
                            self.listen_countdown_label.configure(foreground="#e0e0e0")
                else:
                    self.listen_countdown_var.set("Disabled")
                    self.listen_countdown_label.configure(foreground="#666666")
            except Exception:
                pass  # Bot may not be fully initialized yet
        else:
            self.reply_countdown_var.set("—")
            self.reply_countdown_label.configure(foreground="#666666")
            self.listen_countdown_var.set("—")
            self.listen_countdown_label.configure(foreground="#666666")

        self.root.after(1000, self._tick_countdowns)

    # ── Toggle callbacks ────────────────────────────────────────────
    def _toggle_tts(self):
        config.TTS_ENABLED = self.tts_var.get()
        state = "ON" if config.TTS_ENABLED else "OFF"
        logging.getLogger("kenji.gui").info("TTS toggled %s", state)

    def _toggle_listener(self):
        config.STREAM_LISTEN_ENABLED = self.listen_var.get()
        state = "ON" if config.STREAM_LISTEN_ENABLED else "OFF"
        logging.getLogger("kenji.gui").info("Stream listener toggled %s", state)

    def _toggle_chat(self):
        config.CHAT_REPLIES_ENABLED = self.chat_var.get()
        state = "ON" if config.CHAT_REPLIES_ENABLED else "OFF"
        logging.getLogger("kenji.gui").info("Chat replies toggled %s", state)

    @staticmethod
    def _format_time(secs):
        mins, s = divmod(int(secs), 60)
        return f"({mins}m {s}s)"

    def _update_cooldown(self, _=None):
        config.KENJI_COOLDOWN = self.cooldown_var.get()
        self.cooldown_label.configure(text=self._format_time(config.KENJI_COOLDOWN))
        logging.getLogger("kenji.gui").info("Reply cooldown set to %ds", config.KENJI_COOLDOWN)

    def _update_listen_interval(self, _=None):
        config.LISTEN_INTERVAL = self.listen_interval_var.get()
        self.listen_interval_label.configure(text=self._format_time(config.LISTEN_INTERVAL))
        logging.getLogger("kenji.gui").info("Listen interval set to %ds", config.LISTEN_INTERVAL)

    def _update_listen_duration(self, _=None):
        config.LISTEN_DURATION = self.listen_duration_var.get()
        logging.getLogger("kenji.gui").info("Listen duration set to %ds", config.LISTEN_DURATION)

    # ── Bot start / stop ────────────────────────────────────────────
    def _start_bot(self):
        if self.bot_running:
            return

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_var.set("⬤ Running")
        self.status_label.configure(foreground="#2ecc71")
        self.bot_running = True

        self.bot_thread = threading.Thread(target=self._run_bot_thread, daemon=True)
        self.bot_thread.start()

    def _run_bot_thread(self):
        """Run the bot in a background thread with its own event loop."""
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            from bot import KenjiBot
            self.bot = KenjiBot()
            self.bot.run()
        except Exception as e:
            logging.getLogger("kenji.gui").error("Bot crashed: %s", e)
        finally:
            self.bot_running = False
            # Update UI from the main thread
            self.root.after(0, self._on_bot_stopped)

    def _stop_bot(self):
        if not self.bot_running:
            return

        logging.getLogger("kenji.gui").info("Stopping bot...")
        if self.bot:
            try:
                loop = self.bot.loop
                if loop and loop.is_running():
                    # Schedule a proper async close so twitchio can clean up
                    async def _shutdown():
                        await self.bot.close()
                        loop.stop()
                    loop.call_soon_threadsafe(asyncio.ensure_future, _shutdown())
            except Exception:
                pass

    def _on_bot_stopped(self):
        self.bot_running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_var.set("⬤ Stopped")
        self.status_label.configure(foreground="#ff4444")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = KenjiBotGUI()
    app.run()
