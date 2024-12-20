# robot_train_control_autonomous.py

import asyncio
import threading
import cv2
import numpy as np
from queue import Queue, Empty
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
import json
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback
import gym
from gym import spaces
import torch
import torch.nn as nn
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
import time
import pygame
from stable_baselines3.common.logger import configure
import logging
from aiortc import MediaStreamTrack

# =========================================
# Configuração Inicial
# =========================================

# Configuração do logging para monitoramento e depuração
logging.basicConfig(level=logging.DEBUG)  # Alterado para DEBUG para facilitar a depuração

# Configuração da conexão WebRTC com o robô
conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)

# Inicializar o Pygame para monitoramento visual
pygame.init()
screen = pygame.display.set_mode((640, 480))  # Defina o tamanho da janela conforme necessário
pygame.display.set_caption("Treinamento Autônomo do Robô")

# Filas para comunicação entre threads
frame_queue = Queue()  # Fila para frames da câmera
lidar_queue = Queue()  # Fila para dados do LIDAR

# Estado global para gerenciar ações
is_executing_action = False  # Indica se o robô está executando uma ação

# =========================================
# Funções para Enviar Comandos ao Robô
# =========================================

async def send_command(api_id, parameter=None):
    """
    Envia um comando para o robô via WebRTC.

    Parâmetros:
    - api_id: Identificador do comando.
    - parameter: Parâmetros adicionais para o comando.
    """
    try:
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"],
            {"api_id": api_id, "parameter": parameter if parameter else {}}
        )
        logging.info(f"Comando enviado: {api_id}, Parâmetros: {parameter}")
    except Exception as e:
        logging.error(f"Erro ao enviar comando: {e}")

def send_move_command(x, y, z):
    """
    Envia um comando de movimento ao robô.

    Parâmetros:
    - x: Velocidade no eixo X.
    - y: Velocidade no eixo Y.
    - z: Velocidade no eixo Z (rotação).
    """
    # Limitar os comandos de velocidade para segurança
    max_speed = 1.0  # Defina a velocidade máxima conforme necessário
    x = np.clip(x, -max_speed, max_speed)
    y = np.clip(y, -max_speed, max_speed)
    z = np.clip(z, -max_speed, max_speed)
    
    asyncio.run_coroutine_threadsafe(
        send_command(SPORT_CMD.get("Move", 1000), {"x": x, "y": y, "z": z}), loop
    )

def send_action_command(api_id):
    """
    Envia um comando de ação específico ao robô.

    Parâmetro:
    - api_id: Identificador do comando de ação.
    """
    asyncio.run_coroutine_threadsafe(
        send_command(api_id), loop
    )

def reset_is_executing_action():
    """
    Redefine o estado de execução de ação, permitindo novos comandos.
    """
    global is_executing_action
    is_executing_action = False
    logging.info("Ação concluída. Pronto para o próximo comando.")

def send_action_command_with_lock(api_id):
    """
    Envia um comando de ação com bloqueio para evitar comandos simultâneos.

    Parâmetro:
    - api_id: Identificador do comando de ação.
    """
    global is_executing_action
    if is_executing_action:
        logging.info("Já existe uma ação em execução. Aguarde antes de enviar outro comando.")
        return
    is_executing_action = True
    send_action_command(api_id)
    duration = action_durations.get(api_id, 2.0)
    threading.Timer(duration, reset_is_executing_action).start()

# =========================================
# Definição de `action_durations`
# =========================================

# Dicionário de durações das ações (em segundos)
action_durations = {
    SPORT_CMD.get("StandUp", 1001): 1.0,
    SPORT_CMD.get("Sit", 1002): 1.0,
    SPORT_CMD.get("WiggleHips", 1003): 5.0,
    SPORT_CMD.get("Dance1", 1004): 10.0,
    SPORT_CMD.get("Hello", 1005): 1.0,
    SPORT_CMD.get("FrontJump", 1006): 2.0,
}

# =========================================
# Funções para Captura de Dados
# =========================================

def preprocess_observation(observation):
    """
    Pré-processa a observação (imagem) para reduzir a complexidade.

    Parâmetros:
    - observation: Frame atual da câmera.

    Retorna:
    - processed_observation: Imagem pré-processada.
    """
    # Redimensionar a imagem
    resized_frame = cv2.resize(observation, (160, 120))  # Reduzindo a resolução

    # Converter para escala de cinza
    gray = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2GRAY)

    # Normalizar a imagem
    normalized_frame = gray / 255.0

    # Adicionar dimensão de canal (necessário para CNNs)
    processed_observation = np.expand_dims(normalized_frame, axis=2)

    return processed_observation

def preprocess_lidar(lidar_data, lidar_size=360):
    """
    Pré-processa os dados do LIDAR para integrar à observação.

    Parâmetros:
    - lidar_data: Dados brutos do LIDAR.
    - lidar_size: Tamanho esperado dos dados do LIDAR.

    Retorna:
    - processed_lidar: Dados do LIDAR pré-processados.
    """
    try:
        # Se os dados forem JSON, parse
        if isinstance(lidar_data, str):
            lidar_json = json.loads(lidar_data)
            # Extrair informações relevantes, por exemplo, um array de distâncias
            distances = lidar_json.get("distances", [])
            # Padronizar o tamanho
            distances = distances[:lidar_size]  # Limitar a 360
            if len(distances) < lidar_size:
                distances += [0.0] * (lidar_size - len(distances))
            processed_lidar = np.array(distances, dtype=np.float32)
        elif isinstance(lidar_data, bytes):
            # Decodificar bytes se necessário
            lidar_str = lidar_data.decode('utf-8')
            lidar_json = json.loads(lidar_str)
            distances = lidar_json.get("distances", [])
            distances = distances[:lidar_size]
            if len(distances) < lidar_size:
                distances += [0.0] * (lidar_size - len(distances))
            processed_lidar = np.array(distances, dtype=np.float32)
        else:
            # Outro formato, ajuste conforme necessário
            processed_lidar = np.zeros(lidar_size, dtype=np.float32)
    except Exception as e:
        logging.error(f"Erro ao processar dados do LIDAR: {e}")
        processed_lidar = np.zeros(lidar_size, dtype=np.float32)

    # Normalizar ou ajustar conforme necessário
    processed_lidar = processed_lidar / np.max(processed_lidar) if np.max(processed_lidar) > 0 else processed_lidar

    # Redimensionar para (120, 3)
    if lidar_size % 120 == 0:
        channels = lidar_size // 120  # 3
        processed_lidar = processed_lidar.reshape(120, channels)
    else:
        # Se não for divisível, preencher com zeros
        processed_lidar = np.zeros((120, 3), dtype=np.float32)

    return processed_lidar

def process_lidar_data():
    """
    Processa os dados recebidos do LIDAR.
    """
    while True:
        try:
            # Tente obter dados do LIDAR
            data = lidar_queue.get(timeout=1)
            # Processar os dados do LIDAR conforme necessário
            processed_lidar = preprocess_lidar(data)
            lidar_queue.put(processed_lidar)
            logging.debug(f"Dado LIDAR processado e colocado na fila: {processed_lidar.shape}")
        except Empty:
            continue

# =========================================
# Loop Asyncio para Conexão WebRTC com a Câmera do Robô
# =========================================

def run_asyncio_loop(loop):
    """
    Executa o loop asyncio para gerenciar a conexão WebRTC e assinatura dos dados da câmera.
    """
    async def recv_camera_stream(track: MediaStreamTrack):
        """
        Async function para receber frames da câmera e colocá-los na fila.
        """
        while True:
            try:
                frame = await track.recv()
                # Converter o frame para um array NumPy
                img = frame.to_ndarray(format="bgr24")
                frame_queue.put(img)
                logging.debug(f"Frame da câmera recebido e colocado na fila: {img.shape}")
            except Exception as e:
                logging.error(f"Erro ao receber frame da câmera: {e}")
                break

    async def setup():
        """
        Configura a conexão WebRTC e inicia a captura de frames.
        """
        try:
            await conn.connect()
            logging.info("Conexão WebRTC estabelecida com sucesso.")

            # Switch video channel on and start receiving video frames
            conn.video.switchVideoChannel(True)
            logging.info("Canal de vídeo ativado.")

            # Adicionar callback para lidar com os frames recebidos
            conn.video.add_track_callback(recv_camera_stream)
            logging.info("Callback para recebimento de frames configurado.")
        except Exception as e:
            logging.error(f"Erro na configuração do WebRTC: {e}")

    try:
        loop.run_until_complete(setup())
        loop.run_forever()
    except RuntimeError as e:
        logging.error(f"Erro no loop asyncio: {e}")

# =========================================
# Inicialização de Threads
# =========================================

# Inicializar o loop asyncio
loop = asyncio.new_event_loop()
asyncio_thread = threading.Thread(target=run_asyncio_loop, args=(loop,), daemon=True)
asyncio_thread.start()

# Iniciar processamento de dados do LIDAR em uma thread separada
lidar_processing_thread = threading.Thread(target=process_lidar_data, daemon=True)
lidar_processing_thread.start()

# =========================================
# Classe Personalizada para Extrator de Características CNN
# =========================================

class CustomCNN(BaseFeaturesExtractor):
    """
    Classe personalizada para o extrator de características CNN.
    """
    def __init__(self, observation_space: gym.spaces.Box, features_dim: int=512):
        super(CustomCNN, self).__init__(observation_space, features_dim)
        # Calcular a dimensionalidade das imagens de entrada
        n_input_channels = observation_space.shape[2]  # 4 canais (1 da câmera + 3 do LIDAR)
        self.conv = nn.Sequential(
            nn.Conv2d(n_input_channels, 32, kernel_size=8, stride=4, padding=0),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=4, stride=2, padding=0),
            nn.ReLU(),
            nn.Conv2d(64, 64, kernel_size=3, stride=1, padding=0),
            nn.ReLU(),
            nn.Flatten(),
        )
        
        # Calcular a dimensão após as camadas convolucionais
        with torch.no_grad():
            sample_input = torch.zeros(1, *observation_space.shape)
            # Reordenar as dimensões de [batch, height, width, channels] para [batch, channels, height, width]
            sample_input = sample_input.permute(0, 3, 1, 2)
            n_flatten = self.conv(sample_input).shape[1]
        
        # Camada linear para reduzir a dimensionalidade
        self.fc = nn.Sequential(
            nn.Linear(n_flatten, features_dim),
            nn.ReLU()
        )
        
        self._features_dim = features_dim

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        # Reordenar as dimensões de [batch, height, width, channels] para [batch, channels, height, width]
        observations = observations.permute(0, 3, 1, 2)
        return self.fc(self.conv(observations))

    @property
    def features_dim(self) -> int:
        return self._features_dim

# =========================================
# Classe do Ambiente Personalizado do Gym
# =========================================

class RobotEnv(gym.Env):
    """
    Ambiente personalizado para o robô.
    Integra dados da câmera e do LIDAR para treinamento com PPO.
    """
    def __init__(self, frame_queue, lidar_queue):
        super(RobotEnv, self).__init__()

        # Definição dos espaços de ação e observação
        # Observação: Imagem (120, 160, 1) + LIDAR (120, 3)
        self.camera_shape = (120, 160, 1)
        self.lidar_size = 360  # Número total de pontos do LIDAR

        # Espaço de observação combinado
        self.observation_space = spaces.Box(low=0.0, high=1.0, 
                                            shape=(self.camera_shape[0], self.camera_shape[1], self.camera_shape[2] + 3),
                                            dtype=np.float32)

        # Espaço de ação
        self.action_space = spaces.Discrete(4)  # 4 ações: frente, trás, esquerda, direita

        # Inicializar variáveis de estado
        self.current_observation = np.zeros((self.camera_shape[0], self.camera_shape[1], self.camera_shape[2] + 3), dtype=np.float32)
        self.done = False
        self.step_count = 0
        self.max_steps = 1000  # Número máximo de passos por episódio

        # Posições (exemplo simplificado)
        self.current_position = np.array([0.0, 0.0])
        self.target_position = np.array([10.0, 10.0])  # Defina o objetivo

        # Filas para frames e LIDAR
        self.frame_queue = frame_queue
        self.lidar_queue = lidar_queue

        # Variáveis para gerenciar ações
        self.current_action = None
        self.action_remaining_steps = 0
        self.action_duration_steps = {
            0: 20,  # Frente: 1 segundo (assumindo 20 FPS)
            1: 20,  # Trás: 1 segundo
            2: 20,  # Esquerda: 1 segundo
            3: 20,  # Direita: 1 segundo
        }

        # Configurar o logger para TensorBoard
        self.logger = configure("./ppo_robot_tensorboard/", ["stdout", "tensorboard"])
        self.set_logger()

    def set_logger(self):
        """
        Configura o logger do ambiente.
        """
        self.logger.set_level(0)  # Define o nível de logging

    def reset(self):
        """
        Reseta o ambiente para um estado inicial.
        """
        self.done = False
        self.step_count = 0
        self.current_observation = np.zeros((self.camera_shape[0], self.camera_shape[1], self.camera_shape[2] + 3), dtype=np.float32)
        self.current_position = np.array([0.0, 0.0])
        self.current_action = None
        self.action_remaining_steps = 0
        return self.current_observation

    def get_camera_frame(self):
        """
        Função para obter e pré-processar o frame da câmera do robô.
        """
        try:
            frame = self.frame_queue.get_nowait()
            processed_frame = preprocess_observation(frame)
            return processed_frame
        except Empty:
            # Se não houver frames disponíveis, retornar uma imagem preta
            return np.zeros((self.camera_shape[0], self.camera_shape[1], self.camera_shape[2]), dtype=np.float32)

    def get_lidar_frame(self):
        """
        Função para obter e pré-processar os dados do LIDAR do robô.
        """
        try:
            lidar_data = self.lidar_queue.get_nowait()
            # Se os dados já estiverem processados, retorná-los diretamente
            if isinstance(lidar_data, np.ndarray):
                return lidar_data
            processed_lidar = preprocess_lidar(lidar_data, self.lidar_size)
            return processed_lidar
        except Empty:
            # Se não houver dados disponíveis, retornar zeros
            return np.zeros((120, 3), dtype=np.float32)

    def calculate_reward(self, observation, current_position, target_position):
        """
        Calcula a recompensa baseada na observação e na posição atual do robô.

        Parâmetros:
        - observation: Frame atual da câmera pré-processado.
        - current_position: Posição atual do robô.
        - target_position: Posição alvo para o robô alcançar.

        Retorna:
        - reward: Valor da recompensa.
        """
        # Detectar bordas usando Canny
        edges = cv2.Canny((observation[:, :, 0] * 255).astype(np.uint8), 50, 150)
        # Contar o número de bordas detectadas
        num_edges = np.sum(edges > 0)

        # Recompensa por evitar obstáculos
        if num_edges > 1000:
            reward = -1.0  # Penalização por obstáculo
        else:
            reward = 1.0  # Recompensa por navegação sem obstáculos

        # Recompensa adicional por se aproximar do objetivo
        distance = np.linalg.norm(current_position - target_position)
        reward += -0.01 * distance  # Penalização proporcional à distância

        # Recompensa grande ao alcançar o objetivo
        if distance < 1.0:
            reward += 100.0

        return reward

    def check_done(self, observation, current_position, target_position):
        """
        Verifica se o episódio terminou com base na observação e na posição.

        Parâmetros:
        - observation: Frame atual da câmera pré-processado.
        - current_position: Posição atual do robô.
        - target_position: Posição alvo para o robô alcançar.

        Retorna:
        - done: Booleano indicando se o episódio terminou.
        """
        # Detectar bordas usando Canny
        edges = cv2.Canny((observation[:, :, 0] * 255).astype(np.uint8), 50, 150)
        # Contar o número de bordas detectadas
        num_edges = np.sum(edges > 0)

        # Termina o episódio se detectar muitos obstáculos
        if num_edges > 1500:
            logging.info("Episódio terminado: Obstáculo detectado.")
            return True  # Episódio termina devido a obstáculo

        # Termina o episódio se alcançar o objetivo
        distance = np.linalg.norm(current_position - target_position)
        if distance < 1.0:
            logging.info("Episódio terminado: Objetivo alcançado.")
            return True  # Episódio termina ao alcançar o objetivo

        # Termina o episódio após um número máximo de passos
        if self.step_count >= self.max_steps:
            logging.info("Episódio terminado: Número máximo de passos atingido.")
            return True

        return False

    def step(self, action):
        """
        Executa uma ação e retorna a nova observação, recompensa, done e info.

        Parâmetro:
        - action: Ação a ser executada (0: frente, 1: trás, 2: esquerda, 3: direita).

        Retorna:
        - observation: Nova observação após a ação.
        - reward: Recompensa obtida.
        - done: Booleano indicando se o episódio terminou.
        - info: Informações adicionais (dicionário vazio neste caso).
        """
        if self.done:
            return self.reset(), 0, self.done, {}

        if self.action_remaining_steps > 0:
            # Continuação da ação atual sem enviar novos comandos
            logging.debug(f"Executando ação em progresso: {self.current_action}, passos restantes: {self.action_remaining_steps}")

            self.action_remaining_steps -= 1

            # Obter observação da câmera
            camera_observation = self.get_camera_frame()

            # Obter observação do LIDAR
            lidar_observation = self.get_lidar_frame()

            # Combinar observações
            lidar_observation_expanded = lidar_observation.reshape(120, 3)
            lidar_observation_expanded = np.repeat(lidar_observation_expanded[:, np.newaxis, :], self.camera_shape[1], axis=1)  # (120,160,3)

            # Verificar formas das observações para depuração
            logging.debug(f"Forma da observação da câmera: {camera_observation.shape}")
            logging.debug(f"Forma da observação do LIDAR após a expansão: {lidar_observation_expanded.shape}")

            # Concatenar com a observação da câmera ao longo do eixo dos canais
            try:
                self.current_observation = np.concatenate((camera_observation, lidar_observation_expanded), axis=2)  # (120,160,4)
            except ValueError as e:
                logging.error(f"Erro na concatenação das observações: {e}")
                # Retornar uma observação padrão para evitar falhas
                self.current_observation = np.zeros((self.camera_shape[0], self.camera_shape[1], self.camera_shape[2] + 3), dtype=np.float32)
                return self.current_observation, 0, True, {}

            # Atualizar posição (exemplo simplificado)
            self.current_position += np.array([
                0.1 * (self.current_action == 0) - 0.1 * (self.current_action == 1),
                0.1 * (self.current_action == 2) - 0.1 * (self.current_action == 3)
            ])

            # Calcular recompensa
            reward = self.calculate_reward(camera_observation, self.current_position, self.target_position)

            # Registrar métricas para TensorBoard
            self.logger.record("rewards/reward", reward)
            self.logger.record("distance/distance_to_goal", np.linalg.norm(self.current_position - self.target_position))
            self.logger.record("metrics/num_edges", np.sum(cv2.Canny((camera_observation[:, :, 0] * 255).astype(np.uint8), 50, 150) > 0))

            # Incrementar contador de passos
            self.step_count += 1

            # Verificar condição de término
            self.done = self.check_done(camera_observation, self.current_position, self.target_position)

            return self.current_observation, reward, self.done, {}
        
        else:
            # Nenhuma ação está em execução, processar nova ação
            logging.debug(f"Recebendo nova ação: {action}")

            # Definir a ação atual e a duração
            self.current_action = action
            self.action_remaining_steps = self.action_duration_steps.get(action, 20)  # Default para 1 segundo (20 passos)

            # Executar a ação imediatamente
            if self.current_action == 0:
                send_move_command(1, 0, 0)  # Andar para frente
            elif self.current_action == 1:
                send_move_command(-1, 0, 0)  # Andar para trás
            elif self.current_action == 2:
                send_move_command(0, 0, 1)  # Rotacionar para a esquerda
            elif self.current_action == 3:
                send_move_command(0, 0, -1)  # Rotacionar para a direita

            # Decrementar o contador de passos
            self.action_remaining_steps -= 1

            # Obter observação da câmera
            camera_observation = self.get_camera_frame()

            # Obter observação do LIDAR
            lidar_observation = self.get_lidar_frame()

            # Combinar observações
            lidar_observation_expanded = lidar_observation.reshape(120, 3)
            lidar_observation_expanded = np.repeat(lidar_observation_expanded[:, np.newaxis, :], self.camera_shape[1], axis=1)  # (120,160,3)

            # Verificar formas das observações para depuração
            logging.debug(f"Forma da observação da câmera: {camera_observation.shape}")
            logging.debug(f"Forma da observação do LIDAR após a expansão: {lidar_observation_expanded.shape}")

            # Concatenar com a observação da câmera ao longo do eixo dos canais
            try:
                self.current_observation = np.concatenate((camera_observation, lidar_observation_expanded), axis=2)  # (120,160,4)
            except ValueError as e:
                logging.error(f"Erro na concatenação das observações: {e}")
                # Retornar uma observação padrão para evitar falhas
                self.current_observation = np.zeros((self.camera_shape[0], self.camera_shape[1], self.camera_shape[2] + 3), dtype=np.float32)
                return self.current_observation, 0, True, {}

            # Atualizar posição (exemplo simplificado)
            self.current_position += np.array([
                0.1 * (self.current_action == 0) - 0.1 * (self.current_action == 1),
                0.1 * (self.current_action == 2) - 0.1 * (self.current_action == 3)
            ])

            # Calcular recompensa
            reward = self.calculate_reward(camera_observation, self.current_position, self.target_position)

            # Registrar métricas para TensorBoard
            self.logger.record("rewards/reward", reward)
            self.logger.record("distance/distance_to_goal", np.linalg.norm(self.current_position - self.target_position))
            self.logger.record("metrics/num_edges", np.sum(cv2.Canny((camera_observation[:, :, 0] * 255).astype(np.uint8), 50, 150) > 0))

            # Incrementar contador de passos
            self.step_count += 1

            # Verificar condição de término
            self.done = self.check_done(camera_observation, self.current_position, self.target_position)

            return self.current_observation, reward, self.done, {}

# =========================================
# Função para Treinar o Modelo PPO
# =========================================

def train_model():
    """
    Inicializa o ambiente, configura o modelo PPO e inicia o treinamento.
    """
    # Inicializar o ambiente personalizado com filas de frames e LIDAR
    env = RobotEnv(frame_queue, lidar_queue)
    env = DummyVecEnv([lambda: env])

    # Configurar o logger para incluir stdout e tensorboard
    new_logger = configure("./ppo_robot_tensorboard/", ["stdout", "tensorboard"])
    env.envs[0].logger = new_logger

    # Callback para salvar o modelo a cada 10k timesteps
    checkpoint_callback = CheckpointCallback(save_freq=10000, save_path='./models/',
                                             name_prefix='ppo_robot')

    # Definir os argumentos da política para uma CNN personalizada
    policy_kwargs = dict(
        features_extractor_class=CustomCNN,  # Classe personalizada definida acima
        features_extractor_kwargs=dict(features_dim=512),
    )

    # Instanciar o modelo PPO com o callback e a política personalizada
    model = PPO("CnnPolicy", env, verbose=1, tensorboard_log="./ppo_robot_tensorboard/",
                policy_kwargs=policy_kwargs)

    # Treinar o modelo
    logging.info("Iniciando o treinamento do modelo PPO...")
    try:
        model.learn(total_timesteps=100000, callback=checkpoint_callback)  # Ajuste o número de timesteps conforme necessário
    except Exception as e:
        logging.error(f"Erro durante o treinamento: {e}")
    finally:
        # Salvar o modelo treinado
        model.save("ppo_robot")
        logging.info("Modelo treinado e salvo como 'ppo_robot.zip'")

        # Encerrar o loop asyncio após o treinamento
        loop.call_soon_threadsafe(loop.stop)
        asyncio_thread.join()

# =========================================
# Função para Exibir Frames na Janela Pygame
# =========================================

def display_frames():
    """
    Exibe os frames capturados da câmera na janela do Pygame.
    """
    try:
        frame = frame_queue.get_nowait()
        frame = cv2.resize(frame, (160, 120))  # Redimensionar para corresponder ao tamanho esperado
        frame_surface = pygame.surfarray.make_surface(frame)
        frame_surface = pygame.transform.scale(frame_surface, (640, 480))  # Redimensionar para caber na janela
        screen.blit(frame_surface, (0, 0))
    except Empty:
        # Mostrar uma tela preta se não houver frames
        screen.fill((0, 0, 0))  # Preencher com preto

# =========================================
# Execução Principal
# =========================================

if __name__ == "__main__":
    try:
        # Iniciar o treinamento em uma thread separada para não bloquear o loop principal
        training_thread = threading.Thread(target=train_model, daemon=True)
        training_thread.start()

        # Loop principal para monitoramento visual com Pygame
        while training_thread.is_alive():
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    # Encerrar o treinamento e o script
                    logging.info("Encerrando o treinamento via Pygame.")
                    training_thread.join(timeout=1)
                    raise KeyboardInterrupt

            # Exibir frame na janela (opcional)
            display_frames()

            pygame.display.update()

    except KeyboardInterrupt:
        logging.info("Encerrando o programa pelo usuário.")

    finally:
        # Encerrando o loop asyncio e o Pygame
        loop.call_soon_threadsafe(loop.stop)
        asyncio_thread.join()
        pygame.quit()
        logging.info("Programa encerrado.")

# tensorboard --logdir=./ppo_robot_tensorboard/