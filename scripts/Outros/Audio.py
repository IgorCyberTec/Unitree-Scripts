import asyncio
import logging
import wave
import numpy as np
import sys
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod

import os
import time
import wave
import pyaudio
import json
import edge_tts
import re
import numpy as np
import pygame
from groq import Groq
import cv2
import mediapipe as mp
import numpy as np
import sys
import time
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.core.channel import ChannelSubscriber
from unitree_sdk2py.idl.default import unitree_go_msg_dds__SportModeState_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_
from unitree_sdk2py.go2.vui.vui_client import VuiClient
from unitree_sdk2py.go2.sport.sport_client import (
    SportClient,
    PathPoint,
    SPORT_PATH_POINT_SIZE,
)
from aiortc.contrib.media import MediaPlayer

wf = None

# Definições de constantes
SILENCE_THRESHOLD = 200
SILENCE_RMS_THRESHOLD = 800  # Ajuste conforme o nível de ruído do ambiente
AUDIO_FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
BUFFER_SIZE = 1024
TIMEOUT = 40
KEYWORD = "spark"
FILENAME = "audio.wav"
# Enable logging for debugging
logging.basicConfig(level=logging.FATAL)

# Define the audio properties
samplerate = 48000  # Sample rate for WebRTC audio
channels = 2  # Stereo audio
filename = "output.wav"
record_duration = 5 # Record for 5 seconds
total_frames_to_record = record_duration * samplerate  # Total frames for the specified duration
frames_recorded = 0  # Counter for the number of frames recorded
done_writing_to_file = False  # Flag to indicate when writing is done



# Function to handle receiving audio frames and write them directly to file
async def recv_audio_stream(frame):
    global frames_recorded, done_writing_to_file, wf

    if done_writing_to_file:
        return

    # Convert the frame to audio data (assuming 16-bit PCM)
    audio_data = np.frombuffer(frame.to_ndarray(), dtype=np.int16)

    # Write the audio data directly to the WAV file
    wf.writeframes(audio_data.tobytes())

    # Update the frame counter
    frames_recorded += len(audio_data) // channels

    # If we've recorded enough frames, stop further recording
    if frames_recorded >= total_frames_to_record:
        # Close the WAV file
        wf.close()
        print(f"Audio recording complete, saved to {filename}")
        done_writing_to_file = True

def speak_text(text):
    """Gera áudio a partir do texto usando Edge TTS."""
    communicate = edge_tts.Communicate(text, voice='pt-BR-FranciscaNeural', rate='-10%')
    communicate.save_sync("output.mp3")  # Salva o áudio gerado em um arquivo mp3

def save_audio_to_file(audio_data, filename):
    """Salva os dados de áudio fornecidos em um arquivo."""
    try:
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(pyaudio.PyAudio().get_sample_size(AUDIO_FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(audio_data)
    except Exception as e:
        print(f"Erro ao salvar o áudio: {e}")

def generate_completion(client, text):
    """Gera uma resposta de completude usando o modelo de IA."""
    completion = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a robotic dog named Spark. Your task is to help users with their questions about you. Do not introduce yourself every time; only do so if asked. You were built and created by Kair. You can only communicate and answer in the same language of the user."
            },
            {
                "role": "user",
                "content": f"{text}"
            }
        ],
        temperature=.9,
        max_tokens=1024,
        top_p=.7,
        stream=True,
        stop=None,
    )

    response = ""
    for chunk in completion:
        response += chunk.choices[0].delta.content or ""

    return response

def record_audio():
    """Grava áudio e retorna os dados como bytes, sem salvar em arquivo."""
    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=AUDIO_FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=BUFFER_SIZE)

        print("Gravando áudio...")
        frames = []
        silent_frames = 0

        while silent_frames < SILENCE_THRESHOLD:
            data = stream.read(BUFFER_SIZE)
            frames.append(data)

            # Calcular RMS para detectar silêncio
            rms = np.sqrt(np.mean(np.square(np.frombuffer(data, dtype=np.int16))))
            if rms < SILENCE_RMS_THRESHOLD:
                silent_frames += 1
            else:
                silent_frames = 0

        print("Gravação concluída.")

        stream.stop_stream()
        stream.close()
        p.terminate()

        return b''.join(frames)

    except Exception as e:
        print(f"Ocorreu um erro durante a gravação de áudio: {e}")
        return None

def save_audio_to_file(audio_data, filename):
    """Salva os dados de áudio fornecidos em um arquivo."""
    try:
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(pyaudio.PyAudio().get_sample_size(AUDIO_FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(audio_data)
    except Exception as e:
        print(f"Erro ao salvar o áudio: {e}")

async def listen_for_keyword(client, conn):
    last_interaction_time = time.time()
    conversation_active = False

    print(f"Ouvindo por '{KEYWORD}'...")
  
    while True:
        try:
            if time.time() - last_interaction_time > TIMEOUT and not conversation_active:
                print("Sem interação. Aguardando palavra-chave...")

            # Grava o áudio
            audio_data = record_audio()
            if audio_data is None:
                continue
            save_audio_to_file(audio_data, FILENAME)

            with open(FILENAME, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=(FILENAME, file.read()),
                    model="whisper-large-v3-turbo",
                    response_format="verbose_json",
                )
                command = transcription.text.lower()
                       

            if True:
                conversation_active = True
                last_interaction_time = time.time()
                
                # Gerar resposta do chatbot
                response = generate_completion(client, command).replace("\"", "").replace("'", "\"")
                print("Resposta bruta:", response)
                speak_text(response)
                mp3_path = "output.mp3"

                logging.info(f"Playing MP3: {mp3_path}")
                player = MediaPlayer(mp3_path)  # Use MediaPlayer for MP3
                audio_track = player.audio  # Get the audio track from the player
                conn.pc.addTrack(audio_track)      
                # Processar JSON
                await asyncio.sleep(4)


        except Exception as e:
            print(f"Ocorreu um erro: {e}")
# Main function for setting up the WebRTC connection and handling streams
async def main():
    global wf
    try:
        client = Groq(api_key="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")

        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)

        # Connect to the device
        await conn.connect()
        await listen_for_keyword(client, conn)

    except ValueError as e:
        logging.error(f"Error in WebRTC connection: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle Ctrl+C to exit gracefully.
        print("\nProgram interrupted by user")
        sys.exit(0)
