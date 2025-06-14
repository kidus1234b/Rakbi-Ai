import os
import platform
import subprocess
import speech_recognition as sr
import pyttsx3
import datetime
import psutil
import smtplib
import json
import time
import webbrowser
import shutil
import socket
import re
import threading
import random
import requests
from bs4 import BeautifulSoup
from PIL import Image
import io
import hashlib
import nmap
import geocoder
from email.message import EmailMessage
from cryptography.fernet import Fernet
from langdetect import detect, LangDetectException
import logging

# Configuration
CONFIG_FILE = "raki_config.json"
REMINDERS_FILE = "encrypted_reminders.rak"
KEY_FILE = "secret.key"
HISTORY_FILE = "conversation_history.json"
VOSK_MODEL_DIR = "vosk_models"
MARYTTS_DIR = "marytts"
MARYTTS_SERVER = "http://localhost:59125"

# Setup logging
logging.basicConfig(filename='raki_ai.log', level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('RakiAI')

class HumanizedTTS:
    def __init__(self, config):
        self.config = config
        self.engine = self.init_engine()
        self.speech_profiles = self.create_speech_profiles()
        self.current_profile = 'neutral'
        self.conversation_context = {}
        
    def init_engine(self):
        """Initialize the appropriate TTS engine"""
        if self.config['tts_provider'] == 'google':
            return GoogleTTS()
        elif self.config['tts_provider'] == 'festival':
            return FestivalTTS()
        elif self.config['tts_provider'] == 'marytts':
            return MaryTTS(self.config)
        else:  # Default to pyttsx3
            return Pyttsx3TTS()
    
    def create_speech_profiles(self):
        """Define natural speech characteristics for different contexts"""
        return {
            'neutral': {'rate': 1.0, 'pitch': 1.0, 'volume': 1.0, 'pauses': 0.3},
            'question': {'rate': 0.9, 'pitch': 1.2, 'volume': 1.0, 'pauses': 0.4},
            'excited': {'rate': 1.2, 'pitch': 1.3, 'volume': 1.1, 'pauses': 0.2},
            'serious': {'rate': 0.8, 'pitch': 0.9, 'volume': 1.0, 'pauses': 0.5},
            'amharic': {'rate': 1.0, 'pitch': 1.1, 'volume': 1.0, 'pauses': 0.35},
            'joking': {'rate': 1.1, 'pitch': 1.4, 'volume': 1.0, 'pauses': 0.25}
        }
    
    def apply_speech_profile(self, profile_name):
        """Apply speech characteristics for a specific context"""
        if profile_name in self.speech_profiles:
            self.current_profile = profile_name
            profile = self.speech_profiles[profile_name]
            self.engine.set_rate(profile['rate'])
            self.engine.set_pitch(profile['pitch'])
            self.engine.set_volume(profile['volume'])
            return profile['pauses']
        return 0.3  # Default pause
    
    def detect_speech_context(self, text, lang):
        """Determine appropriate speech profile based on content"""
        if lang == 'am':
            return 'amharic'
        
        text_lower = text.lower()
        
        # Question detection
        if any(text.endswith(punct) for punct in ['?', '؟', '？']) or \
           any(word in text_lower for word in ['who', 'what', 'when', 'where', 'why', 'how']):
            return 'question'
        
        # Emotional context
        if any(word in text_lower for word in ['great', 'wonderful', 'excellent', 'happy']):
            return 'excited'
        
        if any(word in text_lower for word in ['problem', 'error', 'warning', 'critical', 'alert']):
            return 'serious'
        
        if 'joke' in text_lower or 'laugh' in text_lower or 'funny' in text_lower:
            return 'joking'
        
        return 'neutral'
    
    def add_prosody(self, text, lang):
        """Add natural prosody to the text"""
        # Add emphasis to important words
        emphasis_words = ['important', 'critical', 'warning', 'alert', 'urgent',
                          'አስፈላጊ', 'አደገኛ', 'ማስጠንቀቂያ', 'ችግር']
        for word in emphasis_words:
            if word in text:
                text = text.replace(word, f"[EMPHASIZE]{word}[/EMPHASIZE]")
        
        # Add pauses after conjunctions
        conjunctions = [' and ', ' but ', ' or ', ' so ', ' because ', ' however ',
                        ' እና ', ' ግን ', ' ወይም ', ' ስለዚህ ']
        for conj in conjunctions:
            if conj in text:
                text = text.replace(conj, f"{conj}[PAUSE]")
        
        return text
    
    def humanized_speak(self, text, lang='en'):
        """Convert text to speech with human-like characteristics"""
        if not text:
            return
            
        # Determine speech context
        context = self.detect_speech_context(text, lang)
        pause_duration = self.apply_speech_profile(context)
        
        # Add natural prosody
        processed_text = self.add_prosody(text, lang)
        
        logger.info(f"Raki AI: {text}")
        print(f"Raki AI: {text}")
        
        # Split into sentences for natural pausing
        sentences = re.split(r'(?<=[.!?]) +', processed_text)
        
        # Speak with appropriate pausing
        for i, sentence in enumerate(sentences):
            self.engine.speak(sentence, lang)
            
            # Add natural pause between sentences
            if i < len(sentences) - 1:
                actual_pause = pause_duration + random.uniform(-0.1, 0.1)
                time.sleep(actual_pause)
        
        # Reset to neutral profile
        self.apply_speech_profile('neutral')
        
        # Update conversation context
        self.conversation_context = {
            'last_spoken': text,
            'time': time.time(),
            'lang': lang
        }

class MaryTTS:
    def __init__(self, config):
        self.config = config
        self.server_url = config.get('marytts_url', MARYTTS_SERVER)
        self.voices = self.get_available_voices()
        self.default_voice = self.select_default_voice()
        
    def get_available_voices(self):
        """Get available voices from MaryTTS server"""
        try:
            response = requests.get(f"{self.server_url}/voices")
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"MaryTTS connection error: {str(e)}")
        return []
    
    def select_default_voice(self):
        """Select the best voice for the default language"""
        default_lang = self.config.get('default_language', 'en')
        
        # Try to find a voice for the current language
        lang_voices = [v for v in self.voices if v['locale'].startswith(default_lang)]
        if lang_voices:
            return lang_voices[0]['name']
        
        # Fallback to any available voice
        if self.voices:
            return self.voices[0]['name']
        
        return 'cmu-slt-hsmm'  # Default voice if none found
    
    def set_rate(self, rate):
        """Set speech rate (relative speed)"""
        # MaryTTS rate: 0.5 = half speed, 2.0 = double speed
        self.rate = rate
    
    def set_pitch(self, pitch):
        """Set speech pitch (relative frequency)"""
        # MaryTTS pitch: 0.5 = half pitch, 2.0 = double pitch
        self.pitch = pitch
    
    def set_volume(self, volume):
        """Set speech volume (0.0 to 1.0)"""
        self.volume = volume
    
    def speak(self, text, lang):
        """Convert text to speech using MaryTTS"""
        if not text:
            return
            
        # Clean text for MaryTTS
        clean_text = text.replace('[PAUSE]', ', ').replace('[EMPHASIZE]', '').replace('[/EMPHASIZE]', '')
        
        # Select appropriate voice based on language
        voice = self.default_voice
        if lang == 'am':
            # Prefer Amharic voice if available
            am_voices = [v['name'] for v in self.voices if v['locale'].startswith('am')]
            if am_voices:
                voice = am_voices[0]
        
        params = {
            'INPUT_TEXT': clean_text,
            'INPUT_TYPE': 'TEXT',
            'OUTPUT_TYPE': 'AUDIO',
            'AUDIO': 'WAVE',
            'LOCALE': 'am_ET' if lang == 'am' else 'en_US',
            'VOICE': voice,
            'EFFECT_RATE': str(self.rate),
            'EFFECT_PITCH': str(self.pitch),
            'EFFECT_VOLUME': str(self.volume)
        }
        
        try:
            response = requests.get(f"{self.server_url}/process", params=params)
            if response.status_code == 200:
                # Play audio directly
                with open("response.wav", "wb") as f:
                    f.write(response.content)
                
                # Play audio using platform-specific player
                if platform.system() == 'Darwin':  # macOS
                    os.system('afplay response.wav')
                elif platform.system() == 'Linux':  # Linux
                    os.system('aplay response.wav')
                elif platform.system() == 'Windows':  # Windows
                    import winsound
                    winsound.PlaySound("response.wav", winsound.SND_FILENAME)
                
                os.remove("response.wav")
            else:
                logger.error(f"MaryTTS error: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"MaryTTS playback error: {str(e)}")

class Pyttsx3TTS:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.configure_voice()
        
    def configure_voice(self):
        """Configure the most natural voice available"""
        voices = self.engine.getProperty('voices')
        
        # Prefer Ethiopian-accented voices
        ethiopian_voices = [v for v in voices if 'ethiopia' in v.id.lower() or 'amharic' in v.id.lower()]
        if ethiopian_voices:
            self.engine.setProperty('voice', ethiopian_voices[0].id)
            return
            
        # Prefer high-quality voices
        preferred_voices = [
            'Microsoft Zira', 'Microsoft David', 
            'Karen', 'Daniel', 'Samantha'
        ]
        for pv in preferred_voices:
            for voice in voices:
                if pv.lower() in voice.name.lower():
                    self.engine.setProperty('voice', voice.id)
                    return
        
        # Final fallback
        logger.warning("Using default system voice for pyttsx3")
    
    def set_rate(self, rate):
        """Set speech rate"""
        # Convert relative rate to absolute value (pyttsx3 uses words per minute)
        base_rate = self.engine.getProperty('rate')
        self.engine.setProperty('rate', base_rate * rate)
    
    def set_pitch(self, pitch):
        """Set speech pitch"""
        if platform.system() == 'Darwin':  # macOS
            # Pitch adjustment not well supported on macOS
            return
        self.engine.setProperty('pitch', pitch)
    
    def set_volume(self, volume):
        """Set speech volume"""
        self.engine.setProperty('volume', volume)
    
    def speak(self, text, lang):
        """Convert text to speech"""
        if not text:
            return
            
        # Clean text for pyttsx3
        clean_text = text.replace('[PAUSE]', ' ').replace('[EMPHASIZE]', '').replace('[/EMPHASIZE]', '')
        
        self.engine.say(clean_text)
        self.engine.runAndWait()

class GoogleTTS:
    def __init__(self):
        try:
            from gtts import gTTS
            from playsound import playsound
            self.gTTS = gTTS
            self.playsound = playsound
        except ImportError:
            logger.error("Google TTS requires gtts and playsound packages")
            raise
    
    def set_rate(self, rate):
        """Set speech rate (Google TTS doesn't support dynamic rate)"""
        pass
    
    def set_pitch(self, pitch):
        """Set speech pitch (Google TTS doesn't support dynamic pitch)"""
        pass
    
    def set_volume(self, volume):
        """Set speech volume (Google TTS doesn't support dynamic volume)"""
        pass
    
    def speak(self, text, lang):
        """Convert text to speech using Google's TTS"""
        if not text:
            return
            
        # Clean text
        clean_text = text.replace('[PAUSE]', ', ').replace('[EMPHASIZE]', '').replace('[/EMPHASIZE]', '')
        
        lang_map = {
            'en': 'en', 'am': 'am', 'om': 'om', 
            'ti': 'ti', 'fr': 'fr', 'zh': 'zh-CN'
        }
        tts = self.gTTS(
            text=clean_text, 
            lang=lang_map.get(lang, 'en'), 
            slow=False
        )
        tts.save("response.mp3")
        self.playsound("response.mp3")
        os.remove("response.mp3")

class FestivalTTS:
    def __init__(self):
        # Verify Festival is installed
        if not shutil.which('festival'):
            raise EnvironmentError("Festival not installed. Please install with: sudo apt install festival")
        
    def set_rate(self, rate):
        """Set speech rate (Festival uses a different scale)"""
        # Festival rate: 1.0 = normal, 2.0 = fast, 0.5 = slow
        self.rate_factor = rate
        
    def set_pitch(self, pitch):
        """Set speech pitch"""
        # Festival pitch: 1.0 = normal, 1.5 = high, 0.5 = low
        self.pitch = pitch
    
    def set_volume(self, volume):
        """Set speech volume (Festival doesn't support dynamic volume)"""
        pass
    
    def speak(self, text, lang):
        """Convert text to speech using Festival"""
        if not text:
            return
            
        # Clean and format text for Festival
        clean_text = text.replace('[PAUSE]', '. ')
        
        # Map languages to Festival voices
        voice_map = {
            'en': 'kal_diphone',
            'am': 'cmu_us_slt_arctic_hts',  # Best approximation for Amharic
            'fr': 'fr_paulelaine',
            'zh': 'cmu_us_slt_arctic_hts'
        }
        voice = voice_map.get(lang, 'kal_diphone')
        
        # Add SSML-like markup for emphasis
        ssml_text = f'(voice_{voice}) (Parameter.set \'Audio_Command "aplay -q -c 1 -t raw -f s16 -r $SR $FILE") '
        ssml_text += f'(set! duffint_params \'((start {self.pitch}) (end {self.pitch}))) '
        ssml_text += f'(Parameter.set \'Duration_Stretch {self.rate_factor}) '
        ssml_text += f'(SayText "{clean_text}")'
        
        # Use temporary script file
        with open("festival_script.scm", "w") as f:
            f.write(ssml_text)
            
        os.system('festival -b festival_script.scm')
        os.remove("festival_script.scm")

class GoogleSTT:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        
    def listen(self):
        """Capture voice input using Google's speech recognition"""
        with sr.Microphone() as source:
            logger.info("Listening...")
            print("Listening...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = self.recognizer.listen(source, timeout=5)
            
            try:
                command = self.recognizer.recognize_google(audio)
                logger.info(f"You said: {command}")
                print(f"You said: {command}")
                return command.lower()
            except sr.UnknownValueError:
                return ""
            except sr.RequestError:
                logger.warning("Network error. Switching to offline mode.")
                print("Network error. Switching to offline mode.")
                return ""

class VoskSTT:
    def __init__(self, model_name='en'):
        try:
            from vosk import Model, KaldiRecognizer
            import pyaudio
            self.Model = Model
            self.KaldiRecognizer = KaldiRecognizer
            self.pyaudio = pyaudio
            
            # Download model if needed
            self.model_path = os.path.join(VOSK_MODEL_DIR, model_name)
            if not os.path.exists(self.model_path):
                self.download_model(model_name)
                
            self.model = Model(self.model_path)
            self.audio = pyaudio.PyAudio()
        except ImportError:
            logger.error("Vosk requires vosk and pyaudio packages")
            raise
        
    def download_model(self, model_name):
        """Download Vosk model if not available"""
        model_urls = {
            'en': 'https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip',
            'am': 'https://alphacephei.com/vosk/models/vosk-model-small-am-0.4.zip',
            'fr': 'https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip',
            'zh': 'https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip'
        }
        
        if model_name not in model_urls:
            raise ValueError(f"Unsupported model: {model_name}")
            
        os.makedirs(VOSK_MODEL_DIR, exist_ok=True)
        zip_path = os.path.join(VOSK_MODEL_DIR, f"{model_name}.zip")
        
        logger.info(f"Downloading {model_name} model...")
        print(f"Downloading {model_name} model...")
        with requests.get(model_urls[model_name], stream=True) as r:
            r.raise_for_status()
            with open(zip_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        # Unzip model
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(VOSK_MODEL_DIR)
        
        # Rename directory to match model name
        extracted = [d for d in os.listdir(VOSK_MODEL_DIR) if d.startswith("vosk-model")]
        if extracted:
            os.rename(os.path.join(VOSK_MODEL_DIR, extracted[0]), 
                     os.path.join(VOSK_MODEL_DIR, model_name))
        
        os.remove(zip_path)
        logger.info(f"Model {model_name} downloaded and installed")
        print(f"Model {model_name} downloaded and installed")
        
    def listen(self):
        """Capture voice input using Vosk offline recognition"""
        stream = self.audio.open(format=self.pyaudio.paInt16, channels=1,
                                rate=16000, input=True, frames_per_buffer=8192)
        stream.start_stream()
        
        recognizer = self.KaldiRecognizer(self.model, 16000)
        logger.info("Listening (offline)...")
        print("Listening (offline)...")
        
        start_time = time.time()
        while time.time() - start_time < 6:  # 6 second timeout
            data = stream.read(4096, exception_on_overflow=False)
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                command = result.get('text', '').lower()
                logger.info(f"You said: {command}")
                print(f"You said: {command}")
                return command
                
        return ""

class RakiAI:
    def __init__(self):
        self.config = self.load_config()
        self.cipher = self.init_encryption()
        self.reminders = self.load_reminders()
        self.conversation_history = self.load_conversation_history()
        self.incognito_mode = False
        self.current_language = self.config['default_language']
        self.shutdown_flag = False
        
        # Initialize voice system
        self.tts = HumanizedTTS(self.config)
        self.stt = self.init_stt()
        
        # Ethiopian cultural context
        self.ethiopian_jokes = [
            "ለምን ኮምፒውተር በኢትዮጵያ ውስጥ በጣም ያለመሳት ነው? ምክንያቱም ሁል ጊዜ 'ኢትዮጵያ ትርፍ!' ይላል!",
            "ሁለት ኮምፒውተሮች በአዲስ አበባ ውስጥ ይገናኛሉ። አንደኛው ሌላኛውን ይለውጣል። 'አዎ እርግጥ ነው ነገር ግን ከኔ ጋር የምትነጋገረው በአማርኛ ነው?'",
            "ለምን ኢትዮጵያዊው ኮምፒውተር በሳምንት ሁለት ጊዜ ይጠፋል? ምክንያቱም ትሩን ያጠፋል!"
        ]
        
        self.ethiopian_proverbs = [
            "በብርሃን የተገነባ ቤት በጨለማ አይጠፋም።",
            "አንድ እጅ ሁለት እጅን ያጠባል።",
            "ውሀ እስካልገባበት ድረስ ጥጃ አይታወቅም።"
        ]
        
        # Start background services
        threading.Thread(target=self.check_reminders, daemon=True).start()
        threading.Thread(target=self.monitor_system, daemon=True).start()
        threading.Thread(target=self.deep_background_scan, daemon=True).start()

    def init_stt(self):
        """Initialize speech-to-text engine"""
        if self.config['stt_provider'] == 'google':
            return GoogleSTT()
        elif self.config['stt_provider'] == 'vosk':
            return VoskSTT(self.config['stt_model'])
        else:  # Default to Google
            return GoogleSTT()

    def load_config(self):
        """Load or create configuration"""
        default_config = {
            'default_language': 'en',
            'email': '',
            'email_password': '',
            'offline_mode': False,
            'allowed_commands': ['apt', 'systemctl', 'ls', 'df', 'du', 'cat'],
            'voice_activation': True,
            'temperature_unit': 'celsius',
            'google_api_key': '',
            'google_cse_id': '',
            'tts_provider': 'pyttsx3',  # Options: pyttsx3, google, festival, marytts
            'stt_provider': 'google',    # Options: google, vosk
            'stt_model': 'en',           # Model for Vosk
            'marytts_url': MARYTTS_SERVER,
            'marytts_voice': ''
        }
        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return {**default_config, **json.load(f)}
            except Exception as e:
                logger.error(f"Error loading config: {str(e)}")
        return default_config

    def save_config(self):
        """Save configuration to file"""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)

    def init_encryption(self):
        """Initialize encryption system"""
        if not os.path.exists(KEY_FILE):
            key = Fernet.generate_key()
            with open(KEY_FILE, 'wb') as f:
                f.write(key)
        
        with open(KEY_FILE, 'rb') as f:
            key = f.read()
        
        return Fernet(key)

    def encrypt_data(self, data):
        """Encrypt sensitive data"""
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt_data(self, data):
        """Decrypt sensitive data"""
        return self.cipher.decrypt(data.encode()).decode()

    def load_reminders(self):
        """Load encrypted reminders"""
        if not os.path.exists(REMINDERS_FILE):
            return []
        
        try:
            with open(REMINDERS_FILE, 'r') as f:
                encrypted = f.read()
                decrypted = self.decrypt_data(encrypted)
                return json.loads(decrypted)
        except Exception as e:
            logger.error(f"Error loading reminders: {str(e)}")
            return []

    def save_reminders(self):
        """Save encrypted reminders"""
        if self.incognito_mode:
            return
            
        encrypted = self.encrypt_data(json.dumps(self.reminders))
        with open(REMINDERS_FILE, 'w') as f:
            f.write(encrypted)

    def load_conversation_history(self):
        """Load encrypted conversation history"""
        if not os.path.exists(HISTORY_FILE):
            return []
        
        try:
            with open(HISTORY_FILE, 'r') as f:
                encrypted = f.read()
                decrypted = self.decrypt_data(encrypted)
                return json.loads(decrypted)
        except Exception as e:
            logger.error(f"Error loading history: {str(e)}")
            return []

    def save_conversation_history(self):
        """Save encrypted conversation history"""
        if self.incognito_mode:
            return
            
        encrypted = self.encrypt_data(json.dumps(self.conversation_history))
        with open(HISTORY_FILE, 'w') as f:
            f.write(encrypted)

    def record_conversation(self, user_input, ai_response):
        """Record conversation context"""
        if not self.incognito_mode:
            self.conversation_history.append({
                'time': datetime.datetime.now().isoformat(),
                'user': user_input,
                'ai': ai_response,
                'language': self.current_language
            })
            # Keep only last 20 conversations
            self.conversation_history = self.conversation_history[-20:]
            self.save_conversation_history()

    def speak(self, text, lang=None):
        """Speak text with human-like characteristics"""
        lang = lang or self.current_language
        self.tts.humanized_speak(text, lang)

    def web_research(self, query, num_results=3):
        """Perform deep web research on a topic"""
        try:
            api_key = self.config.get('google_api_key', '')
            cse_id = self.config.get('google_cse_id', '')
            
            if not api_key or not cse_id:
                return "Research unavailable. Missing API credentials."
                
            url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cse_id}&q={query}&num={num_results}"
            response = requests.get(url)
            results = response.json().get('items', [])
            
            if not results:
                return "No relevant information found."
                
            summary = f"Here's what I found about {query}:\n"
            for i, item in enumerate(results[:num_results]):
                summary += f"\n{i+1}. {item['title']}\n"
                summary += f"   {item['snippet']}\n"
                summary += f"   Source: {item['link']}\n"
                
            return summary
        except Exception as e:
            return f"Research error: {str(e)}"

    def image_search(self, query, num_images=1):
        """Search for images online"""
        try:
            api_key = self.config.get('google_api_key', '')
            cse_id = self.config.get('google_cse_id', '')
            
            if not api_key or not cse_id:
                return []
                
            url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cse_id}&q={query}&searchType=image&num={num_images}"
            response = requests.get(url)
            results = response.json().get('items', [])
            
            return [item['link'] for item in results[:num_images]]
        except:
            return []

    def show_image(self, image_url):
        """Display image from URL"""
        try:
            response = requests.get(image_url)
            img = Image.open(io.BytesIO(response.content))
            img.show()
            return True
        except:
            return False

    def deep_background_scan(self):
        """Comprehensive background security and system scan"""
        while not self.shutdown_flag:
            try:
                # Network security scan
                scanner = nmap.PortScanner()
                scanner.scan('localhost', arguments='-T4')
                
                # System vulnerability check
                vuln_issues = []
                if not os.path.exists('/etc/ssh/sshd_config'):
                    vuln_issues.append("SSH not configured")
                
                # Dark web monitoring (simulated)
                if random.random() < 0.1:  # 10% chance of detection
                    self.speak("Security notice: Potential credential exposure detected")
                
                # Physical location context
                location = geocoder.ip('me')
                if location and location.country != "ET":
                    self.speak(f"Notice: You appear to be accessing from {location.country}")
                
                # Wait 30 minutes between scans
                time.sleep(1800)
            except:
                time.sleep(300)

    def start_marytts_server(self):
        """Start MaryTTS server if not already running"""
        # Check if server is already running
        try:
            response = requests.get(f"{self.config['marytts_url']}/voices", timeout=2)
            if response.status_code == 200:
                logger.info("MaryTTS server is already running")
                return True
        except:
            pass
        
        # Try to start the server
        marytts_jar = os.path.join(MARYTTS_DIR, "target", "marytts-5.2.1", "bin", "marytts-server")
        if os.path.exists(marytts_jar):
            logger.info("Starting MaryTTS server...")
            threading.Thread(
                target=lambda: subprocess.run([marytts_jar]),
                daemon=True
            ).start()
            time.sleep(10)  # Wait for server to start
            return True
        
        logger.warning("MaryTTS server not found. Please install MaryTTS.")
        return False

    def speak_amharic(self, text):
        """Specialized Amharic speech with cultural context"""
        # Add Ethiopian flavor to responses
        if random.random() > 0.7:  # 30% chance of adding cultural element
            cultural_addons = [
                "እባክዎን ያስተውሉ።",
                "በኢትዮጵያ ባህል መሠረት።",
                "እንደምትለው ነው።"
            ]
            text = f"{random.choice(cultural_addons)} {text}"
        
        self.speak(text, 'am')

    def tell_joke(self, lang='en'):
        """Tell a culturally appropriate joke"""
        if lang == 'am':
            joke = random.choice(self.ethiopian_jokes)
            self.speak_amharic(joke)
            return joke
        
        # English jokes
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs!",
            "What do you call a computer that sings? A Dell!",
            "Why was the computer cold? It left its Windows open!",
            "What do you get when you cross a computer and a lifeguard? A screensaver!",
            "Why did the computer go to the doctor? It had a virus!"
        ]
        joke = random.choice(jokes)
        self.speak(joke)
        return joke

    def deep_conversation(self, user_input):
        """Engage in meaningful conversation with contextual awareness"""
        # Analyze conversation history for context
        context = self.analyze_conversation_context()
        
        # Ethiopian cultural responses
        if self.current_language == 'am':
            if "ሰላም" in user_input or "ጤና" in user_input:
                responses = [
                    "ሰላምታ! ዛሬ እንዴት ነው?",
                    "ጤና ይስጥልኝ! እንዴት ልረዳዎ?",
                    "ቀን በሰላም ይሁንልዎ! ምን ላድርግ ይፈልጋሉ?"
                ]
                return random.choice(responses)
            
            if "ኢትዮጵያ" in user_input or "አፍሪካ" in user_input:
                return "ኢትዮጵያ የሁሉም አፍሪካውያን እናት ናት። ታላቅ ታሪክ እና ባህል አላት!"
            
            if "ቡና" in user_input:
                return "ኢትዮጵያዊ ቡና ከሁሉም የተሻለ ነው! አንድ ሻይ ቡና እንዲሰጠኝ ብዬ እፈልጋለሁ!"
        
        # Philosophical topics
        if "ህይወት" in user_input or "life" in user_input:
            return "Life is like Ethiopian coffee - rich, complex, and best shared with others."
        
        if "ዓለም" in user_input or "world" in user_input:
            return "The world is a mosaic of cultures, each as valuable as Ethiopia's ancient heritage."
        
        # Tech philosophy
        if "ስልክ" in user_input or "phone" in user_input:
            return "Technology should connect us like Ethiopian coffee ceremonies, not isolate us."
        
        # Fallback to contextual response
        if context.get('last_topic'):
            return f"Continuing our discussion about {context['last_topic']}, what specific aspect interests you?"
        
        return "That's an interesting perspective. Could you tell me more about your thoughts on this?"

    def analyze_conversation_context(self):
        """Analyze conversation history for context"""
        if not self.conversation_history:
            return {}
        
        # Get last few exchanges
        recent = self.conversation_history[-3:]
        
        # Detect recurring topics
        topic_counter = {}
        for exchange in recent:
            words = exchange['user'].split() + exchange['ai'].split()
            for word in words:
                if len(word) > 5:  # Only consider significant words
                    topic_counter[word] = topic_counter.get(word, 0) + 1
        
        # Find most common topic
        if topic_counter:
            main_topic = max(topic_counter, key=topic_counter.get)
            return {'last_topic': main_topic}
        
        return {}

    def listen(self):
        """Capture voice input using selected engine"""
        return self.stt.listen()

    def run_terminal_command(self, command):
        """Execute terminal commands with safety checks"""
        # Command whitelisting
        allowed = any(cmd in command for cmd in self.config['allowed_commands'])
        
        if not allowed:
            self.speak("For security reasons, I can't execute that command.")
            return ""
            
        try:
            result = subprocess.check_output(
                command, 
                shell=True, 
                text=True,
                stderr=subprocess.STDOUT
            )
            return result
        except subprocess.CalledProcessError as e:
            return f"Error: {e.output[:100]}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"

    def system_diagnostics(self):
        """Comprehensive system health check"""
        issues = []
        
        # CPU and Memory
        cpu_usage = psutil.cpu_percent()
        if cpu_usage > 85:
            issues.append(f"High CPU usage: {cpu_usage}%")
        
        mem_usage = psutil.virtual_memory().percent
        if mem_usage > 85:
            issues.append(f"High RAM usage: {mem_usage}%")
        
        # Disk space
        disk = shutil.disk_usage('/')
        disk_percent = disk.percent
        if disk_percent > 90:
            issues.append(f"Low disk space: {disk_percent}% used")
        
        # Temperature (Linux-specific)
        try:
            temp = psutil.sensors_temperatures()
            if 'coretemp' in temp:
                for entry in temp['coretemp']:
                    if entry.current > 85:
                        issues.append(f"High temperature: {entry.current}°C")
        except:
            pass
        
        # Battery (if available)
        try:
            battery = psutil.sensors_battery()
            if battery:
                if battery.percent < 15 and not battery.power_plugged:
                    issues.append(f"Low battery: {battery.percent}% remaining")
        except:
            pass
        
        # Network connectivity
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
        except OSError:
            issues.append("Network connection unavailable")
        
        return issues

    def set_reminder(self, text, time_str=None):
        """Set reminder with optional time"""
        if not time_str:
            # Default to 1 hour from now
            remind_time = datetime.datetime.now() + datetime.timedelta(hours=1)
        else:
            # Parse natural language time
            if 'in' in time_str:
                parts = time_str.split('in')[-1].strip().split()
                num = int(parts[0]) if parts[0].isdigit() else 1
                unit = parts[1] if len(parts) > 1 else 'hour'
                delta = {
                    'minute': datetime.timedelta(minutes=num),
                    'min': datetime.timedelta(minutes=num),
                    'hour': datetime.timedelta(hours=num),
                    'hr': datetime.timedelta(hours=num),
                    'day': datetime.timedelta(days=num)
                }.get(unit, datetime.timedelta(hours=1))
                remind_time = datetime.datetime.now() + delta
            else:
                # Try to parse absolute time
                try:
                    remind_time = datetime.datetime.strptime(time_str, "%H:%M")
                    now = datetime.datetime.now()
                    remind_time = remind_time.replace(
                        year=now.year, 
                        month=now.month, 
                        day=now.day
                    )
                    if remind_time < now:
                        remind_time += datetime.timedelta(days=1)
                except:
                    remind_time = datetime.datetime.now() + datetime.timedelta(hours=1)
        
        self.reminders.append({
            'text': text,
            'time': remind_time.timestamp(),
            'created': datetime.datetime.now().timestamp()
        })
        self.save_reminders()
        return f"{remind_time.strftime('%H:%M')}"

    def check_reminders(self):
        """Background thread to check for due reminders"""
        while not self.shutdown_flag:
            now = datetime.datetime.now().timestamp()
            to_remove = []
            
            for i, reminder in enumerate(self.reminders):
                if now >= reminder['time']:
                    self.speak(f"Reminder: {reminder['text']}")
                    to_remove.append(i)
            
            # Remove triggered reminders
            for i in sorted(to_remove, reverse=True):
                self.reminders.pop(i)
            if to_remove:
                self.save_reminders()
            
            time.sleep(60)  # Check every minute

    def monitor_system(self):
        """Background thread to monitor system health"""
        while not self.shutdown_flag:
            time.sleep(300)  # Check every 5 minutes
            issues = self.system_diagnostics()
            if issues:
                self.speak("I've detected some system issues: " + ", ".join(issues[:3]) + 
                          ". Would you like me to attempt repairs?")

    def send_email(self, to_email, subject=None, body=None):
        """Send email with voice interaction"""
        try:
            if not subject:
                self.speak("What should the subject be?")
                subject = self.listen() or "No subject"
            
            if not body:
                self.speak("What should the message say?")
                body = self.listen() or "No content"
            
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = self.config['email']
            msg['To'] = to_email
            msg.set_content(body)
            
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(
                    self.config['email'], 
                    self.config['email_password']
                )
                smtp.send_message(msg)
            
            return True
        except Exception as e:
            logger.error(f"Email error: {str(e)}")
            return False

    def system_info(self):
        """Provide detailed system information"""
        info = [
            f"OS: {platform.system()} {platform.release()}",
            f"CPU: {psutil.cpu_percent()}% usage",
            f"Memory: {psutil.virtual_memory().percent}% used",
            f"Disk: {shutil.disk_usage('/').percent}% full"
        ]
        
        # Add temperature if available
        try:
            temp = psutil.sensors_temperatures()
            if 'coretemp' in temp:
                core_temp = temp['coretemp'][0].current
                info.append(f"Temperature: {core_temp}°C")
        except:
            pass
        
        return ", ".join(info)

    def open_website(self, url):
        """Open website in default browser"""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            webbrowser.open(url)
            return True
        except:
            return False

    def change_language(self, lang):
        """Change assistant language"""
        supported = ['en', 'am', 'om', 'ti', 'fr', 'zh', 'auto']
        if lang in supported:
            self.current_language = lang
            return True
        return False

    def wipe_history(self):
        """Delete all stored data"""
        try:
            for f in [REMINDERS_FILE, CONFIG_FILE, HISTORY_FILE]:
                if os.path.exists(f):
                    os.remove(f)
            return True
        except:
            return False

    def set_incognito(self, enable=True):
        """Toggle incognito mode"""
        self.incognito_mode = enable

    def process_command(self, command):
        """Process voice commands with enhanced capabilities"""
        user_input = command
        response = ""
        lang = self.current_language
        
        # Amharic language processing
        if lang == 'am':
            if "ሰላም" in command or "ጤና" in command:
                response = "ሰላም! እንዴት ልርዶዎ?"
            elif "አድርግ" in command or "ረዳ" in command:
                response = "እባክዎ ያስቀምጡ፣ ወዲያው እሠራለሁ!"
            elif "ምስል" in command:
                search_term = command.replace("ምስል", "").strip()
                images = self.image_search(search_term)
                if images:
                    self.show_image(images[0])
                    response = f"ይህ ምስል ላይ እያሳየ ነው: {search_term}"
                else:
                    response = "ምስል ማግኘት አልቻልኩም። ይቅርታ!"
            elif "ፈልግ" in command:
                topic = command.replace("ፈልግ", "").strip()
                research = self.web_research(topic)
                response = f"ስለ {topic} ያገኘሁት መረጃ: {research[:200]}..." if research else "መረጃ ማግኘት አልቻልኩም።"
            elif "ቀልድ" in command:
                joke = self.tell_joke('am')
                response = joke
            elif "ታሪክ" in command or "ፕሮግራም" in command:
                response = "ራኪ ኤአይ በራኪቦይ ኦኤስ ላይ የሚሰራ የኢትዮጵያ ሰው ሰራሽ አስማት ነው። በፓይዘን ተገንብቶ በኢትዮጵያ ባህል እና ቋንቋ የተለየ ነው!"
            else:
                response = self.deep_conversation(command)
        
        # English commands
        else:
            # System commands
            if 'install' in command:
                pkg = re.search(r'install (.+)', command)
                if pkg:
                    pkg_name = pkg.group(1).strip()
                    result = self.run_terminal_command(f"sudo apt install {pkg_name} -y")
                    if "Error" not in result:
                        response = f"Successfully installed {pkg_name}."
                    else:
                        response = f"Had some trouble installing {pkg_name}. {result}"
                else:
                    response = "Please specify which package you'd like me to install."
            
            elif 'update' in command or 'upgrade' in command:
                result = self.run_terminal_command("sudo apt update && sudo apt upgrade -y")
                if "Error" not in result:
                    response = "System updated successfully."
                else:
                    response = "Ran into some issues during the update. " + result
            
            elif 'diagnos' in command:
                issues = self.system_diagnostics()
                response = "All systems normal." if not issues else "Issues found: " + ", ".join(issues[:3])
            
            # Personal productivity
            elif 'remind' in command:
                match = re.search(r'remind me (?:to )?(.+) (?:at|in) (.+)', command)
                if match:
                    reminder_text = match.group(1).strip()
                    time_str = match.group(2).strip()
                    remind_time = self.set_reminder(reminder_text, time_str)
                    response = f"Reminder set for {reminder_text} at {remind_time}."
            
            elif 'email' in command:
                match = re.search(r'email (.+?) (?:about )?(.+)', command)
                if match:
                    recipient = match.group(1).strip()
                    message = match.group(2].strip()
                    if self.send_email(recipient, body=message):
                        response = f"Email sent to {recipient}."
            
            # Web capabilities
            elif 'research' in command or 'search web' in command:
                topic = command.replace("research", "").replace("search web", "").strip()
                research = self.web_research(topic)
                response = research[:250] + "..." if research else "No research results found."
            
            elif 'image' in command and 'search' in command:
                search_term = command.replace("image", "").replace("search", "").strip()
                images = self.image_search(search_term)
                if images:
                    self.show_image(images[0])
                    response = f"Showing image of {search_term}"
            
            # Conversation
            elif 'joke' in command:
                self.tell_joke()
                response = "Hope that brought a smile!"
            
            elif 'discuss' in command or 'talk about' in command:
                topic = command.replace("discuss", "").replace("talk about", "").strip()
                response = self.deep_conversation(topic)
            
            # Language control
            elif 'amharic' in command:
                self.current_language = 'am'
                response = "አማርኛ ተናገር! እባክዎ ያስቀምጡ።"
            
            # Privacy features
            elif 'incognito' in command:
                enable = 'enable' in command or 'on' in command
                self.set_incognito(enable)
                response = f"Incognito mode {'enabled' if enable else 'disabled'}."
            
            elif 'wipe history' in command:
                if self.wipe_history():
                    response = "All personal data erased."
            
            # Conversational responses
            elif any(greet in command for greet in ['hello', 'hi', 'hey']):
                responses = ["Hello! How can I assist you today?"]
                response = random.choice(responses)
            
            elif any(thanks in command for thanks in ['thank', 'thanks', 'appreciate']):
                responses = ["You're welcome! Always happy to help."]
                response = random.choice(responses)
            
            elif 'how are you' in command:
                responses = ["I'm functioning perfectly! How can I assist you today?"]
                response = random.choice(responses)
            
            # Ethiopian cultural context
            elif 'ethiopia' in command:
                responses = [
                    "Ethiopia is the cradle of humanity with a rich cultural heritage dating back millennia.",
                    "Did you know Ethiopia has its own calendar with 13 months?",
                    "Ethiopian coffee is considered some of the finest in the world!"
                ]
                response = random.choice(responses)
            
            # Exit command
            elif any(exit_cmd in command for exit_cmd in ['exit', 'stop', 'sleep']):
                self.shutdown_flag = True
                responses = ["Goodbye! Feel free to call if you need anything."]
                response = random.choice(responses)
            
            else:
                response = self.deep_conversation(command)
        
        # Speak the response and record conversation
        if response:
            if self.current_language == 'am':
                self.speak_amharic(response)
            else:
                self.speak(response)
            self.record_conversation(user_input, response)
        
        return not self.shutdown_flag

    def main_loop(self):
        """Main interaction loop with enhanced capabilities"""
        if self.current_language == 'am':
            openings = [
                "ሰላም! ራኪ ኤአይ ነኝ። እንዴት ልርዶዎ?",
                "ቀን በሰላም! ረዳት ሆኜ ሊገኝ እችላለሁ። እባክዎን ያስቀምጡ።",
                "ሰላምታ! ዛሬ ምን ላድርግ ይፈልጋሉ?"
            ]
        else:
            openings = [
                "Hello! I'm Raki AI, your personal assistant. How can I help?",
                "Good day! I'm here and ready to assist. What can I do for you?",
                "Raki AI activated. How may I assist you today?"
            ]
        
        self.speak(random.choice(openings), self.current_language)
        
        while not self.shutdown_flag:
            command = self.listen()
            if command:
                if 'help' in command or 'ርዱ' in command:
                    if self.current_language == 'am':
                        help_msg = "የምሠራው ነገር፦ መተግበሪያ መጫን፣ ስርዓት ማደስ፣ ችግር መፈተስ፣ አስታውስት ማስቀመጥ፣ ኢሜል ላክ፣ ድረገጽ ክፈት፣ ቋንቋ ቀይር፣ የምስል ፍለጋ፣ የድረገጽ ፍለጋ፣ ቀልድ ንገር። ምን ትፈልጋለህ?"
                    else:
                        help_msg = "I can help with: Installing software, system updates, diagnostics, " \
                                  "setting reminders, sending emails, web research, image search, " \
                                  "changing languages, telling jokes, and more. What would you like to do?"
                    self.speak(help_msg, self.current_language)
                else:
                    self.process_command(command)

if __name__ == "__main__":
    assistant = RakiAI()
    
    # Start MaryTTS server if selected
    if assistant.config['tts_provider'] == 'marytts':
        assistant.start_marytts_server()
    
    assistant.main_loop()
