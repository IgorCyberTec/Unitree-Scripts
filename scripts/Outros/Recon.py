import cv2
import numpy as np

# Create an OpenCV window and display a blank image
height, width = 720, 1280  # Adjust the size as needed
img = np.zeros((height, width, 3), dtype=np.uint8)
cv2.imshow('Video', img)
cv2.waitKey(1)  # Ensure the window is created

import json

from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD
import asyncio
import logging
import threading
import time
from queue import Queue
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from aiortc import MediaStreamTrack
import cv2
import mediapipe as mp
import numpy as np

# Inicialização do MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2)
mp_draw = mp.solutions.drawing_utils

def normalizar_pontos(landmarks):
    # Centraliza e normaliza os pontos
    pontos = np.array([[lm.x, lm.y, lm.z] for lm in landmarks])
    centro = pontos[0]  # Ponto do punho
    pontos -= centro
    escala = np.linalg.norm(pontos, axis=1).max()
    pontos /= escala
    return pontos

def detectar_gesto(pontos):
    # Cálculo dos ângulos ou distâncias relevantes
    # Exemplo simplificado para detectar mão aberta
    dedos_estendidos = []
    margem = 0.1  # Margem de erro de 10%
    for id in [8, 12, 16, 20]:  # Pontas dos dedos
        # Verifica se o dedo está estendido
        if pontos[id][1] < (pontos[id - 2][1] * (1 + margem)):
            dedos_estendidos.append(True)
        else:
            dedos_estendidos.append(False)
    # Verifica o polegar
    if pontos[4][0] > (pontos[3][0] * (1 - margem)):
        dedos_estendidos.append(True)
    else:
        dedos_estendidos.append(False)

    # Reconhecimento dos gestos
    if all(dedos_estendidos):
        return 'open_hand'
    if dedos_estendidos[0] and dedos_estendidos[1] and not any(dedos_estendidos[2:]):
        return 'peace'
    if dedos_estendidos[0] and not any(dedos_estendidos[1:]):
        return 'finger'
    if dedos_estendidos[0] and dedos_estendidos[3] and not any([dedos_estendidos[1], dedos_estendidos[2], dedos_estendidos[4]]):
        return 'rock'
    if dedos_estendidos[4] and dedos_estendidos[0] and not any([dedos_estendidos[1], dedos_estendidos[2], dedos_estendidos[3]]):
        return 'heart'
    if dedos_estendidos[1] and not any([dedos_estendidos[0], dedos_estendidos[2], dedos_estendidos[3], dedos_estendidos[4]]):
        return 'middle'
    if dedos_estendidos[0] and dedos_estendidos[3] and dedos_estendidos[4] and not any([dedos_estendidos[1], dedos_estendidos[2]]):
        return 'spider'
    if dedos_estendidos[0] and dedos_estendidos[1] and dedos_estendidos[3] and not any([dedos_estendidos[2], dedos_estendidos[4]]):
        return 'stranger'
    if dedos_estendidos[0] and dedos_estendidos[1] and dedos_estendidos[3] and not any([dedos_estendidos[2], dedos_estendidos[4]]):
        return 'stranger'
    if not any(dedos_estendidos):
        return 'closed'
    return 'none'

# Enable logging for debugging
logging.basicConfig(level=logging.FATAL)


BREAK_TIME_OUT = 1.0  # Tempo em segundos

# Enable logging for debugging
logging.basicConfig(level=logging.FATAL)

async def main():
    frame_queue = Queue()
    breaked = False  # Flag para prevenir ações repetidas
    breaked_at = None

    # Choose a connection method (uncomment the correct one)
    # conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip="192.168.1.12")
    # conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, serialNumber="B42D20007BCAEG4")
    conn = Go2WebRTCConnection(WebRTCConnectionMethod.Remote, serialNumber="B42D4000O49AKA06", username="andre@glededu.com", password="Gie2309$")
    # conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)

    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        min_detection_confidence=0.7, min_tracking_confidence=0.7, max_num_hands=1
    )
    # Async function to receive video frames and put them in the queue
    async def recv_camera_stream(track: MediaStreamTrack):

        while True:
            frame = await track.recv()
            # Convert the frame to a NumPy array
            img = frame.to_ndarray(format="bgr24")
            frame_queue.put(img)

    # Movimento comando
    async def run():
        await conn.datachannel.pub_sub.publish_request_new(
                                RTC_TOPIC["SPORT_MOD"], 
                                {
                                    "api_id": SPORT_CMD["Move"],
                                    "parameter": {"x": 0.2, "y": 0, "z": 0}
                                }
                            )
    
    #run backwords
    async def back():
        await conn.datachannel.pub_sub.publish_request_new(
                                RTC_TOPIC["SPORT_MOD"], 
                                {
                                    "api_id": SPORT_CMD["Move"],
                                    "parameter": {"x": -0.2, "y": 0, "z": 0}
                                }
                            )
        
    async def stand():
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"], 
            {
                "api_id": 1002,
                "parameter": {"name": "ai"}
            }
        )
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], 
            {
                "api_id": SPORT_CMD["StandOut"],
                "parameter": {"data": True}
            }
        )

        await asyncio.sleep(5)

        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], 
            {
                "api_id": SPORT_CMD["StandOut"],
                "parameter": {"data": False}
            }
        )

        await conn.datachannel.pub_sub.publish_request_new(
                        RTC_TOPIC["MOTION_SWITCHER"], 
                        {
                            "api_id": 1002,
                            "parameter": {"name": "normal"}
                        }
                    )

    async def flip():
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"], 
            {
                "api_id": 1002,
                "parameter": {"name": "ai"}
            }
        )

        await conn.datachannel.pub_sub.publish_request_new(
             RTC_TOPIC["SPORT_MOD"], 
             {
                 "api_id": SPORT_CMD["BackFlip"],
                 "parameter": {"data": True}
             }
         )
        
        await conn.datachannel.pub_sub.publish_request_new(
                        RTC_TOPIC["MOTION_SWITCHER"], 
                        {
                            "api_id": 1002,
                            "parameter": {"name": "normal"}
                        }
                    )

    
    def run_asyncio_loop(loop):
        asyncio.set_event_loop(loop)
        async def setup():
            try:
                # Connect to the device
                await conn.connect()
                response = await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["MOTION_SWITCHER"], 
                    {"api_id": 1001}
                )

                if response['data']['header']['status']['code'] == 0:
                    data = json.loads(response['data']['data'])
                    current_motion_switcher_mode = data['name']
                    print(f"Current motion mode: {current_motion_switcher_mode}")

                # Switch to "normal" mode if not already
                if current_motion_switcher_mode != "normal":
                    print(f"Switching motion mode from {current_motion_switcher_mode} to 'normal'...")
                    await conn.datachannel.pub_sub.publish_request_new(
                        RTC_TOPIC["MOTION_SWITCHER"], 
                        {
                            "api_id": 1002,
                            "parameter": {"name": "normal"}
                        }
                    )
                    await asyncio.sleep(5)  # Wait while it stands up



                # Switch video channel on and start receiving video frames
                conn.video.switchVideoChannel(True)

                # Add callback to handle received video frames
                conn.video.add_track_callback(recv_camera_stream)
            except Exception as e:
                logging.error(f"Error in WebRTC connection: {e}")

        # Run the setup coroutine and then start the event loop
        loop.run_until_complete(setup())
        loop.run_forever()

    # Create a new event loop for the asyncio code
    loop = asyncio.new_event_loop()

    # Start the asyncio event loop in a separate thread
    asyncio_thread = threading.Thread(target=run_asyncio_loop, args=(loop,))
    asyncio_thread.start()
    # Start the asyncio event loop in a separate thread

    loop2 = asyncio.new_event_loop()
    th = threading.Thread(target=loop2.run_forever)
    th.start()
    try:
        while True:
            if not frame_queue.empty():
                img = frame_queue.get()
                print(f"Shape: {img.shape}, Dimensions: {img.ndim}, Type: {img.dtype}, Size: {img.size}")
                # Display the frame
                image_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                results = hands.process(image_rgb)

                print(breaked)
                if breaked and time.time() - breaked_at > 1:
                    breaked = False
                    
                # Desenhar landmarks da mão detectada e executar ações
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        mp.solutions.drawing_utils.draw_landmarks(
                            img, hand_landmarks, mp_hands.HAND_CONNECTIONS
                        )
                        pontos = normalizar_pontos(hand_landmarks.landmark)
                        gesto = detectar_gesto(pontos)
                        #print(gesto)
                        if gesto == "open_hand":
                            asyncio.run_coroutine_threadsafe(run(), loop2)
                            #await asyncio.sleep(3)
                        if gesto == 'closed':
                            asyncio.run_coroutine_threadsafe(back(), loop2)
                        if gesto == 'peace':
                            asyncio.run_coroutine_threadsafe(stand(), loop2)
                        if gesto == 'spider':
                            asyncio.run_coroutine_threadsafe(flip(), loop2)
                        '''if gesto == 'finger':
                            asyncio.run_coroutine_threadsafe(run(), loop2)
                        if gesto == 'heart':
                            asyncio.run_coroutine_threadsafe(run(), loop2)'''
                        breaked = True
                        breaked_at = time.time()

                cv2.imshow('Video', img)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            else:
                # Sleep briefly to prevent high CPU usage
                time.sleep(0.01)

        print("----------------------------- saiu do loop")
    finally:
        print("-----------------------------  safe")

        cv2.destroyAllWindows()
        # Stop the asyncio event loop
        loop.call_soon_threadsafe(loop.stop)
        loop2.call_soon_threadsafe(loop2.stop)
        asyncio_thread.join()
        th.join()


if __name__ == "__main__":
    asyncio.run(main())
