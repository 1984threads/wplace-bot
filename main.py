# WPlace-Bot | Copyright (C) 2025  "1984Threads" <1984threads@proton.me>

from patchright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from procs.watchdog import WatchdogClass
from procs.log import logproc
from procs.manager import ManagerClass
import subprocess
import os
import multiprocessing as mp
import tkinter as tk


"""
TODO:
Block redirects to https://wplace.live/offline (so we can skip the 10 sec cooldown)
"""

GACC_COUNT = 1

def main():
    os.makedirs("sessions/pre/", exist_ok=True)
    os.makedirs("sessions/post/", exist_ok=True)

    # Spawn browser externally (I don't like dealing it internally)
    browser_process = subprocess.Popen(
        ["npx", "patchright", "launch-server", "--browser", "chromium", "--config", "patchright.json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=True
    )

    ws_endpoint = None
    for line in browser_process.stdout:
        print(">>", line.strip())
        if "ws://localhost" in line:
            ws_endpoint = line.strip()
            print("Found WebSocket URL:", ws_endpoint)
            break

    if ws_endpoint is None:
        raise ValueError("Invalid WebSocket, its none")
    print(f"Browser WS Endpoint: {ws_endpoint}")

    browser = sync_playwright().start().chromium.connect(ws_endpoint=ws_endpoint)

    print("Note: Your login credentials and cookies ARE NOT sent anywhere and are ONLY STORED LOCALLY. You can check by yourself on sessions/*/*.json")
    for gacc_id in range(GACC_COUNT):
        if os.path.exists(f"sessions/pre/{gacc_id}.json"):
            print(f"Skipping GA N°{gacc_id} because its session file exists")
            continue
        ctx = browser.new_context()

        page = ctx.new_page()
        page.goto("https://accounts.google.com")
        print(f"Login to GA N°{gacc_id} now.")
        while True:
            if "myaccount.google.com" in page.url:
                break
            else:
                page.wait_for_timeout(500)

        print("Saving Pre-State...")
        ctx.storage_state(path=f"sessions/pre/{gacc_id}.json")
        print("Saved Successfully")
        ctx.close()

    # Queues
    log_pipe = mp.Queue()
    task_pipe = mp.Queue()

    log_proc = mp.Process(target=logproc, args=(log_pipe,))
    log_proc.start()

    watchdog_processes = []
    action_value = mp.Value('b', True)

    manager_proc = ManagerClass(
        log_pipe=log_pipe,
        task_pipe=task_pipe,
        luz_lock=action_value
    )
    manager_proc.start()

    for gacc_id in range(GACC_COUNT):
        x = WatchdogClass(
            ws_endpoint=ws_endpoint,
            log_pipe=log_pipe,
            task_pipe=task_pipe,
            action_value=action_value,
            gacc_id=gacc_id,
        )
        x.start()
        watchdog_processes.append(x)

    for x in watchdog_processes:
        x.join()

    log_proc.kill()
    manager_proc.kill()
    print("End")

if __name__ == "__main__":
    main()