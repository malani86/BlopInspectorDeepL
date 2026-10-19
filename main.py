import sys

from PySide6.QtWidgets import QApplication

from main_window import MainWindow


WORKER_FLAG = "--batch-worker"


def main() -> int:
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
