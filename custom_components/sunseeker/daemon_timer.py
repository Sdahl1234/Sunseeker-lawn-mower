"""Timer that never blocks interpreter shutdown."""

from threading import Timer


class DaemonTimer(Timer):
    """Timer running as a daemon thread."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the timer as a daemon thread."""
        super().__init__(*args, **kwargs)
        self.daemon = True
