# train_robot.py

import gym
from gym import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
import asyncio
import threading
import json
import cv2
import numpy as np
from queue import Queue, Empty
import torch
import torchvision.transforms as T
import pygame

# Filas para comunicação entre threads
frame_queue = Queue()

# Configuração da conexão WebRTC
conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)

# Definição dos espaços de ação e observação
# Ações: [andar para frente, andar para trás, rotacionar para a esquerda, rotacionar para a direita]
ACTION_FORWARD = 0
ACTION_BACKWARD = 1
ACTION_ROTATE_LEFT = 2
ACTION_ROTATE_RIGHT = 3

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
        if action == ACTION_FORWARD:
            send_move_command(1, 0, 0)  # Andar para frente
        elif action == ACTION_BACKWARD:
            send_move_command(-1, 0, 0)  # Andar para trás
        elif action == ACTION_ROTATE_LEFT:
            send_move_command(0, 0, 1)  # Rotacionar para a esquerda
        elif action == ACTION_ROTATE_RIGHT:
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
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return frame
        except Empty:
            # Se não houver frames disponíveis, retornar uma imagem preta
            return np.zeros((240, 320, 3), dtype=np.uint8)

    def calculate_reward(self, observation):
        """
        Calcula a recompensa baseada na observação.
        """
        # Implementar lógica de recompensa baseada na observação
        # Por exemplo, recompensar se o robô estiver se movendo sem colisões
        # Aqui está um exemplo simplificado:
        # Recompensa constante
        return 1.0

    def check_done(self, observation):
        """
        Verifica se o episódio terminou.
        """
        # Implementar lógica de terminação baseada na observação
        # Por exemplo, detectar colisões
        # Aqui está um exemplo simplificado:
        return False

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
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0.05), loop)

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

# Loop principal para manter o script rodando
try:
    while training_thread.is_alive():
        pass
finally:
    # Encerrando o loop asyncio e o Pygame
    pygame.quit()
