# Dr. Gopu - Headless Veterinary Smart Speaker Module

A standalone, voice-activated smart speaker backend built with FastAPI (Python). Designed to operate on embedded hardware (such as Raspberry Pi or headless servers) without requiring a graphical screen or video display. It provides real-time spoken veterinary triage and first-aid guidance in English, Telugu, and Hindi.

---

## Project Structure

- **`hardware_agent.py`**: Headless FastAPI server running on port `8001`. Handles state-based wake word detection, spoken language selection, speech-to-text (STT), LLM reasoning, and audio synthesis.
- **`simulate_speaker.py`**: Python terminal client that captures microphone input and plays back synthesized speaker audio through local speakers.

---

## Hardware Interaction Flow

The speaker operates across three distinct internal states:

1. **Standby Mode (State 0):** The speaker continuously listens for wake words (`Hey Gopu`, `Gopu`, `Namaste`).
2. **Language Selection (State 1):** Once awakened, the speaker prompts the user in three languages (*"For English say English. తెలుగు కోసం తెలుగు అని చెప్పండి. हिंदी के लिए हिंदी बोलिए."*).
3. **Active Clinical Consultation (State 2):** Performs structured medical intake, provides immediate supportive first-aid advice (e.g., hydration, bland diet, temperature monitoring), and recommends clinical veterinarian evaluation when necessary.

---

## Setup & Running Locally

### 1. Requirements & Dependencies
Install required audio and server packages:
```bash
pip install fastapi uvicorn requests edge-tts sounddevice soundfile pygame
```

### 2. Configure Environment Keys
Create a `.env` file in the parent or local directory containing your API credentials:
```env
DEEPGRAM_API_KEY="your_deepgram_api_key"
GROQ_API_KEY="your_groq_api_key"
```

### 3. Start the Headless Server
Run the hardware backend on port `8001`:
```bash
python hardware_agent.py
```
*(On Windows systems using multiple Python versions, use `py -3.11 hardware_agent.py`)*

### 4. Test Microphone Interaction
To interact with the running speaker server, open a second terminal and run:
```bash
python simulate_speaker.py
```

---

## Customizing Speech & Hardware Logic

- **Adjusting Recording Duration:** By default, `simulate_speaker.py` listens for `6.0` seconds per turn. You can modify `duration_sec=6.0` in `simulate_speaker.py` to fit your hardware microphone environment.
- **Changing TTS Voices:** Neural speech synthesis voices can be customized in `hardware_agent.py` under the `synthesize_speech()` function (`en-IN-NeerjaNeural`, `te-IN-ShrutiNeural`, `hi-IN-SwaraNeural`).
- **Hardware Reset Endpoint:** To manually reset the speaker back to standby mode at any time, send a POST request to `http://localhost:8001/api/hardware_reset` or press `r` in the simulator terminal.
