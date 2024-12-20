import asyncio
import threading
import pygame
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod

conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)

async def move_device(x, y, z):
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        {
            "api_id": SPORT_CMD["Move"],
            "parameter": {"x": x, "y": y, "z": z}
        }
    )

async def stand_device():
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        {"api_id": SPORT_CMD["StandOut"], "parameter": {"data": True}}
    )

async def sit_device():
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        {"api_id": SPORT_CMD["StandOut"], "parameter": {"data": False}}
    )

def handle_key_press(keys):
    if keys[pygame.K_w]:
        asyncio.run_coroutine_threadsafe(move_device(0.2, 0, 0), loop)
    if keys[pygame.K_s]:
        asyncio.run_coroutine_threadsafe(move_device(-0.2, 0, 0), loop)
    if keys[pygame.K_a]:
        asyncio.run_coroutine_threadsafe(move_device(0, -0.2, 0), loop)
    if keys[pygame.K_d]:
        asyncio.run_coroutine_threadsafe(move_device(0, 0.2, 0), loop)
    if keys[pygame.K_p]:
        asyncio.run_coroutine_threadsafe(stand_device(), loop)
    if keys[pygame.K_o]:
        asyncio.run_coroutine_threadsafe(sit_device(), loop)

def run_asyncio_loop():
    async def setup():
        await conn.connect()
    loop.run_until_complete(setup())
    loop.run_forever()

loop = asyncio.new_event_loop()
asyncio_thread = threading.Thread(target=run_asyncio_loop)
asyncio_thread.start()

pygame.init()
screen = pygame.display.set_mode((400, 300))
pygame.display.set_caption("Controlador do Dispositivo")

running = True
try:
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False
                    break

        keys = pygame.key.get_pressed()
        handle_key_press(keys)  # Passa o estado de todas as teclas para handle_key_press()

finally:
    loop.call_soon_threadsafe(loop.stop)
    async def wait_for_loop():
        await asyncio.sleep(0.1)
    asyncio.run(wait_for_loop())
    pygame.quit()
