import asyncio
import threading
import pygame
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod

# Conexão WebRTC
conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)

# Estados de movimento
movement_active = {"w": False, "s": False, "a": False, "d": False}
movement_tasks = {"w": None, "s": None, "a": None, "d": None}

# Função para enviar comandos
async def send_command(api_id, parameter=None):
    print(f"Sending command: {api_id}, with parameters: {parameter}")
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        {"api_id": api_id, "parameter": parameter if parameter else {}}
    )

# Função para mover o dispositivo
async def move_device(x, y, z):
    await send_command(SPORT_CMD["Move"], {"x": x, "y": y, "z": z})

# Função de movimento contínuo
async def continuous_movement(direction, x, y, z):
    while movement_active[direction]:
        await move_device(x, y, z)

# Função para lidar com eventos do teclado
def handle_key_events(event):
    global movement_active, movement_tasks

    if event.type == pygame.KEYDOWN:
        # Início do movimento
        if event.key == pygame.K_w and not movement_active["w"]:
            movement_active["w"] = True
            movement_tasks["w"] = asyncio.run_coroutine_threadsafe(
                continuous_movement("w", 1, 0, 0), loop
            )
        if event.key == pygame.K_s and not movement_active["s"]:
            movement_active["s"] = True
            movement_tasks["s"] = asyncio.run_coroutine_threadsafe(
                continuous_movement("s", -1, 0, 0), loop
            )
        if event.key == pygame.K_a and not movement_active["a"]:
            movement_active["a"] = True
            movement_tasks["a"] = asyncio.run_coroutine_threadsafe(
                continuous_movement("a", 0, 0, -1), loop  # Rotação para a esquerda
            )
        if event.key == pygame.K_d and not movement_active["d"]:
            movement_active["d"] = True
            movement_tasks["d"] = asyncio.run_coroutine_threadsafe(
                continuous_movement("d", 0, 0, 1), loop  # Rotação para a direita
            )

        # Ações especiais (pressione as teclas para executar)
        if event.key == pygame.K_1:  # StandUp
            asyncio.run_coroutine_threadsafe(send_command(SPORT_CMD["StandUp"]), loop)
        if event.key == pygame.K_2:  # Sit
            asyncio.run_coroutine_threadsafe(send_command(SPORT_CMD["Sit"]), loop)
        if event.key == pygame.K_3:  # WiggleHips
            asyncio.run_coroutine_threadsafe(send_command(SPORT_CMD["WiggleHips"]), loop)
        if event.key == pygame.K_4:  # FrontJump
            asyncio.run_coroutine_threadsafe(send_command(SPORT_CMD["FrontJump"]), loop)
        if event.key == pygame.K_5:  # BackFlip
            asyncio.run_coroutine_threadsafe(send_command(SPORT_CMD["BackFlip"]), loop)
        if event.key == pygame.K_6:  # Dance1
            asyncio.run_coroutine_threadsafe(send_command(SPORT_CMD["Dance1"]), loop)
        if event.key == pygame.K_7:  # Dance2
            asyncio.run_coroutine_threadsafe(send_command(SPORT_CMD["Dance2"]), loop)
        if event.key == pygame.K_8:  # MoonWalk
            asyncio.run_coroutine_threadsafe(send_command(SPORT_CMD["MoonWalk"]), loop)

    if event.type == pygame.KEYUP:
        # Fim do movimento
        if event.key == pygame.K_w:
            movement_active["w"] = False
        if event.key == pygame.K_s:
            movement_active["s"] = False
        if event.key == pygame.K_a:
            movement_active["a"] = False
        if event.key == pygame.K_d:
            movement_active["d"] = False

# Loop asyncio em um thread separado
def run_asyncio_loop():
    async def setup():
        await conn.connect()
    loop.run_until_complete(setup())
    loop.run_forever()

loop = asyncio.new_event_loop()
asyncio_thread = threading.Thread(target=run_asyncio_loop, daemon=True)
asyncio_thread.start()

# Inicialização do Pygame
pygame.init()
screen = pygame.display.set_mode((400, 300))
pygame.display.set_caption("Controlador do Dispositivo")

# Loop principal
running = True
try:
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            if event.type in [pygame.KEYDOWN, pygame.KEYUP]:
                handle_key_events(event)
finally:
    # Encerrando o loop asyncio e o Pygame
    loop.call_soon_threadsafe(loop.stop)
    async def wait_for_loop():
        await asyncio.sleep(0.1)
    asyncio.run(wait_for_loop())
    pygame.quit()
