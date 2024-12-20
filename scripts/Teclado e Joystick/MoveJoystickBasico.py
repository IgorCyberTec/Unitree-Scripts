import asyncio
import threading
import pygame
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod

# Conexão WebRTC
conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)

# Inicializar suporte ao joystick
pygame.init()
pygame.joystick.init()
joystick = pygame.joystick.Joystick(0)  # Primeiro controle conectado
joystick.init()

# Estados de movimento e ação
movement_active = {"forward": False, "backward": False, "rotate_left": False, "rotate_right": False}
movement_tasks = {}
is_moving = False  # Indica se o robô está se movendo
is_executing_action = False  # Indica se o robô está executando uma ação

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
        await asyncio.sleep(0.1)  # Intervalo entre comandos

# Função para redefinir o estado de execução de ação
def reset_is_executing_action():
    global is_executing_action
    is_executing_action = False

# Dicionário de durações das ações
action_durations = {
    SPORT_CMD["StandUp"]: 3.0,
    SPORT_CMD["Sit"]: 3.0,
    SPORT_CMD["WiggleHips"]: 5.0,
    SPORT_CMD["Dance1"]: 10.0,
}

# Função para enviar comandos de ação
def send_action_command(api_id):
    global is_executing_action
    is_executing_action = True
    asyncio.run_coroutine_threadsafe(send_command(api_id), loop)
    duration = action_durations.get(api_id, 2.0)
    threading.Timer(duration, reset_is_executing_action).start()

# Função para atualizar o estado de movimento
def update_is_moving():
    global is_moving
    is_moving = any(movement_active.values())

# Função para lidar com eventos do joystick
def handle_joystick_events():
    global movement_active, movement_tasks, is_moving, is_executing_action

    # Movimentos contínuos baseados nos eixos analógicos
    axis_forward = joystick.get_axis(1)  # Eixo Y do analógico esquerdo
    axis_rotation = joystick.get_axis(0)  # Eixo X do analógico esquerdo

    # Movimento para frente
    if axis_forward < -0.2 and not is_executing_action:
        if not movement_active["forward"]:
            movement_active["forward"] = True
            movement_tasks["forward"] = asyncio.run_coroutine_threadsafe(
                continuous_movement("forward", 0.2, 0, 0), loop
            )
    else:
        if movement_active["forward"]:
            movement_active["forward"] = False

    # Movimento para trás
    if axis_forward > 0.2 and not is_executing_action:
        if not movement_active["backward"]:
            movement_active["backward"] = True
            movement_tasks["backward"] = asyncio.run_coroutine_threadsafe(
                continuous_movement("backward", -0.2, 0, 0), loop
            )
    else:
        if movement_active["backward"]:
            movement_active["backward"] = False

    # Rotação para a esquerda
    if axis_rotation < -0.2 and not is_executing_action:
        if not movement_active["rotate_left"]:
            movement_active["rotate_left"] = True
            movement_tasks["rotate_left"] = asyncio.run_coroutine_threadsafe(
                continuous_movement("rotate_left", 0, 0, 0.1), loop
            )
    else:
        if movement_active["rotate_left"]:
            movement_active["rotate_left"] = False

    # Rotação para a direita
    if axis_rotation > 0.2 and not is_executing_action:
        if not movement_active["rotate_right"]:
            movement_active["rotate_right"] = True
            movement_tasks["rotate_right"] = asyncio.run_coroutine_threadsafe(
                continuous_movement("rotate_right", 0, 0, -0.1), loop
            )
    else:
        if movement_active["rotate_right"]:
            movement_active["rotate_right"] = False

    # Atualizar estado de movimento
    update_is_moving()

    # Ações específicas para botões
    if not is_moving and not is_executing_action:
        if joystick.get_button(0):  # Botão A
            send_action_command(SPORT_CMD["StandUp"])
        if joystick.get_button(1):  # Botão B
            send_action_command(SPORT_CMD["Sit"])
        if joystick.get_button(2):  # Botão X
            send_action_command(SPORT_CMD["WiggleHips"])
        if joystick.get_button(3):  # Botão Y
            send_action_command(SPORT_CMD["Dance1"])

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

        # Lidar com eventos do joystick
        handle_joystick_events()

finally:
    # Encerrando o loop asyncio e o Pygame
    loop.call_soon_threadsafe(loop.stop)
    async def wait_for_loop():
        await asyncio.sleep(0.1)
    asyncio.run(wait_for_loop())
    pygame.quit()
