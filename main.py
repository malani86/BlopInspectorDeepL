import sys
import os

from PySide6.QtWidgets import QApplication

from main_window import MainWindow


WORKER_FLAG = "--batch-worker"


def main() -> int:
    # Windowed PyInstaller executables can start with no stdout/stderr.
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if stream is None:
            setattr(sys, stream_name, open(os.devnull, "w", encoding="utf-8"))
        elif hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) > 1 and sys.argv[1] == WORKER_FLAG:
        from quantify_droplets_batch import main as batch_main

        sys.argv = [sys.argv[0], *sys.argv[2:]]
        batch_main()
        return 0

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
