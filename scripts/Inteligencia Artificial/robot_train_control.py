# robot_train_control.py

import asyncio
import threading
import pygame
import cv2
import numpy as np
from queue import Queue, Empty
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
import json
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
import gym
from gym import spaces
import torch
import torchvision.transforms as T
import time

# Configuração da conexão WebRTC
conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)

# Inicializar suporte ao joystick
pygame.init()
pygame.joystick.init()
screen = pygame.display.set_mode((400, 300))
pygame.display.set_caption("Controle e Treinamento do Robô")

joystick = pygame.joystick.Joystick(0)  # Primeiro controle conectado
joystick.init()

# Filas para comunicação entre threads
frame_queue = Queue()

# Estados
threshold = 0.1  # Valor mínimo para considerar movimento
is_executing_action = False  # Indica se o robô está executando uma ação

# Dicionário de durações das ações
action_durations = {
    SPORT_CMD["StandUp"]: 1.0,
    SPORT_CMD["Sit"]: 1.0,
    SPORT_CMD["WiggleHips"]: 5.0,
    SPORT_CMD["Dance1"]: 10.0,
    SPORT_CMD["Hello"]: 1.0,
    SPORT_CMD["FrontJump"]: 2.0,
}

# Funções para enviar comandos
async def send_command(api_id, parameter=None):
    try:
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"],
            {"api_id": api_id, "parameter": parameter if parameter else {}}
        )
        print(f"Comando enviado: {api_id}, Parâmetros: {parameter}")
    except Exception as e:
        print(f"Erro ao enviar comando: {e}")

def send_move_command(x, y, z):
    asyncio.run_coroutine_threadsafe(
        send_command(SPORT_CMD["Move"], {"x": x, "y": y, "z": z}), loop
    )

def send_action_command(api_id):
    asyncio.run_coroutine_threadsafe(
        send_command(api_id), loop
    )

# Função para redefinir o estado de execução de ação
def reset_is_executing_action():
    global is_executing_action
    is_executing_action = False
    print("Ação concluída. Pronto para o próximo comando.")

# Função para enviar comandos de ação com bloqueio
def send_action_command_with_lock(api_id):
    global is_executing_action
    if is_executing_action:
        print("Já existe uma ação em execução. Aguarde antes de enviar outro comando.")
        return
    is_executing_action = True
    send_action_command(api_id)
    duration = action_durations.get(api_id, 2.0)
    threading.Timer(duration, reset_is_executing_action).start()

# Função para capturar frames da câmera e colocá-los na fila
def capture_camera_frames():
    # Substitua '0' pelo índice correto da câmera do robô
    cap = cv2.VideoCapture(0)
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_queue.put(frame)
        # Limitar a taxa de captura para evitar sobrecarga
        time.sleep(0.05)  # 20 FPS

# Loop asyncio em um thread separado
init = 'normal'
def run_asyncio_loop():
    async def setup():
        try:
            await conn.connect()
            response = await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["MOTION_SWITCHER"],
                {"api_id": 1001}
            )
            if response['data']['header']['status']['code'] == 0:
                data = json.loads(response['data']['data'])
                current_motion_switcher_mode = data['name']
                print(f"Modo atual: {current_motion_switcher_mode}")
                if current_motion_switcher_mode != init:
                    print(f"Alterando modo de movimento para '{init}'...")
                    await conn.datachannel.pub_sub.publish_request_new(
                        RTC_TOPIC["MOTION_SWITCHER"],
                        {"api_id": 1002, "parameter": {"name": init}}
                    )
                    await asyncio.sleep(5)
        except Exception as e:
            print(f"Erro na configuração do WebRTC: {e}")

    try:
        loop.run_until_complete(setup())
        loop.run_forever()
    except RuntimeError as e:
        print(f"Erro no loop asyncio: {e}")

loop = asyncio.new_event_loop()
asyncio_thread = threading.Thread(target=run_asyncio_loop, daemon=True)
asyncio_thread.start()

# Iniciar captura de frames da câmera em uma thread separada
camera_thread = threading.Thread(target=capture_camera_frames, daemon=True)
camera_thread.start()

# Classe do Ambiente Personalizado
class RobotEnv(gym.Env):
    """
    Ambiente personalizado para o robô cachorro.
    """
    def __init__(self, frame_queue):
        super(RobotEnv, self).__init__()

        # Definição dos espaços de ação e observação
        self.action_space = spaces.Discrete(4)  # 4 ações
        self.observation_space = spaces.Box(low=0, high=255, shape=(240, 320, 3), dtype=np.uint8)

        # Inicializar variáveis de estado
        self.current_observation = np.zeros((240, 320, 3), dtype=np.uint8)
        self.done = False

        # Fila para frames
        self.frame_queue = frame_queue

    def reset(self):
        """
        Reseta o ambiente para um estado inicial.
        """
        self.done = False
        self.current_observation = np.zeros((240, 320, 3), dtype=np.uint8)
        return self.current_observation

    def step(self, action):
        """
        Executa uma ação e retorna a nova observação, recompensa, done e info.
        """
        if self.done:
            return self.reset(), 0, self.done, {}

        # Mapeamento de ações
        if action == 0:
            send_move_command(1, 0, 0)  # Andar para frente
        elif action == 1:
            send_move_command(-1, 0, 0)  # Andar para trás
        elif action == 2:
            send_move_command(0, 0, 1)  # Rotacionar para a esquerda
        elif action == 3:
            send_move_command(0, 0, -1)  # Rotacionar para a direita

        # Obter observação
        self.current_observation = self.get_camera_frame()

        # Calcular recompensa
        reward = self.calculate_reward(self.current_observation)

        # Verificar condição de término
        self.done = self.check_done(self.current_observation)

        return self.current_observation, reward, self.done, {}

    def get_camera_frame(self):
        """
        Função para obter o frame da câmera do robô.
        """
        try:
            frame = self.frame_queue.get_nowait()
            frame = cv2.resize(frame, (320, 240))
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)  # OpenCV usa BGR
            return frame
        except Empty:
            # Se não houver frames disponíveis, retornar uma imagem preta
            return np.zeros((240, 320, 3), dtype=np.uint8)

    def calculate_reward(self, observation):
        """
        Calcula a recompensa baseada na observação.
        """
        # Implementar lógica de recompensa baseada na observação
        # Exemplo simplificado:
        # Recompensa constante
        return 1.0

    def check_done(self, observation):
        """
        Verifica se o episódio terminou.
        """
        # Implementar lógica de terminação baseada na observação
        # Exemplo simplificado:
        return False

# Função para treinar o modelo PPO
def train_model():
    # Inicializar o ambiente personalizado
    env = RobotEnv(frame_queue)
    env = DummyVecEnv([lambda: env])

    # Instanciar o modelo PPO com política CNN adequada para observações de imagem
    model = PPO("CnnPolicy", env, verbose=1, tensorboard_log="./ppo_robot_tensorboard/")

    # Treinar o modelo
    print("Iniciando o treinamento do modelo PPO...")
    model.learn(total_timesteps=100000)  # Ajuste o número de timesteps conforme necessário

    # Salvar o modelo treinado
    model.save("ppo_robot")
    print("Modelo treinado e salvo como 'ppo_robot.zip'")

    # Encerrar o loop asyncio após o treinamento
    loop.call_soon_threadsafe(loop.stop)
    asyncio_thread.join()

# Iniciar o treinamento em uma thread separada para não bloquear o loop principal
training_thread = threading.Thread(target=train_model, daemon=True)
training_thread.start()

# Função para exibir frames na janela Pygame
def display_frames():
    try:
        frame = frame_queue.get_nowait()
        frame_surface = pygame.surfarray.make_surface(frame)
        screen.blit(frame_surface, (0, 0))
    except Empty:
        # Mostrar uma tela preta se não houver frames
        screen.fill((0, 0, 0))

# Função para lidar com eventos do joystick (Opcional: Remova se não quiser controle manual)
def handle_joystick_events():
    global is_executing_action

    # Movimentos baseados nos eixos analógicos
    axis_forward = joystick.get_axis(1)  # Eixo Y do analógico esquerdo
    axis_rotation = joystick.get_axis(0)  # Eixo X do analógico esquerdo

    # Touchpad como controle de movimento (se aplicável)
    try:
        touchpad_x = joystick.get_axis(2)  # X do touchpad
        touchpad_y = joystick.get_axis(5)  # Y do touchpad
        if abs(touchpad_x) > threshold or abs(touchpad_y) > threshold:
            send_move_command(touchpad_y * -1, 0, touchpad_x * -1)
    except pygame.error:
        print("Erro ao acessar o touchpad.")

    # Verificar valores mínimos antes de enviar comandos
    if abs(axis_forward) > threshold:
        send_move_command(axis_forward * -1, 0, 0)  # Inverter eixo para ajuste
    if abs(axis_rotation) > threshold:
        send_move_command(0, 0, axis_rotation * -1)

    # Ações específicas para botões
    if joystick.get_button(1):  # Botão X (PS4)
        send_action_command_with_lock(SPORT_CMD["StandUp"])
    if joystick.get_button(2):  # Botão Círculo
        send_action_command_with_lock(SPORT_CMD["StandDown"])
    if joystick.get_button(0):  # Botão Quadrado
        send_action_command_with_lock(SPORT_CMD["WiggleHips"])
    if joystick.get_button(3):  # Botão Triângulo
        send_action_command_with_lock(SPORT_CMD["FingerHeart"])

    # Comandos adicionais para LB, RB, LT, RT e Setas
    lb_pressed = joystick.get_button(4)  # LB
    rb_pressed = joystick.get_button(5)  # RB
    lt_value = joystick.get_axis(2)  # LT
    rt_value = joystick.get_axis(5)  # RT
    hat_state = joystick.get_hat(0)  # Setas

    if hat_state == (0, -1):  # Seta para baixo
        send_action_command_with_lock(SPORT_CMD["Sit"])
    if hat_state == (0, 1):  # Seta para cima
        send_action_command_with_lock(SPORT_CMD["Hello"])
    if hat_state == (-1, 0):  # Seta para a esquerda
        send_action_command_with_lock(SPORT_CMD["WiggleHips"])
    if hat_state == (1, 0):  # Seta para a direita
        send_action_command_with_lock(SPORT_CMD["FrontJump"])

# Loop principal
try:
    while training_thread.is_alive():
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # Encerrar o treinamento e o script
                training_thread.join(timeout=1)
                raise KeyboardInterrupt

        # Lidar com eventos do joystick (Opcional)
        handle_joystick_events()

        # Exibir frame na janela
        display_frames()

        pygame.display.update()

except KeyboardInterrupt:
    print("Encerrando o programa...")

finally:
    # Encerrando o loop asyncio e o Pygame
    loop.call_soon_threadsafe(loop.stop)
    asyncio_thread.join()
    pygame.quit()
