import multiprocessing as mp
import random
import time
import os
import traceback
import json
import math
from patchright.sync_api import sync_playwright
from helpers import logsetup

ADDITIONAL_ARGS = "/?lat=73.65355915529693&lng=54.57858365302732&zoom=13.647975872902206"

class WatchdogClass(mp.Process):
    def __init__(self,
            ws_endpoint: str,
            log_pipe: mp.Queue,
            task_pipe: mp.Queue,
            action_value,
            gacc_id: int):
        super().__init__()
        self.ws_endpoint = ws_endpoint
        self.log_pipe = log_pipe
        self.task_pipe = task_pipe
        self.action_value = action_value
        self.gacc_id = gacc_id
        self.task_list = None
        self.browser = None

    def run(self):
        logger = logsetup(self.log_pipe, f"Watchdog-{self.gacc_id}")
        logger.info(f"Connecting to browser at {self.ws_endpoint}...")
        self.browser = sync_playwright().start().chromium.connect(ws_endpoint=self.ws_endpoint)
        
        logger.info("Connected to browser. Now iniating context...")
        if os.path.exists(f"sessions/post/{self.gacc_id}.json") is False:
            if os.path.exists(f"sessions/pre/{self.gacc_id}.json") is False:
                raise ValueError("Pre-Session doesn't exist. Did you log in before hand?")
            ctx = self.browser.new_context(storage_state=f"sessions/pre/{self.gacc_id}.json")
            logger.info("Context Initialization Success - Creating Post-Session")

            page = ctx.new_page()

            # Open the site
            page.goto('https://wplace.live/', wait_until="networkidle")
            logger.info("10 Sec cooldown")
            page.wait_for_timeout(10000)
            logger.info("Proceeding")

            login_btn = page.locator("body > div > div.disable-pinch-zoom.relative.h-full.overflow-hidden.svelte-6wmtgk > div.absolute.right-2.top-2.z-30 > div > button")
            login_btn.wait_for(state="visible")
            login_btn.click(delay=random.randint(20, 80))

            parent_div = page.locator("body > div > dialog:nth-child(3) > div > div > div > form > div > div > div")
            parent_div.wait_for(state="attached")

            child = parent_div.locator("[id^='cf-chl-widget-'][id$='_response']")
            child.wait_for(state="attached", timeout=10000)

            start_time = time.time()
            handled = False

            while (time.time() - start_time) < 30 and handled is False:
                if child.input_value().strip().startswith("0."):
                    handled = True
                page.wait_for_timeout(500)
            
            if handled is False:
                logger.info("Cloudflare doesn't trust us. Clicking Captcha...")
                raise ValueError("TODO")
            logger.info("Captcha Success")

            google_btn = page.locator("body > div > dialog:nth-child(3) > div > div > div > form > div > a:nth-child(1)")
            google_btn.wait_for(state="visible")
            google_btn.click()

            ctx.storage_state(path=f"sessions/post/{self.gacc_id}.json")
            logger.info("Post-Session state saved. Restarting Context...")
            ctx.close()

        ctx = self.browser.new_context(storage_state=f"sessions/post/{self.gacc_id}.json")
        logger.info("Context Initialization Success - Post-Session already exists, OK.")
        page = ctx.new_page()

        def handle_route(route, request):
            if self.task_list is None:
                route.fulfill(
                    status=200,
                    content_type="text/plain",
                    body="NONE 110"
                )
            original_data = json.loads(request.post_data)
            original_data["colors"] = self.task_list["colors"]
            original_data["coords"] = self.task_list["coords"]

            route.continue_(
                method=request.method,
                headers=request.headers,
                post_data=json.dumps(original_data)
            )

        def get_charges() -> int:
            tmp_page = ctx.new_page()
            response = tmp_page.goto("https://backend.wplace.live/me", wait_until="networkidle")
            loaded_json = json.loads(response.text())
            tmp_page.close()
            return math.floor(loaded_json["charges"]["count"])

        page.route("https://backend.wplace.live/s0/pixel/*/*", handle_route)

        while True:
            try:
                page.goto('https://wplace.live/' + ADDITIONAL_ARGS, wait_until="networkidle")
                logger.info("10 Sec cooldown")
                page.wait_for_timeout(10000)
                logger.info("Proceeding")

                available_charges = get_charges()
                logger.info(f"Available charges: {available_charges}")
                
                if available_charges <= 10:
                    page.wait_for_timeout(60*1000)
                    logger.info("Less than 10 charges available. Waiting a minute.")
                    continue

                paint_btn_parent = page.locator("body > div > div.disable-pinch-zoom.relative.h-full.overflow-hidden.svelte-6wmtgk > div.absolute.bottom-3.left-1\/2.z-30.-translate-x-1\/2")
                paint_btn_parent.wait_for(state="attached")

                if self.action_value.value is False:
                    self.task_list = None
                    logger.info("Action value is false... sleeping...")
                    time.sleep(1)
                    continue

                self.task_list = {
                    "colors": [],
                    "coords": []
                }

                for x in range(1, available_charges):
                    resp = self.task_pipe.get()
                    self.task_list["colors"].append(resp["color_id"])
                    self.task_list["coords"].extend(resp["coord"])
                    logger.info(f'added: {resp["color_name"]} at {resp["coord"]}')

                cf_requried = page.locator("div.disable-pinch-zoom.relative.h-full.overflow-hidden.svelte-6wmtgk > div.z-100.absolute.bottom-1.left-1_2.-translate-x-1_2 > div.svelte-lgvfki5").is_visible()

                if cf_requried is True:
                    raise ValueError("TODO")
                
                paint_btn = paint_btn_parent.locator("button")
                paint_btn.wait_for(state="visible")
                paint_btn.click(delay=random.randint(20, 80))

                page.mouse.move(100, 200)
                page.keyboard.down(" ")
                page.wait_for_timeout(100)
                page.keyboard.up(" ")              

                confirm_paint_btn = page.locator("body > div:nth-child(1) > div.disable-pinch-zoom.relative.h-full.overflow-hidden.svelte-6wmtgk > div.absolute.bottom-0.left-0.z-50.w-full > div > div > div.relative.h-12.sm\:h-14 > div.absolute.bottom-0.left-1\/2.-translate-x-1\/2 > button")
                confirm_paint_btn.wait_for(state="visible")
                confirm_paint_btn.click(delay=random.randint(20, 80))
                #page.wait_for_timeout(1000*1000)

            except Exception as e:
                logger.info(f"Detected error: {''.join(str(item) for item in traceback.format_exception(type(e), e, e.__traceback__))}")