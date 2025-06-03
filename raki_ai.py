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

# Configuration
CONFIG_FILE = "raki_config.json"
REMINDERS_FILE = "encrypted_reminders.rak"
KEY_FILE = "secret.key"
HISTORY_FILE = "conversation_history.json"

class HumanizedTTS:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.configure_voice()
        self.speech_patterns = {
            'question': {'rate': -20, 'pitch': 1.2},
            'statement': {'rate': 0, 'pitch': 1.0},
            'exclamation': {'rate': 10, 'pitch': 1.3},
            'command': {'rate': 5, 'pitch': 0.95},
            'joke': {'rate': -10, 'pitch': 1.1},
            'amharic': {'rate': 0, 'pitch': 1.0}
        }
        self.current_voice_profile = 'statement'
        
    def configure_voice(self):
        """Find and configure the most human-like voice available"""
        voices = self.engine.getProperty('voices')
        
        # Prefer Ethiopian-accented voices if available
        ethiopian_voices = [v for v in voices if 'ethiopia' in v.id.lower() or 'amharic' in v.id.lower()]
        if ethiopian_voices:
            self.engine.setProperty('voice', ethiopian_voices[0].id)
            print(f"Using Ethiopian voice: {ethiopian_voices[0].name}")
            return
            
        # Prefer MBROLA voices for natural sound
        mbrola_voices = [v for v in voices if 'mbrola' in v.id.lower()]
        if mbrola_voices:
            self.engine.setProperty('voice', mbrola_voices[0].id)
            print(f"Using MBROLA voice: {mbrola_voices[0].name}")
            return
            
        # Fallback to high-quality natural voices
        preferred_voices = [
            'Microsoft Zira Desktop',  # Windows
            'Microsoft David Desktop',
            'Karen',                   # macOS
            'Daniel',
            'english_rp',              
            'english-us'
        ]
        
        for pv in preferred_voices:
            for voice in voices:
                if pv.lower() in voice.name.lower():
                    self.engine.setProperty('voice', voice.id)
                    print(f"Using preferred voice: {voice.name}")
                    return
        
        # Final fallback
        print("Using default system voice")
    
    def set_voice_profile(self, profile_type):
        """Set vocal characteristics based on context"""
        if profile_type in self.speech_patterns:
            self.current_voice_profile = profile_type
            profile = self.speech_patterns[profile_type]
            current_rate = self.engine.getProperty('rate')
            self.engine.setProperty('rate', max(120, min(300, current_rate + profile['rate']))
            self.engine.setProperty('pitch', profile['pitch'])
    
    def add_vocal_variation(self, text):
        """Add natural pauses and emphasis patterns"""
        # Add commas for natural pauses
        text = re.sub(r'\b(and|but|or|so)\b', r'\1,', text)
        
        # Add emphasis to important words
        emphasis_words = ['important', 'critical', 'warning', 'alert', 'urgent']
        for word in emphasis_words:
            if word in text.lower():
                text = text.replace(word, f"<emphasis>{word}</emphasis>")
        
        return text
    
    def humanized_speak(self, text, lang='en'):
        """Convert text to speech with natural human characteristics"""
        if not text:
            return
            
        # Auto-detect speech context
        if lang == 'am':
            self.set_voice_profile('amharic')
        elif text.endswith('?'):
            self.set_voice_profile('question')
        elif text.endswith('!') or any(w in text.lower() for w in ['alert', 'warning']):
            self.set_voice_profile('exclamation')
        elif text.startswith(('Please', 'Could you', 'Would you')):
            self.set_voice_profile('command')
        elif "joke" in text.lower() or "funny" in text.lower():
            self.set_voice_profile('joke')
        else:
            self.set_voice_profile('statement')
        
        # Add natural vocal variations
        processed_text = self.add_vocal_variation(text)
        
        print(f"Raki AI: {text}")
        
        # Speak with natural pauses between sentences
        sentences = re.split(r'(?<=[.!?]) +', processed_text)
        for i, sentence in enumerate(sentences):
            self.engine.say(sentence)
            self.engine.runAndWait()
            
            # Add natural pause between sentences
            if i < len(sentences) - 1:
                pause = 0.3 + random.uniform(0, 0.2)
                time.sleep(pause)
        
        # Reset to default profile after speaking
        self.set_voice_profile('statement')

class RakiAI:
    def __init__(self):
        self.tts = HumanizedTTS()
        self.recognizer = sr.Recognizer()
        self.config = self.load_config()
        self.cipher = self.init_encryption()
        self.reminders = self.load_reminders()
        self.conversation_history = self.load_conversation_history()
        self.incognito_mode = False
        self.current_language = self.config['default_language']
        self.shutdown_flag = False
        
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

    # Existing methods (load_config, save_config, init_encryption, etc.) remain here
    # ... [Previous implementation of load_config, save_config, etc.] ...

    def load_conversation_history(self):
        """Load encrypted conversation history"""
        if not os.path.exists(HISTORY_FILE):
            return []
        
        try:
            with open(HISTORY_FILE, 'r') as f:
                encrypted = f.read()
                decrypted = self.cipher.decrypt(encrypted.encode()).decode()
                return json.loads(decrypted)
        except:
            return []

    def save_conversation_history(self):
        """Save encrypted conversation history"""
        if self.incognito_mode:
            return
            
        encrypted = self.cipher.encrypt(json.dumps(self.conversation_history).encode()).decode()
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

    # ... [Previous methods: listen, run_terminal_command, system_diagnostics, etc.] ...

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
                    response = f"Successfully installed {pkg_name}." if "Error" not in result else f"Installation failed: {result}"
            
            elif 'update' in command or 'upgrade' in command:
                result = self.run_terminal_command("sudo apt update && sudo apt upgrade -y")
                response = "System updated successfully." if "Error" not in result else f"Update failed: {result}"
            
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
                    message = match.group(2).strip()
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
                        help_msg = "የምሠራው ነገር፦ መተግበሪያ መጫን፣ ስርዓት ማደስ፣ ችግር መፈተስ፣ አስታውስት �ማስቀመጥ፣ ኢሜል ላክ፣ ድረገጽ ክፈት፣ ቋንቋ ቀይር፣ የምስል ፍለጋ፣ የድረገጽ ፍለጋ፣ ቀልድ ንገር። ምን ትፈልጋለህ?"
                    else:
                        help_msg = "I can help with: Installing software, system updates, diagnostics, " \
                                  "setting reminders, sending emails, web research, image search, " \
                                  "changing languages, telling jokes, and more. What would you like to do?"
                    self.speak(help_msg, self.current_language)
                else:
                    self.process_command(command)

if __name__ == "__main__":
    assistant = RakiAI()
    assistant.main_loop()
