import multiprocessing as mp
import logging

def logsetup(log_queue: mp.Queue, name: str):
    logger = logging.getLogger(f"{name}-{mp.current_process().name}")

    # Prevent multiple handlers if called more than once
    if not any(isinstance(h, logging.handlers.QueueHandler) for h in logger.handlers):
        handler = logging.handlers.QueueHandler(log_queue)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)  # Let listener filter what to print
        logger.propagate = False

    return logger