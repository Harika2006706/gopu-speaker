import os
import sys
import io
import re
import time
import urllib.parse

import edge_tts
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import Response
import uvicorn
from groq import Groq


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()
load_dotenv("../.env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("CRITICAL: Missing GROQ_API_KEY in .env file.")
    sys.exit(1)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(title="Hardware Speaker Headless API")


@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {
        "status": "online",
        "service": "Dr. Gopu Hardware Speaker API",
        "docs_url": "/docs",
        "message": "Headless veterinary voice assistant backend is running live."
    }


# ============================================================
# DR. GOPU HARDWARE AGENT
# ============================================================

class HardwareVetAgent:

    def __init__(self):

        self.llm_client = Groq(api_key=GROQ_API_KEY)

        # ----------------------------------------------------
        # BASE SYSTEM PROMPT
        # ----------------------------------------------------

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

            "STYLE: "
            "Use simple words. "
            "Do not use markdown, bullets, or long paragraphs. "
            "Do not add compliments or unrelated comments. "
            "Focus only on helping the animal owner. "
            "If speech recognition has mistakes, understand the intended meaning from context. "

            "Always prioritize animal safety."
        )

        self.base_sys_prompt = sys_prompt

        # Current language.
        self.current_language = "en"

        # Hardware/session state.
        self.is_awake = False
        self.waiting_for_language = False

        # Conversation history.
        self.chat_history = []

        self.reset_conversation_history()

    def reset_conversation_history(self):
        """Reset the conversation history to just the system prompt."""
        self.chat_history = [{"role": "system", "content": self.base_sys_prompt}]


# ============================================================
# GLOBAL AGENT
# ============================================================

agent = HardwareVetAgent()


# ============================================================
# LANGUAGE INSTRUCTIONS
# ============================================================

def get_language_instruction(lang: str) -> str:

    if lang == "te":
        return (
            "\n\nCRITICAL INSTRUCTION: "
            "You MUST reply ONLY in Telugu. "
            "Use natural conversational Telugu."
        )

    if lang == "hi":
        return (
            "\n\nCRITICAL INSTRUCTION: "
            "You MUST reply ONLY in Hindi. "
            "Use natural conversational Hindi."
        )

    return (
        "\n\nCRITICAL INSTRUCTION: "
        "You MUST reply ONLY in English. "
        "Do not output Telugu or Hindi."
    )


# ============================================================
# RESET ONLY THE CONVERSATION
#
# IMPORTANT:
# This clears the LLM conversation but DOES NOT change
# the selected language.
# ============================================================

def reset_conversation_history():

    agent.chat_history = [
        {
            "role": "system",
            "content": (
                agent.base_sys_prompt
                + get_language_instruction(agent.current_language)
            )
        }
    ]

    print(
        f"[Conversation] New conversation started "
        f"while keeping language = {agent.current_language}"
    )


# ============================================================
# COMPLETE HARDWARE RESET
# ============================================================

def reset_hardware_state():

    agent.is_awake = False
    agent.waiting_for_language = False

    # Reset conversation too.
    agent.current_language = "en"
    reset_conversation_history()

    print("[Hardware] Complete state reset to standby.")


# ============================================================
# LANGUAGE DETECTION
# ============================================================

def detect_language_switch(text: str):

    text = text.lower().strip()

    telugu_phrases = [
        "speak telugu",
        "speak in telugu",
        "speaking telugu",
        "speaking in telugu",
        "talk in telugu",
        "talk telugu",
        "reply in telugu",
        "answer in telugu",
        "respond in telugu",
        "change to telugu",
        "switch to telugu",
        "telugu please",
        "తెలుగులో మాట్లాడండి",
        "తెలుగులో మాట్లాడు",
        "తెలుగులో చెప్పు",
        "తెలుగులో మాట్లాడాలి"
    ]

    hindi_phrases = [
        "speak hindi",
        "speak in hindi",
        "speaking hindi",
        "speaking in hindi",
        "talk in hindi",
        "talk hindi",
        "reply in hindi",
        "answer in hindi",
        "respond in hindi",
        "change to hindi",
        "switch to hindi",
        "hindi please",
        "हिंदी में बोलो",
        "हिंदी में बोलिए",
        "हिंदी में बताओ",
        "हिंदी में बताइए"
    ]

    english_phrases = [
        "speak english",
        "speak in english",
        "speaking english",
        "speaking in english",
        "talk in english",
        "talk english",
        "reply in english",
        "answer in english",
        "respond in english",
        "change to english",
        "switch to english",
        "english please"
    ]

    if any(phrase in text for phrase in telugu_phrases):
        return "te"

    if any(phrase in text for phrase in hindi_phrases):
        return "hi"

    if any(phrase in text for phrase in english_phrases):
        return "en"

    return None


# ============================================================
# NEW CONVERSATION / CHANGE TOPIC DETECTION
# ============================================================

def is_new_conversation_request(text: str):

    text = text.lower().strip()

    new_conversation_phrases = [

        # English
        "new conversation",
        "start a new conversation",
        "start new conversation",
        "let's start a new conversation",
        "lets start a new conversation",
        "begin a new conversation",
        "start a fresh conversation",
        "start fresh",
        "start over",
        "start again",
        "new topic",
        "change topic",
        "change the topic",
        "change our topic",
        "talk about something else",
        "let's talk about something else",
        "lets talk about something else",
        "talk about another thing",
        "talk about another topic",
        "forget this conversation",
        "forget our conversation",
        "forget everything",
        "reset conversation",
        "reset the conversation",
        "reset chat",
        "new chat",
        "new discussion",
        "begin again",
        "can we start again",

        # Telugu
        "కొత్త సంభాషణ",
        "కొత్త సంభాషణ మొదలు",
        "కొత్తగా మొదలు పెట్టు",
        "మళ్ళీ మొదలు పెట్టు",
        "మళ్లీ మొదలు పెట్టు",
        "వేరే విషయం మాట్లాడుదాం",
        "వేరే విషయం మాట్లాడండి",
        "విషయం మార్చు",
        "విషయం మార్చండి",

        # Hindi
        "नई बातचीत",
        "नई बातचीत शुरू",
        "नई बात शुरू",
        "फिर से शुरू",
        "दोबारा शुरू",
        "विषय बदलो",
        "विषय बदल दीजिए",
        "दूसरे विषय पर बात करें",
        "कुछ और बात करें"
    ]

    return any(
        phrase in text
        for phrase in new_conversation_phrases
    )


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def clean_transcription(text: str):

    if not text:
        return ""

    cleaned = text.lower()

    cleaned = (
        cleaned
        .replace(".", "")
        .replace(",", "")
        .replace("!", "")
        .replace("?", "")
        .replace(";", "")
        .replace(":", "")
        .strip()
    )

    return cleaned


# ============================================================
# TTS
# ============================================================

async def synthesize_speech(text: str, lang: str) -> bytes:

    # Auto-detect script if LLM outputs Telugu or Hindi
    # while language is incorrectly set to English.

    if re.search(r'[\u0C00-\u0C7F]', text):
        lang = "te"

    elif re.search(r'[\u0900-\u097F]', text):
        lang = "hi"

    tts_voices = {
        "en": "en-IN-NeerjaNeural",
        "te": "te-IN-ShrutiNeural",
        "hi": "hi-IN-SwaraNeural"
    }

    voice = tts_voices.get(
        lang,
        "en-IN-NeerjaNeural"
    )

    try:

        communicate = edge_tts.Communicate(
            text,
            voice,
            rate="+12%"
        )

        audio_bytes = b""

        async for chunk in communicate.stream():

            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]

        return audio_bytes

    except Exception as e_tts:

        print(f"[TTS Error]: {e_tts}")

        return b""


# ============================================================
# LANGUAGE SELECTION RESPONSE
# ============================================================

async def create_language_selection_response():

    lang_prompt_text = (
        "Hello! For English say English. "
        "తెలుగు కోసం తెలుగు అని చెప్పండి. "
        "हिंदी के लिए हिंदी बोलिए."
    )

    en_bytes = await synthesize_speech(
        "Hello! For English say English.",
        "en"
    )

    te_bytes = await synthesize_speech(
        "తెలుగు కోసం తెలుగు అని చెప్పండి.",
        "te"
    )

    hi_bytes = await synthesize_speech(
        "हिंदी के लिए हिंदी बोलिए.",
        "hi"
    )

    audio_bytes = (
        en_bytes
        + te_bytes
        + hi_bytes
    )

    encoded_reply = urllib.parse.quote(
        lang_prompt_text
    )

    return Response(
        content=audio_bytes,
        media_type="audio/mp3",
        headers={
            "X-Agent-Reply": encoded_reply,
            "X-Hardware-State": "select_language"
        }
    )


# ============================================================
# NEW CONVERSATION RESPONSE
# ============================================================

def get_new_conversation_message(lang: str):

    messages = {

        "en":
            "Okay, let's start a new conversation. "
            "What would you like to talk about?",

        "te":
            "సరే, కొత్త సంభాషణను ప్రారంభిద్దాం. "
            "మీరు ఏ విషయం గురించి మాట్లాడాలనుకుంటున్నారు?",

        "hi":
            "ठीक है, चलिए नई बातचीत शुरू करते हैं। "
            "आप किस बारे में बात करना चाहते हैं?"
    }

    return messages.get(
        lang,
        messages["en"]
    )


# ============================================================
# LANGUAGE SWITCH RESPONSE
# ============================================================

def get_language_switch_message(lang: str):

    messages = {

        "en":
            "Sure, I’ll speak in English. How can I help you?",

        "te":
            "సరే, నేను తెలుగులో మాట్లాడతాను. మీకు ఎలా సహాయపడగలను?",

        "hi":
            "ज़रूर, मैं हिंदी में बात करूंगा। मैं आपकी कैसे मदद कर सकता हूँ?"
    }

    return messages.get(
        lang,
        messages["en"]
    )


# ============================================================
# HARDWARE CHAT ENDPOINT
# ============================================================

@app.post("/api/hardware_chat")
async def hardware_chat_endpoint(
    audio: UploadFile = File(...)
):

    print("\n--- [Hardware Speaker] Audio Received ---")

    audio_data = await audio.read()

    if len(audio_data) < 100:

        print("[Hardware] Audio too small.")

        return Response(
            status_code=204
        )

    # --------------------------------------------------------
    # STT LANGUAGE
    # --------------------------------------------------------

    stt_lang = (
        agent.current_language
        if agent.is_awake
        else "en"
    )

    # --------------------------------------------------------
    # WHISPER PROMPT
    # --------------------------------------------------------

    try:

        audio_io = io.BytesIO(audio_data)

        audio_io.name = (
            audio.filename
            if audio.filename
            else "recording.wav"
        )

        if agent.waiting_for_language:

            prompt = (
                "English, Telugu, Hindi, "
                "తెలుగు, हिंदी, "
                "ఆవు, కుక్క, పిల్లి, జ్వరం"
            )

            lang_param = None

        elif stt_lang == "te":

            prompt = (
                "ఆవు, గేదె, కుక్క, పిల్లి, పశువు, జ్వరం, "
                "కొంచెం జ్వరం, నెమరు వేయడం, మేత తినడం లేదు, "
                "నీళ్ళు తాగడం, వాంతులు, విరేచనాలు, "
                "డాక్టర్ గోపు, "
                "కొత్త సంభాషణ, కొత్తగా మొదలు పెట్టు, "
                "మళ్ళీ మొదలు పెట్టు, వేరే విషయం మాట్లాడుదాం, "
                "విషయం మార్చు, "
                "speak Telugu, speak Hindi, speak English, "
                "new conversation, start over, change topic"
            )

            lang_param = "te"

        elif stt_lang == "hi":

            prompt = (
                "कुत्ता, बिल्ली, गाय, भैंस, बकरी, "
                "उल्टी, दस्त, बुखार, थोड़ा बुखार, "
                "जुगाली करना, खाना नहीं खा रहा, पानी, "
                "डॉक्टर गोपु, "
                "नई बातचीत, फिर से शुरू, विषय बदलो, "
                "कुछ और बात करें, "
                "speak Telugu, speak Hindi, speak English, "
                "new conversation, start over, change topic"
            )

            lang_param = "hi"

        else:

            prompt = (
                "Veterinary consultation: dog, cat, cow, "
                "buffalo, goat, bird, diarrhea, loose motions, "
                "vomiting, appetite, drinking water, mild fever, "
                "lethargic, vaccinated, dewormed, Dr. Gopu, "
                "new conversation, start over, new topic, "
                "change topic, reset conversation, "
                "speak Telugu, speak Hindi, speak English"
            )

            lang_param = "en"

        # ----------------------------------------------------
        # GROQ WHISPER
        # ----------------------------------------------------

        transcription = (
            agent.llm_client
            .audio
            .transcriptions
            .create(
                file=(
                    audio_io.name,
                    audio_io.read()
                ),
                model="whisper-large-v3",
                language=lang_param,
                prompt=prompt,
                response_format="json"
            )
        )

        sentence = transcription.text

    except Exception as e_stt:

        print(
            f"[Whisper STT Error]: {e_stt}"
        )

        sentence = ""

    # --------------------------------------------------------
    # CLEAN TRANSCRIPTION
    # --------------------------------------------------------

    clean_text = clean_transcription(
        sentence
    )

    print(f"[Heard]: {sentence}")


    # ========================================================
    # STATE 0
    # IDLE / WAITING FOR WAKE WORD
    # ========================================================

    if (
        not agent.is_awake
        and not agent.waiting_for_language
    ):

        wake_words = [
            "hey gopu",
            "gopu",
            "hello gopu",
            "hi gopu",
            "namaste",
            "గోపు",
            "गोपु"
        ]

        if (
            any(
                ww in clean_text
                for ww in wake_words
            )
        ):

            print(
                "[Hardware]: Wake Word Detected! "
                "Prompting for voice language selection..."
            )

            agent.waiting_for_language = True

            return await create_language_selection_response()

        return Response(
            status_code=204
        )


    # ========================================================
    # STATE 1
    # LANGUAGE SELECTION
    # ========================================================

    if agent.waiting_for_language:

        print(
            "[Hardware]: Evaluating spoken language "
            f"selection: '{clean_text}'"
        )

        if any(
            w in clean_text
            for w in [
                "telugu",
                "తెలుగు",
                "తేలుగు",
                "तेलुगु",
                "तेलगु",
                "टेलुगु",
                "टेलगू"
            ]
        ):

            agent.current_language = "te"
            lang_name = "Telugu"

        elif any(
            w in clean_text
            for w in [
                "hindi",
                "हिंदी",
                "హిందీ",
                "हिन्दी",
                "हिन्दि"
            ]
        ):

            agent.current_language = "hi"
            lang_name = "Hindi"

        else:

            agent.current_language = "en"
            lang_name = "English"

        agent.waiting_for_language = False
        agent.is_awake = True

        # Start a completely clean conversation
        # in the selected language.
        reset_conversation_history()

        greetings = {

            "en":
                "Hello! I am Dr. Gopu, your veterinary assistant. "
                "How can I help you today?",

            "te":
                "నమస్తే! నేను గోపు, మీ పశువైద్య సహాయకుడిని. "
                "ఈరోజు నేను మీకు ఎలా సహాయపడగలను?",

            "hi":
                "नमस्ते! मैं गोपु हूँ, आपका पशु चिकित्सा सहायक। "
                "आज मैं आपकी कैसे मदद कर सकता हूँ?"
        }

        reply_text = greetings[
            agent.current_language
        ]

        agent.chat_history.append(
            {
                "role": "assistant",
                "content": reply_text
            }
        )

        print(
            f"[Hardware Session Started - {lang_name}]: "
            f"{reply_text}"
        )

        audio_bytes = await synthesize_speech(
            reply_text,
            agent.current_language
        )

        encoded_reply = urllib.parse.quote(
            reply_text
        )

        return Response(
            content=audio_bytes,
            media_type="audio/mp3",
            headers={
                "X-Agent-Reply": encoded_reply,
                "X-Hardware-State": "connected"
            }
        )


    # ========================================================
    # STATE 2
    # ACTIVE CLINICAL CONSULTATION
    # ========================================================

    # --------------------------------------------------------
    # FIRST: CHECK FOR NEW CONVERSATION / CHANGE TOPIC
    #
    # This is intentionally checked BEFORE language switching.
    # It guarantees that "new conversation" does not accidentally
    # change language.
    # --------------------------------------------------------

    if is_new_conversation_request(clean_text):

        print(
            "[Conversation] New conversation request detected."
        )

        # Clear previous LLM context.
        # Keep current language.
        reset_conversation_history()

        reply_text = get_new_conversation_message(
            agent.current_language
        )

        agent.chat_history.append(
            {
                "role": "assistant",
                "content": reply_text
            }
        )

        print(
            f"[Conversation] Old context cleared. "
            f"Language preserved: {agent.current_language}"
        )

        audio_bytes = await synthesize_speech(
            reply_text,
            agent.current_language
        )

        encoded_reply = urllib.parse.quote(
            reply_text
        )

        return Response(
            content=audio_bytes,
            media_type="audio/mp3",
            headers={
                "X-Agent-Reply": encoded_reply,
                "X-Hardware-State": "active",
                "X-New-Conversation": "true"
            }
        )


    # --------------------------------------------------------
    # GOODBYE / END SESSION
    # --------------------------------------------------------

    exact_bye = [
        "go to sleep",
        "stop listening",
        "ok bye",
        "okay bye",
        "bye",
        "goodbye",
        "thank you",
        "బై",
        "ధన్యవాదాలు",
        "धन्यवाद",
        "अलविदा"
    ]

    if clean_text in exact_bye:

        farewells = {

            "en":
                "Okay, take care of your pet. "
                "If you need any help, don’t hesitate to call me. "
                "Take care, bye.",

            "te":
                "సరే, మీ పెంపుడు జంతువును జాగ్రత్తగా చూసుకోండి. "
                "మీకు ఏవైనా సహాయం కావాలంటే నాకు కాల్ చేయండి. "
                "జాగ్రత్త, బై.",

            "hi":
                "ठीक है, अपने पालतू जानवर का ख्याल रखें। "
                "अगर आपको कोई मदद चाहिए तो मुझे कॉल करें। "
                "ख्याल रखना, अलविदा।"
        }

        reply_text = farewells.get(
            agent.current_language,
            farewells["en"]
        )

        agent.is_awake = False

        is_end = True

    else:

        is_end = False

        # ----------------------------------------------------
        # LANGUAGE SWITCH
        #
        # IMPORTANT:
        # Switching language does NOT reset conversation.
        # The previous veterinary context is preserved.
        # ----------------------------------------------------

        requested_language = detect_language_switch(
            clean_text
        )

        if requested_language is not None:

            old_language = agent.current_language

            agent.current_language = requested_language

            # Update ONLY the system prompt.
            # Do NOT clear chat history.
            if agent.chat_history:

                agent.chat_history[0]["content"] = (
                    agent.base_sys_prompt
                    + get_language_instruction(
                        agent.current_language
                    )
                )

            print(
                f"[Language] Changed from "
                f"{old_language} -> "
                f"{agent.current_language}"
            )

            reply_text = get_language_switch_message(
                agent.current_language
            )

            agent.chat_history.append(
                {
                    "role": "assistant",
                    "content": reply_text
                }
            )

            audio_bytes = await synthesize_speech(
                reply_text,
                agent.current_language
            )

            encoded_reply = urllib.parse.quote(
                reply_text
            )

            return Response(
                content=audio_bytes,
                media_type="audio/mp3",
                headers={
                    "X-Agent-Reply": encoded_reply,
                    "X-Hardware-State": "active",
                    "X-Language-Changed": agent.current_language
                }
            )


        # ----------------------------------------------------
        # NORMAL VETERINARY CONVERSATION
        # ----------------------------------------------------

        try:

            agent.chat_history.append(
                {
                    "role": "user",
                    "content": sentence
                }
            )

            # Keep system prompt plus the latest 8 messages.
            # This controls token usage while preserving
            # recent consultation context.
            if len(agent.chat_history) > 9:

                agent.chat_history = (
                    [agent.chat_history[0]]
                    + agent.chat_history[-8:]
                )

            # ------------------------------------------------
            # PRIMARY LLM
            # ------------------------------------------------

            try:

                completion = (
                    agent.llm_client
                    .chat
                    .completions
                    .create(
                        model="openai/gpt-oss-120b",
                        messages=agent.chat_history,
                        temperature=0.4,
                        max_tokens=(
                            500
                            if agent.current_language
                            in ["te", "hi"]
                            else 180
                        ),
                        frequency_penalty=0.5
                    )
                )

            except Exception as e_model:

                print(
                    "[Primary LLM Error - Falling back "
                    f"to instant model]: {e_model}"
                )

                completion = (
                    agent.llm_client
                    .chat
                    .completions
                    .create(
                        model="openai/gpt-oss-20b",
                        messages=agent.chat_history,
                        temperature=0.4,
                        max_tokens=(
                            500
                            if agent.current_language
                            in ["te", "hi"]
                            else 180
                        ),
                        frequency_penalty=0.5
                    )
                )

            reply_text = (
                completion
                .choices[0]
                .message
                .content
                .strip()
            )

            agent.chat_history.append(
                {
                    "role": "assistant",
                    "content": reply_text
                }
            )

        except Exception as e_llm:

            print(
                f"LLM Error: {e_llm}"
            )

            reply_text = (
                "I'm sorry, I'm having trouble "
                "thinking right now."
            )


    # ========================================================
    # FINAL RESPONSE / TTS
    # ========================================================

    print(
        f"\n[Hardware Agent]: {reply_text}"
    )

    clean_reply = (
        reply_text
        .replace("*", "")
        .replace("#", "")
    )

    audio_bytes = await synthesize_speech(
        clean_reply,
        agent.current_language
    )

    encoded_reply = urllib.parse.quote(
        clean_reply
    )

    headers = {
        "X-Agent-Reply": encoded_reply,
        "X-Hardware-State": (
            "ended"
            if is_end
            else "active"
        )
    }

    if is_end:

        headers["X-Call-Ended"] = "true"

    return Response(
        content=audio_bytes,
        media_type="audio/mp3",
        headers=headers
    )


# ============================================================
# HARDWARE RESET ENDPOINT
# ============================================================

@app.post("/api/hardware_reset")
async def hardware_reset_endpoint():

    reset_hardware_state()

    return {
        "status": "reset",
        "conversation": "cleared",
        "language": agent.current_language
    }


# ============================================================
# SERVER START
# ============================================================

if __name__ == "__main__":

    print(
        "Starting Headless Hardware Speaker Server "
        "on http://0.0.0.0:8001"
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001
    )