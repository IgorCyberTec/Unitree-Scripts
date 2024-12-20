import asyncio
import threading
import tkinter as tk
from math import atan2, cos, sin, sqrt
from go2_webrtc_driver.constants import RTC_TOPIC
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
import json
import subprocess  # Import necessário para executar o script
import os  # Import para manipulação de paths

# Atualização do dicionário SPORT_CMD
SPORT_CMD = {
    "BalanceStand": 1002,
    "BackFlip": 1044,
    "BodyHeight": 1013,
    "Bound": 1304,
    "ContinuousGait": 1019,
    "Content": 1020,
    "CrossStep": 1302,
    "Dance1": 1022,
    "Dance2": 1023,
    "Damp": 1001,
    "EconomicGait": 1035,
    "Euler": 1007,
    "FingerHeart": 1036,
    "FootRaiseHeight": 1014,
    "FreeWalk": 1045,
    "FrontFlip": 1030,
    "FrontJump": 1031,
    "FrontPounce": 1032,
    "GetBodyHeight": 1024,
    "GetFootRaiseHeight": 1025,
    "GetSpeedLevel": 1026,
    "GetState": 1034,
    "Handstand": 1301,
    "Hello": 1016,
    "LeadFollow": 1045,
    "LeftFlip": 1042,
    "MoonWalk": 1305,
    "Move": 1008,
    "OnesidedStep": 1303,
    "Pose": 1028,
    "RecoveryStand": 1006,
    "RightFlip": 1043,
    "RiseSit": 1010,
    "Scrape": 1029,
    "Sit": 1009,
    "SpeedLevel": 1015,
    "StandDown": 1005,
    "StandOut": 1039,
    "StandUp": 1004,
    "StopMove": 1003,
    "Stretch": 1017,
    "SwitchGait": 1011,
    "SwitchJoystick": 1027,
    "TrajectoryFollow": 1018,
    "Trigger": 1012,
    "Wallow": 1021,
    "WiggleHips": 1033,
}

# Configuração da conexão WebRTC
conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)

# Função para enviar comandos
async def send_command(api_id, parameter=None):
    print(f"Enviando comando: {api_id}, com parâmetros: {parameter}")
    try:
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"],
            {"api_id": api_id, "parameter": parameter if parameter else {}}
        )
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

# Classe do Joystick Virtual
class VirtualJoystick(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Joystick Virtual para Robô")
        self.geometry("600x800")
        self.resizable(False, False)

        # Frame principal
        self.main_frame = tk.Frame(self)
        self.main_frame.pack(expand=True)

        # Configurações do Joystick
        self.joystick_frame = tk.Frame(self.main_frame)
        self.joystick_frame.pack(pady=20)

        self.joystick_radius = 100
        self.knob_radius = 40
        self.center_x = self.joystick_radius
        self.center_y = self.joystick_radius
        self.knob_x = self.center_x
        self.knob_y = self.center_y
        self.active = False

        # Canvas para o joystick
        self.canvas = tk.Canvas(self.joystick_frame, width=2*self.joystick_radius, height=2*self.joystick_radius, highlightthickness=0)
        self.canvas.pack()

        # Desenhar a base do joystick
        self.canvas.create_oval(
            self.center_x - self.joystick_radius,
            self.center_y - self.joystick_radius,
            self.center_x + self.joystick_radius,
            self.center_y + self.joystick_radius,
            fill="gray", outline=""
        )

        # Desenhar o knob do joystick
        self.knob = self.canvas.create_oval(
            self.knob_x - self.knob_radius,
            self.knob_y - self.knob_radius,
            self.knob_x + self.knob_radius,
            self.knob_y + self.knob_radius,
            fill="blue", outline=""
        )

        # Bind de eventos do mouse
        self.canvas.tag_bind(self.knob, "<ButtonPress-1>", self.on_press)
        self.canvas.tag_bind(self.knob, "<B1-Motion>", self.on_move)
        self.canvas.tag_bind(self.knob, "<ButtonRelease-1>", self.on_release)

        # Frame para os botões de ação
        self.action_frame = tk.Frame(self.main_frame)
        self.action_frame.pack(pady=20)

        # Adicionar todos os botões de comando
        self.add_action_buttons()

        # Botão para executar o Recon.py
        self.recon_button = tk.Button(self.main_frame, text="Reconhecimento de Gestos", width=30, command=self.toggle_recon)
        self.recon_button.pack(pady=10)

        # Label para exibir o status
        self.status_label = tk.Label(self.main_frame, text="Pronto", font=("Arial", 14))
        self.status_label.pack(pady=10)

        # Variável para armazenar o processo do Recon.py
        self.recon_process = None

    def add_action_buttons(self):
        # Organizar os botões em uma grade
        buttons_per_row = 4
        row = 0
        column = 0

        for cmd_name in sorted(SPORT_CMD.keys()):
            api_id = SPORT_CMD[cmd_name]
            # Formatar o nome do comando para exibição
            display_name = cmd_name.replace("_", " ").capitalize()
            button = tk.Button(self.action_frame, text=display_name, width=15,
                               command=lambda api_id=api_id: self.on_action_press(api_id))
            button.grid(row=row, column=column, padx=5, pady=5)
            column += 1
            if column >= buttons_per_row:
                column = 0
                row += 1

    def on_press(self, event):
        self.active = True

    def on_move(self, event):
        if not self.active:
            return

        # Coordenadas relativas ao canvas
        dx = event.x - self.center_x
        dy = event.y - self.center_y
        distance = sqrt(dx**2 + dy**2)

        if distance > self.joystick_radius - self.knob_radius:
            angle = atan2(dy, dx)
            dx = (self.joystick_radius - self.knob_radius) * cos(angle)
            dy = (self.joystick_radius - self.knob_radius) * sin(angle)

        new_x = self.center_x + dx
        new_y = self.center_y + dy

        # Mover o knob
        self.canvas.coords(
            self.knob,
            new_x - self.knob_radius,
            new_y - self.knob_radius,
            new_x + self.knob_radius,
            new_y + self.knob_radius
        )

        # Normalizar os valores entre -1 e 1
        normalized_x = dx / (self.joystick_radius - self.knob_radius)
        normalized_y = dy / (self.joystick_radius - self.knob_radius)

        # Inverter o sinal de normalized_y
        normalized_y = -normalized_y

        # Enviar comando de movimento
        send_move_command(normalized_y, 0, -normalized_x)
        self.status_label.config(text=f"Movendo: x={normalized_x:.2f}, y={normalized_y:.2f}")

    def on_release(self, event):
        self.active = False

        # Resetar a posição do knob ao centro
        self.canvas.coords(
            self.knob,
            self.center_x - self.knob_radius,
            self.center_y - self.knob_radius,
            self.center_x + self.knob_radius,
            self.center_y + self.knob_radius
        )

        # Enviar comando para parar o robô
        send_move_command(0, 0, 0)
        self.status_label.config(text="Parado")

    def on_action_press(self, api_id):
        send_action_command(api_id)
        acao = self.get_action_name(api_id)
        self.status_label.config(text=f"Executando: {acao}")

    def get_action_name(self, api_id):
        for key, value in SPORT_CMD.items():
            if value == api_id:
                # Formatar o nome da ação
                return key.replace("_", " ").capitalize()
        return "Ação Desconhecida"

    def toggle_recon(self):
        if self.recon_process is None or self.recon_process.poll() is not None:
            # Não está rodando, então inicia
            self.start_recon()
        else:
            # Está rodando, então para
            self.stop_recon()

    def start_recon(self):
        # Caminho absoluto para o script Recon.py
        script_path = os.path.abspath("kaircode/Outros/Recon.py")
        # Iniciar o subprocesso
        self.recon_process = subprocess.Popen(["python3", script_path])
        self.status_label.config(text="Reconhecimento de Gestos Ativado")
        self.recon_button.config(text="Desativar Reconhecimento de Gestos")

    def stop_recon(self):
        if self.recon_process:
            self.recon_process.terminate()
            self.recon_process.wait()
            self.recon_process = None
            self.status_label.config(text="Reconhecimento de Gestos Desativado")
            self.recon_button.config(text="Reconhecimento de Gestos")

    def on_close(self):
        # Se o Recon.py estiver rodando, pará-lo
        if self.recon_process:
            self.recon_process.terminate()
            self.recon_process.wait()
            self.recon_process = None
        self.destroy()
        loop.call_soon_threadsafe(loop.stop)
        asyncio_thread.join()

def run_asyncio_loop(loop):
    asyncio.set_event_loop(loop)
    async def setup():
        try:
            await conn.connect()
            # Configuração inicial do robô
            response = await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["MOTION_SWITCHER"],
                {"api_id": 1001}
            )
            if response['data']['header']['status']['code'] == 0:
                data = json.loads(response['data']['data'])
                current_motion_switcher_mode = data['name']
                print(f"Modo de movimento atual: {current_motion_switcher_mode}")
            if current_motion_switcher_mode != "normal":
                await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["MOTION_SWITCHER"],
                    {"api_id": 1002, "parameter": {"name": "normal"}}
                )
        except Exception as e:
            print(f"Erro na conexão: {e}")
    loop.run_until_complete(setup())
    loop.run_forever()

if __name__ == "__main__":
    # Inicialização do asyncio em um thread separado
    loop = asyncio.new_event_loop()
    asyncio_thread = threading.Thread(target=run_asyncio_loop, args=(loop,), daemon=True)
    asyncio_thread.start()

    app = VirtualJoystick()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
