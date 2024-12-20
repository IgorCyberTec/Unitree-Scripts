import asyncio
import threading
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from kivy.properties import ObjectProperty
from kivy.clock import Clock
from kivy.config import Config
from kivy.core.window import Window

from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
import json

# Configuração da conexão WebRTC
conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)

# Configuração do tamanho da janela (opcional)
Window.size = (800, 600)

# Inicialização do asyncio em um thread separado
def run_asyncio_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

loop = asyncio.new_event_loop()
asyncio_thread = threading.Thread(target=run_asyncio_loop, args=(loop,), daemon=True)
asyncio_thread.start()

# Função para enviar comandos
async def send_command(api_id, parameter=None):
    print(f"Enviando comando: {api_id}, com parâmetros: {parameter}")
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        {"api_id": api_id, "parameter": parameter if parameter else {}}
    )

def send_move_command(x, y, z):
    asyncio.run_coroutine_threadsafe(
        send_command(SPORT_CMD["Move"], {"x": x, "y": y, "z": z}), loop
    )

def send_action_command(api_id):
    asyncio.run_coroutine_threadsafe(
        send_command(api_id), loop
    )

# Widget do Joystick
class Joystick(Widget):
    joystick_pad = ObjectProperty(None)
    joystick = ObjectProperty(None)
    max_distance = 100  # Distância máxima do joystick

    def __init__(self, **kwargs):
        super(Joystick, self).__init__(**kwargs)
        self.center_x = self.joystick_pad.center_x
        self.center_y = self.joystick_pad.center_y
        self.bind(size=self._update_joystick)
        self.active = False

    def _update_joystick(self, *args):
        self.center_x = self.joystick_pad.center_x
        self.center_y = self.joystick_pad.center_y
        self.joystick.center = self.joystick_pad.center

    def on_touch_down(self, touch):
        if self.joystick_pad.collide_point(touch.x, touch.y):
            self.active = True
            self.move_joystick(touch)
            return True
        return super(Joystick, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.active:
            self.move_joystick(touch)
            return True
        return super(Joystick, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        if self.active:
            self.joystick.center = self.joystick_pad.center
            self.active = False
            # Enviar comando para parar
            send_move_command(0, 0, 0)
            return True
        return super(Joystick, self).on_touch_up(touch)

    def move_joystick(self, touch):
        dx = touch.x - self.joystick_pad.center_x
        dy = touch.y - self.joystick_pad.center_y
        distance = (dx**2 + dy**2) ** 0.5
        angle = atan2(dy, dx)

        if distance > self.max_distance:
            distance = self.max_distance

        new_x = self.joystick_pad.center_x + distance * cos(angle)
        new_y = self.joystick_pad.center_y + distance * sin(angle)

        self.joystick.center = (new_x, new_y)

        # Normalizar os valores entre -1 e 1
        normalized_x = dx / self.max_distance
        normalized_y = dy / self.max_distance

        # Enviar comando de movimento
        send_move_command(normalized_y, 0, -normalized_x)

# Importar funções matemáticas
from math import atan2, sin, cos

# Layout principal
class JoystickLayout(FloatLayout):
    pass

# Aplicativo principal
class VirtualJoystickApp(App):
    def build(self):
        # Carregar o layout
        self.root = JoystickLayout()
        # Iniciar a conexão
        Clock.schedule_once(self.setup_connection, 1)
        return self.root

    async def setup_connection_async(self):
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

    def setup_connection(self, dt):
        asyncio.run_coroutine_threadsafe(self.setup_connection_async(), loop)

    def on_stop(self):
        loop.call_soon_threadsafe(loop.stop)
        asyncio_thread.join()

if __name__ == '__main__':
    VirtualJoystickApp().run()
