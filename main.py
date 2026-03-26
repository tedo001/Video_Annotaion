"""
Video Annotation Tool — Entry Point
Run: python main.py
"""
import tkinter as tk
from ui.main_window import MainWindow


def main():
    root = tk.Tk()
    root.title("Video Annotation Tool  |  YOLOv8")
    root.geometry("1280x800")
    root.minsize(1024, 700)

    app = MainWindow(root)
    app.pack(fill=tk.BOTH, expand=True)

    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()