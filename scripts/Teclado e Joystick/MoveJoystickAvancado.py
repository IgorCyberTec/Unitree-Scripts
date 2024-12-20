import asyncio
import threading
import pygame
from time import time
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
import ctypes
import json

# Configuração da conexão WebRTC
conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)
conn = Go2WebRTCConnection(WebRTCConnectionMethod.Remote, serialNumber="B42D4000O49AKA06", username="andre@glededu.com", password="Gie2309$")


# Inicializar suporte ao joystick
pygame.init()
pygame.joystick.init()
screen = pygame.display.set_mode((0, 0), pygame.NOFRAME)  # Sem bordas, com transparência
pygame.display.set_caption("Janela Transparente")
hwnd = pygame.display.get_wm_info()["window"]

joystick = pygame.joystick.Joystick(0)  # Primeiro controle conectado
joystick.init()

# Estados
movement_active = {"forward": False, "backward": False, "rotate_left": False, "rotate_right": False}
movement_tasks = {}
is_moving = False  # Indica se o robô está se movendo
is_executing_action = False  # Indica se o robô está executando uma ação

# Função para enviar comandos
async def send_command(api_id, parameter=None):
    print(f"Enviando comando: {api_id}, com parâmetros: {parameter}")
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        {"api_id": api_id, "parameter": parameter if parameter else {}}
    )

async def send_data(api_id, parameter=None):
    print(f"Enviando comando: {api_id}, com parâmetros: {parameter}")
    await conn.datachannel.pub_sub.publish_request_new(
        api_id, parameter
    )
    threading.Timer(2, reset_is_executing_action).start()

# Função para mover o dispositivo
async def move_device(x, y, z):
    await send_command(SPORT_CMD["Move"], {"x": x, "y": y, "z": z})

# Função de movimento contínuo
async def continuous_movement(direction, x, y, z):
    while movement_active[direction]:
        await move_device(x, y, z)

# Função para redefinir o estado de execução de ação
def reset_is_executing_action():
    global is_executing_action
    is_executing_action = False
    print("Ação concluída. Pronto para o próximo comando.")

# Dicionário de durações das ações
action_durations = {
    SPORT_CMD["StandUp"]: 1.0,
    SPORT_CMD["Sit"]: 1.0,
    SPORT_CMD["WiggleHips"]: 5.0,
    SPORT_CMD["Dance1"]: 10.0,
}

# Função para enviar comandos de ação
def send_action_command(api_id):
    global is_executing_action
    if is_executing_action:
        print(api_id)
        print("Já existe uma ação em execução. Aguarde antes de enviar outro comando.")
        return
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

    axis_right_x = joystick.get_axis(2)  # Eixo X do analógico direito
    axis_right_y = joystick.get_axis(3)  

    # Movimento para frente
    if axis_forward < -0.1:
        if not movement_active["forward"]:
            movement_active["forward"] = True
            movement_tasks["forward"] = asyncio.run_coroutine_threadsafe(
                continuous_movement("forward", 1, 0, 0), loop
            )
    else:
        if movement_active["forward"]:
            movement_active["forward"] = False

    # Movimento para trás
    if axis_forward > 0.1:
        if not movement_active["backward"]:
            movement_active["backward"] = True
            movement_tasks["backward"] = asyncio.run_coroutine_threadsafe(
                continuous_movement("backward", -1, 0, 0), loop
            )
    else:
        if movement_active["backward"]:
            movement_active["backward"] = False

    # Rotação para a esquerda
    if axis_right_y < -0.1:
        if not movement_active["rotate_left"]:
            movement_active["rotate_left"] = True
            movement_tasks["rotate_left"] = asyncio.run_coroutine_threadsafe(
                continuous_movement("rotate_left", 0, 0, 1), loop
            )
    else:
        if movement_active["rotate_left"]:
            movement_active["rotate_left"] = False

    # Rotação para a direita
    if axis_right_y > 0.1:
        if not movement_active["rotate_right"]:
            movement_active["rotate_right"] = True
            movement_tasks["rotate_right"] = asyncio.run_coroutine_threadsafe(
                continuous_movement("rotate_right", 0, 0, -1), loop
            )
    else:
        if movement_active["rotate_right"]:
            movement_active["rotate_right"] = False

    # Atualizar estado de movimento
    update_is_moving()

    # Ações específicas para botões - Não bloqueiam o movimento
    if joystick.get_button(0):  # Botão A
        send_action_command(SPORT_CMD["StandUp"])
    if joystick.get_button(1):  # Botão B
        send_action_command(SPORT_CMD["StandDown"])
    if joystick.get_button(2):  # Botão X
        send_action_command(SPORT_CMD["WiggleHips"])
    if joystick.get_button(3):  # Botão Y
        send_action_command(SPORT_CMD["FingerHeart"])

    # Adicionar comandos para LB, RB, LT e RT
    lb_pressed = joystick.get_button(4)  # LB
    rb_pressed = joystick.get_button(5)  # RB
    lt_value = joystick.get_axis(2)  # LT
    rt_value = joystick.get_axis(5)  # RT
    hat_state = joystick.get_hat(0)  # Setas

    if hat_state == (0, -1):  # Seta para baixo
        send_action_command(SPORT_CMD["Sit"])
    if hat_state == (0, 1):  # Seta para cima
        send_action_command(SPORT_CMD["Hello"])
    if hat_state == (-1, 0):  # Seta para a esquerda
        send_action_command(SPORT_CMD["WiggleHips"])
    if hat_state == (1, 0):  # Seta para a direita
        send_action_command(SPORT_CMD["FrontJump"])

# Loop asyncio em um thread separado
init = 'normal'
def run_asyncio_loop():
    async def setup():
        await conn.connect()
        response = await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"], 
            {"api_id": 1001}
        )

        if response['data']['header']['status']['code'] == 0:
            data = json.loads(response['data']['data'])
            current_motion_switcher_mode = data['name']
            print(f"Current motion mode: {current_motion_switcher_mode}")
        if current_motion_switcher_mode != init:
            print(f"Switching motion mode from {current_motion_switcher_mode} to '{init}'...")
            await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["MOTION_SWITCHER"], 
                {
                    "api_id": 1002,
                    "parameter": {"name": init}
                }
            )
            await asyncio.sleep(5)
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
        pygame.display.update()

finally:
    # Encerrando o loop asyncio e o Pygame
    loop.call_soon_threadsafe(loop.stop)
    async def wait_for_loop():
        await asyncio.sleep(1)
    asyncio.run(wait_for_loop())
    pygame.quit()
