import logging
import logging.handlers
import signal
import os
import sys
import threading
from multiprocessing import Queue

CURRENT_LEVEL = logging.DEBUG  # Default level (global to this process)
wait_event = threading.Event()  # Used to block the main thread

def toggle_log_level(signum, frame):
    global CURRENT_LEVEL
    CURRENT_LEVEL = logging.DEBUG if CURRENT_LEVEL == logging.INFO else logging.INFO
    logging.getLogger().setLevel(CURRENT_LEVEL)
    print(f"[Log Listener] Switched level to: {logging.getLevelName(CURRENT_LEVEL)}")

def logproc(log_queue: Queue):
    # Setup root logger with a stream handler
    root_logger = logging.getLogger()
    root_logger.setLevel(CURRENT_LEVEL)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s] %(message)s')
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Register signal handler
    if os.name == 'nt':
        signal.signal(signal.SIGBREAK, toggle_log_level)
        print(f"[Log Listener] PID: {os.getpid()} (press Ctrl+Break to toggle level)")
    else:
        signal.signal(signal.SIGUSR1, toggle_log_level)
        print(f"[Log Listener] PID: {os.getpid()} (send SIGUSR1 to toggle level)")

    # Start listening to the logging queue
    listener = logging.handlers.QueueListener(log_queue, handler)
    listener.start()

    try:
        print("[Log Listener] Waiting for signal...")
        wait_event.wait()  # Block until program ends
    except KeyboardInterrupt:
        print("[Log Listener] KeyboardInterrupt received.")
    finally:
        listener.stop()
