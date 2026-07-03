import os
import sys
import time
import tempfile
import requests

try:
    import sounddevice as sd
    import soundfile as sf
    import pygame
except ImportError:
    print("[Simulator]: Installing required audio packages (sounddevice, soundfile, pygame, requests)...")
    os.system("pip install sounddevice soundfile pygame requests")
    import sounddevice as sd
    import soundfile as sf
    import pygame

# Initialize pygame mixer for audio playback
pygame.mixer.init()

API_URL = "http://localhost:8001/api/hardware_chat"
SAMPLE_RATE = 16000
CHANNELS = 1

def play_mp3_bytes(audio_bytes):
    if not audio_bytes or len(audio_bytes) < 100:
        return
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            fp.write(audio_bytes)
            temp_path = fp.name
            
        print("[Speaker Output]: Playing voice response...")
        if pygame.mixer.get_init():
            pygame.mixer.quit()
        pygame.mixer.init(frequency=24000)
        pygame.mixer.music.load(temp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.music.unload()
        pygame.mixer.quit()
        try:
            os.remove(temp_path)
        except Exception:
            pass
    except Exception as e:
        print(f"[Audio Playback Error]: {e}")

def record_audio(duration_sec=6.0):
    print(f"\n[Recording]: Listening for {duration_sec} seconds... Speak now!")
    recording = sd.rec(int(duration_sec * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16')
    sd.wait()
    print("[Recording]: Finished recording.")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as fp:
        sf.write(fp.name, recording, SAMPLE_RATE)
        return fp.name

def main():
    print("="*60)
    print("   HEADLESS HARDWARE SPEAKER TERMINAL SIMULATOR")
    print("="*60)
    print("Make sure hardware_agent.py is running in another terminal on port 8001!")
    
    # Auto-reset hardware state to standby on startup
    try:
        requests.post("http://localhost:8001/api/hardware_reset")
        print("[Simulator]: Hardware server automatically reset to Standby Mode.")
    except Exception:
        pass

    print("Press ENTER to record your voice and send to speaker backend.")
    print("Type 'r' and ENTER to reset speaker back to Standby Mode.")
    print("Type 'q' and ENTER to quit.")
    print("="*60)

    while True:
        try:
            user_input = input("\n[Press ENTER to talk / 'r' reset / 'q' quit]: ").strip().lower()
            if user_input == 'q':
                print("Exiting simulator.")
                break
            if user_input == 'r':
                requests.post("http://localhost:8001/api/hardware_reset")
                print("[Simulator]: Speaker reset back to Standby Mode! Say 'Hey Gopu' to start.")
                continue
                
            wav_path = record_audio(duration_sec=6.0)
            
            print("[Network]: Sending audio to headless hardware server...")
            with open(wav_path, 'rb') as f:
                files = {'audio': ('recording.wav', f, 'audio/wav')}
                response = requests.post(API_URL, files=files)
                
            try:
                os.remove(wav_path)
            except Exception:
                pass
                
            if response.status_code == 204:
                print("[Server]: 204 No Content (Silence / Not Wake Word)")
                continue
                
            if response.status_code == 200:
                reply_text = urllib.parse.unquote(response.headers.get("X-Agent-Reply", ""))
                hw_state = response.headers.get("X-Hardware-State", "unknown")
                print(f"[Speaker State ({hw_state})]: {reply_text}")
                
                # Play the speaker's audio output through PC speakers
                play_mp3_bytes(response.content)
            else:
                print(f"[Server Error]: HTTP {response.status_code}")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[Error]: {e}")
            time.sleep(1)

if __name__ == "__main__":
    import urllib.parse
    main()
