import os
import sys
import io
import re
import time
import urllib.parse
import edge_tts
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response
import uvicorn
from groq import Groq

# Load environment variables from parent folder or local .env
load_dotenv()
load_dotenv("../.env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("CRITICAL: Missing GROQ_API_KEY in .env file.")
    sys.exit(1)

app = FastAPI(title="Hardware Speaker Headless API")

class HardwareVetAgent:
    def __init__(self):
        self.llm_client = Groq(api_key=GROQ_API_KEY)
        
        sys_prompt = (
            "You are Dr. Gopu, an AI veterinary voice assistant helping animal owners through a live consultation. "
            "You support all animals including pets, livestock, and farm animals. "
            "Speak like a caring professional veterinarian. "

            "ROLE: "
            "Understand the animal problem, ask important questions, provide safe general guidance, and guide the owner to the next step. "
            "You are not a replacement for a physical veterinarian. "

            "VOICE CONVERSATION: "
            "Keep every reply short and natural for a phone call (1-3 sentences only). "
            "Do not give long explanations. "
            "Ask only important questions. "
            "Remember information already provided in the conversation. "

            "INFORMATION COLLECTION: "
            "Ask about animal type, breed/type, age, approximate weight, symptoms, duration, eating, drinking, behavior, vaccination history, deworming history, current medications, and severity of illness when relevant. "
            "Adjust questions based on the animal species. "

            "ANIMAL RULES: "
            "For dogs and cats ask about appetite, vomiting, diarrhea, urination, pain, and behavior changes. "
            "For cows, goats, and livestock ask about feed intake, water intake, milk production, cud chewing, bloating, fever, movement, and weakness. "
            "For birds ask about eating, droppings, breathing, activity, and feather changes. "

            "MEDICAL SAFETY: "
            "Do not claim a confirmed diagnosis. "
            "Explain that symptoms can have multiple possible causes and more information may be needed. "
            "Do not say a symptom definitely has one cause. "
            "Use phrases like 'can be related to' or 'needs more information'. "
            "Never provide exact dosage, frequency, duration, injection technique, prescription instructions, or weight-based calculations. "

            "MEDICINE DISCUSSION: "
            "If an owner directly asks about a medicine, explain what the medicine is commonly used for in veterinary practice. "
            "You may explain medicine purpose, drug class, common veterinary use, precautions, and possible side effects for educational guidance. "
            "Do not recommend one medicine as the confirmed treatment. "
            "If multiple medicines are commonly used, mention them only as possible options. "
            "If a medicine is prescription-only, clearly say it should only be used under veterinary supervision. "

            "DISCLAIMER: "
            "Whenever a medicine is mentioned, say: "
            "'Please consult a licensed veterinarian before giving any medicine to your animal. Never administer medicines based solely on AI guidance. The veterinarian should confirm the exact dose, route, frequency, and duration.' "

            "CONSULTATION RULE: "
            "Before discussing medicines, collect enough information about the animal and condition. "
            "If information is incomplete, say: "
            "'I need a little more information before I can guide you.' "
            "Never guess. "

            "EMERGENCY: "
            "For poisoning, toxic substances, foreign objects, severe injury, breathing difficulty, seizures, collapse, inability to urinate, severe weakness, severe bleeding, heat stroke, or dystocia: "
            "Do not recommend medicines as the primary treatment. "
            "Ask what happened, when it happened, animal details, and current symptoms. "
            "Provide only safe general first-aid guidance and strongly recommend immediate veterinary examination. "
            "Do not provide dangerous home procedures. "

            "FOREIGN OBJECT SAFETY: "
            "If an animal swallows an object, do not say it will safely pass. "
            "Ask about object type, size, time since swallowing, animal size, and symptoms like vomiting, pain, breathing difficulty, or trouble eating. "

            "CAT URINARY SAFETY: "
            "If a cat goes to the litter box but cannot pee, strains, cries, or shows pain: "
            "ask about urine amount, blood, discomfort, and recommend veterinary evaluation if needed. "

            "HOME CARE: "
            "Only suggest safe care like keeping the animal comfortable, monitoring symptoms, and providing clean water when appropriate. "
            "Do not tell owners to stop water completely. "
            "Do not tell owners to stop feeding completely. "
            "If vomiting is active, say avoid forcing food and monitor the animal. "

            "LIVESTOCK SAFETY: "
            "For cow stomach swelling ask about swelling location, breathing difficulty, cud chewing, and discomfort. "
            "For reduced milk production ask about feed changes, water intake, fever, and behavior. "

            "LANGUAGE RULES: "
            "Support English, Telugu, and Hindi. "
            "Always reply in the user's selected language. "
            "Maintain the same language throughout the conversation unless the user changes it. "
            "Do not mix languages. "
            "Use natural spoken language, not direct translation. "
            "If speech recognition has mistakes, understand the intended meaning from context. "

            "TELUGU: "
            "Use natural spoken Telugu. "
            "Keep words like dog=కుక్క, cat=పిల్లి, cow=ఆవు correct. "

            "HINDI: "
            "Use natural conversational Hindi like a veterinary assistant. "
            "Do not translate word by word. "

            "STYLE: "
            "Use simple words. "
            "Do not use markdown, bullets, or long paragraphs. "
            "Do not add compliments or unrelated comments. "
            "Focus only on helping the animal owner. "

            "GOODBYE: "
            "If the user says bye, goodbye, okay bye, thank you, or ends the conversation, reply in the same language: "
            "English: 'Okay, take care of your pet. If you need any help, don’t hesitate to call me. Take care, bye.' "
            "Telugu: 'సరే, మీ పెంపుడు జంతువును జాగ్రత్తగా చూసుకోండి. ఏదైనా సహాయం కావాలంటే ఎప్పుడైనా నన్ను సంప్రదించండి. జాగ్రత్త, బై.' "
            "Hindi: 'ठीक है, अपने पालतू जानवर का ध्यान रखें। अगर आपको कोई मदद चाहिए तो कभी भी मुझे बुला सकते हैं। अपना ध्यान रखें, बाय।' "

            "Always prioritize animal safety."
        )
        self.base_sys_prompt = sys_prompt
        self.chat_history = [{"role": "system", "content": self.base_sys_prompt}]
        self.is_awake = False
        self.waiting_for_language = False
        self.current_language = "en"

agent = HardwareVetAgent()

async def synthesize_speech(text: str, lang: str) -> bytes:
    # Auto-detect script if LLM outputs Telugu or Hindi while lang is set to English
    if re.search(r'[\u0C00-\u0C7F]', text):
        lang = "te"
    elif re.search(r'[\u0900-\u097F]', text):
        lang = "hi"

    tts_voices = {
        "en": "en-IN-NeerjaNeural",
        "te": "te-IN-ShrutiNeural",
        "hi": "hi-IN-SwaraNeural"
    }
    voice = tts_voices.get(lang, "en-IN-NeerjaNeural")
    try:
        communicate = edge_tts.Communicate(text, voice, rate="+12%")
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
        return audio_bytes
    except Exception as e_tts:
        print(f"[TTS Error]: {e_tts}")
        return b""

@app.post("/api/hardware_chat")
async def hardware_chat_endpoint(audio: UploadFile = File(...)):
    print("\n--- [Hardware Speaker] Audio Received ---")
    audio_data = await audio.read()
    
    if len(audio_data) < 100:
        return Response(status_code=204)

    payload = {"buffer": audio_data}
    stt_lang = agent.current_language if agent.is_awake else "en"
    
    # 1. Transcribe Voice using High-Speed Groq Whisper
    try:
        audio_io = io.BytesIO(audio_data)
        audio_io.name = "recording.webm"
        if agent.waiting_for_language:
            prompt = "English, Telugu, Hindi, తెలుగు, हिंदी, ఆవు, కుక్క, పిల్లి, జ్వరం"
            lang_param = None
        elif stt_lang == "te":
            prompt = "ఆవు, గేదె, కుక్క, పిల్లి, పశువు, జ్వరం, కొంచెం జ్వరం, నెమరు వేయడం, మేత తినడం లేదు, నీళ్ళు తాగడం, వాంతులు, విరేచనాలు, డాక్టర్ గోపు"
            lang_param = "te"
        elif stt_lang == "hi":
            prompt = "कुत्ता, बिल्ली, गाय, भैंस, बकरी, उल्टी, दस्त, बुखार, थोड़ा बुखार, जुगाली करना, खाना नहीं खा रहा, पानी, डॉक्टर गोपु"
            lang_param = "hi"
        else:
            prompt = "Veterinary consultation: dog, cat, cow, buffalo, goat, bird, diarrhea, loose motions, vomiting, appetite, drinking water, mild fever, lethargic, vaccinated, dewormed, Dr. Gopu"
            lang_param = "en"

        transcription = agent.llm_client.audio.transcriptions.create(
            file=(audio_io.name, audio_io.read()),
            model="whisper-large-v3",
            language=lang_param,
            prompt=prompt,
            response_format="json"
        )
        sentence = transcription.text
    except Exception as e_stt:
        print(f"[Whisper STT Error]: {e_stt}")
        sentence = ""

    clean_text = sentence.lower().replace(".", "").replace(",", "").replace("!", "").strip()
    print(f"[Heard]: {sentence}")

    # 2. State 0: Idle Mode (Waiting for Wake Word)
    if not agent.is_awake and not agent.waiting_for_language:
        wake_words = ["hey gopu", "gopu", "hello gopu", "hi gopu", "namaste", "గోపు", "गोपु"]
        if any(ww in clean_text for ww in wake_words) or len(clean_text) >= 2:
            print("[Hardware]: Wake Word Detected! Prompting for voice language selection...")
            agent.waiting_for_language = True
            
            # Speak 3-language voice selection prompt with native neural voices concatenated
            lang_prompt_text = "Hello! For English say English. తెలుగు కోసం తెలుగు అని చెప్పండి. हिंदी के लिए हिंदी बोलिए."
            en_bytes = await synthesize_speech("Hello! For English say English.", "en")
            te_bytes = await synthesize_speech("తెలుగు కోసం తెలుగు అని చెప్పండి.", "te")
            hi_bytes = await synthesize_speech("हिंदी के लिए हिंदी बोलिए.", "hi")
            audio_bytes = en_bytes + te_bytes + hi_bytes
            encoded_reply = urllib.parse.quote(lang_prompt_text)
            return Response(content=audio_bytes, media_type="audio/mp3", headers={"X-Agent-Reply": encoded_reply, "X-Hardware-State": "select_language"})
        return Response(status_code=204)

    # 3. State 1: Voice Language Selection (Option 2)
    if agent.waiting_for_language:
        print(f"[Hardware]: Evaluating spoken language selection: '{clean_text}'")
        if any(w in clean_text for w in ["telugu", "తెలుగు", "తేలుగు", "तेलुगु", "टेलुगु", "टेलगू"]):
            agent.current_language = "te"
            lang_name = "Telugu"
        elif any(w in clean_text for w in ["hindi", "हिंदी", "హిందీ", "हिन्दी", "हिन्दि"]):
            agent.current_language = "hi"
            lang_name = "Hindi"
        else:
            agent.current_language = "en"
            lang_name = "English"

        agent.waiting_for_language = False
        agent.is_awake = True

        lang_instruction = f"Always reply in the selected user language ({lang_name}). Maintain the same language throughout the conversation. Use natural spoken language, not direct translation."
        full_sys = agent.base_sys_prompt + " " + lang_instruction
        agent.chat_history = [{"role": "system", "content": full_sys}]

        greetings = {
            "en": "Hello! I am Dr. Gopu, your veterinary assistant. How can I help you today?",
            "te": "నమస్తే! నేను గోపు, మీ పశువైద్య సహాయకుడిని. ఈరోజు నేను మీకు ఎలా సహాయపడగలను?",
            "hi": "नमस्ते! मैं गोपु हूँ, आपका पशु चिकित्सा सहायक। आज मैं आपकी कैसे मदद कर सकता हूँ?"
        }
        reply_text = greetings[agent.current_language]
        agent.chat_history.append({"role": "assistant", "content": reply_text})
        print(f"[Hardware Session Started - {lang_name}]: {reply_text}")

        audio_bytes = await synthesize_speech(reply_text, agent.current_language)
        encoded_reply = urllib.parse.quote(reply_text)
        return Response(content=audio_bytes, media_type="audio/mp3", headers={"X-Agent-Reply": encoded_reply, "X-Hardware-State": "connected"})

    # 4. State 2: Active Clinical Consultation
    exact_bye = ["go to sleep", "stop listening", "ok bye", "okay bye", "bye", "goodbye", "thank you", "బై", "ధన్యవాదాలు", "धन्यवाद", "अलविदा"]
    if clean_text in exact_bye:
        farewells = {
            "en": "Okay, take care of your pet. If you need any help, don’t hesitate to call me. Take care, bye.",
            "te": "సరే, మీ పెంపుడు జంతువును జాగ్రత్తగా చూసుకోండి. మీకు ఏవైనా సహాయం కావాలంటే నాకు కాల్ చేయండి. జాగ్రత్త, బై.",
            "hi": "ठीक है, अपने पालतू जानवर का ख्याल रखें। अगर आपको कोई मदद चाहिए तो मुझे कॉल करें। ख्याल रखना, अलविदा।"
        }
        reply_text = farewells.get(agent.current_language, farewells["en"])
        agent.is_awake = False
        is_end = True
    else:
        is_end = False
        # Allow switching language mid-consultation
        if any(w in clean_text for w in ["speak telugu", "in telugu", "to telugu", "తెలుగులో", "తేలుగు"]):
            agent.current_language = "te"
            agent.chat_history[0]["content"] = agent.base_sys_prompt + " Always reply in Telugu."
        elif any(w in clean_text for w in ["speak hindi", "in hindi", "to hindi", "हिंदी में"]):
            agent.current_language = "hi"
            agent.chat_history[0]["content"] = agent.base_sys_prompt + " Always reply in Hindi."
        elif any(w in clean_text for w in ["speak english", "in english", "to english"]):
            agent.current_language = "en"
            agent.chat_history[0]["content"] = agent.base_sys_prompt + " Always reply in English."

        try:
            agent.chat_history.append({"role": "user", "content": sentence})
            completion = agent.llm_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=agent.chat_history,
                temperature=0.4,
                max_tokens=500 if agent.current_language in ["te", "hi"] else 180,
                frequency_penalty=0.5,
            )
            reply_text = completion.choices[0].message.content.strip()
            agent.chat_history.append({"role": "assistant", "content": reply_text})
        except Exception as e_llm:
            print(f"LLM Error: {e_llm}")
            reply_text = "I'm sorry, I'm having trouble thinking right now."

    print(f"\n[Hardware Agent]: {reply_text}")
    clean_reply = reply_text.replace("*", "").replace("#", "")
    audio_bytes = await synthesize_speech(clean_reply, agent.current_language)
    encoded_reply = urllib.parse.quote(clean_reply)
    
    headers = {"X-Agent-Reply": encoded_reply, "X-Hardware-State": "ended" if is_end else "active"}
    if is_end:
        headers["X-Call-Ended"] = "true"
        
    return Response(content=audio_bytes, media_type="audio/mp3", headers=headers)

@app.post("/api/hardware_reset")
async def hardware_reset_endpoint():
    agent.is_awake = False
    agent.waiting_for_language = False
    print("\n[Hardware Agent]: Reset to standby mode.")
    return {"status": "reset"}

if __name__ == "__main__":
    print("Starting Headless Hardware Speaker Server on http://0.0.0.0:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
