# Add at the top with other imports
from utils.logger   import get_logger
from ui.log_viewer  import LogViewer

log = get_logger("ui.MainWindow")

# ── Inside _build_toolbar(), add one more button after the others:
btn("📋  Logs", self._show_logs)

# ── Add these two methods inside MainWindow:

def _show_logs(self):
    """Open / bring-to-front the log viewer window."""
    if not hasattr(self, "_log_viewer") or not self._log_viewer.winfo_exists():
        self._log_viewer = LogViewer(self.master)
    else:
        self._log_viewer.deiconify()
        self._log_viewer.lift()

# ── Patch _set_status to also log:
def _set_status(self, msg: str):
    self.status_var.set(msg)
    log.info(f"[STATUS] {msg}")
    self.update_idletasks()