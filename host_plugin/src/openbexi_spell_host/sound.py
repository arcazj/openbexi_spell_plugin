"""Native prompt timeout notification in the host's audio/terminal session."""
import sys


def reminder():
    if sys.platform == 'win32':
        import winsound
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            return
        except RuntimeError:
            # An unavailable audio device must not terminate a waiting procedure.
            pass
    sys.stderr.write('\a')
    sys.stderr.flush()
