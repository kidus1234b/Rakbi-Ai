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
import math
from email.message import EmailMessage
from cryptography.fernet import Fernet
from langdetect import detect, LangDetectException

# Configuration
CONFIG_FILE = "raki_config.json"
REMINDERS_FILE = "encrypted_reminders.rak"
KEY_FILE = "secret.key"

class HumanizedTTS:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.configure_voice()
        self.speech_patterns = {
            'question': {'rate': -20, 'pitch': 1.2},
            'statement': {'rate': 0, 'pitch': 1.0},
            'exclamation': {'rate': 10, 'pitch': 1.3},
            'command': {'rate': 5, 'pitch': 0.95}
        }
        self.current_voice_profile = 'statement'
        
    def configure_voice(self):
        """Find and configure the most human-like voice available"""
        voices = self.engine.getProperty('voices')
        
        # Prefer MBROLA voices for natural sound (if available)
        mbrola_voices = [v for v in voices if 'mbrola' in v.id.lower()]
        if mbrola_voices:
            self.engine.setProperty('voice', mbrola_voices[0].id)
            print(f"Using MBROLA voice: {mbrola_voices[0].name}")
        else:
            # Try to find high-quality natural voices
            preferred_voices = [
                'Microsoft Zira Desktop',  # Windows natural voice
                'Microsoft David Desktop',
                'Karen',                   # macOS natural voice
                'Daniel',
                'english_rp',              # eSpeak variants
                'english-us'
            ]
            
            for pv in preferred_voices:
                for voice in voices:
                    if pv.lower() in voice.name.lower():
                        self.engine.setProperty('voice', voice.id)
                        print(f"Using preferred voice: {voice.name}")
                        return
            
            # Fallback to first available female voice
            for voice in voices:
                if 'female' in voice.name.lower():
                    self.engine.setProperty('voice', voice.id)
                    print(f"Using female voice: {voice.name}")
                    return
        
        print("Using default system voice")
    
    def set_voice_profile(self, profile_type):
        """Set vocal characteristics based on context"""
        if profile_type in self.speech_patterns:
            self.current_voice_profile = profile_type
            profile = self.speech_patterns[profile_type]
            current_rate = self.engine.getProperty('rate')
            self.engine.setProperty('rate', max(120, min(300, current_rate + profile['rate'])))
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
    
    def humanized_speak(self, text):
        """Convert text to speech with natural human characteristics"""
        if not text:
            return
            
        # Auto-detect speech context
        if text.endswith('?'):
            self.set_voice_profile('question')
        elif text.endswith('!') or any(w in text.lower() for w in ['alert', 'warning']):
            self.set_voice_profile('exclamation')
        elif text.startswith(('Please', 'Could you', 'Would you')):
            self.set_voice_profile('command')
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
            
            # Add natural pause between sentences (longer at paragraph breaks)
            if i < len(sentences) - 1:
                pause = 0.3 + random.uniform(0, 0.2)  # 300ms ± random variation
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
        self.incognito_mode = False
        self.current_language = self.config['default_language']
        self.shutdown_flag = False
        
        # Start background services
        threading.Thread(target=self.check_reminders, daemon=True).start()
        threading.Thread(target=self.monitor_system, daemon=True).start()

    def load_config(self):
        """Load or create configuration"""
        default_config = {
            'default_language': 'en',
            'email': '',
            'email_password': '',
            'offline_mode': False,
            'allowed_commands': ['apt', 'systemctl', 'ls', 'df', 'du', 'cat'],
            'voice_activation': True,
            'temperature_unit': 'celsius'
        }
        
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return {**default_config, **json.load(f)}
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
        except:
            return []

    def save_reminders(self):
        """Save encrypted reminders"""
        if self.incognito_mode:
            return
            
        encrypted = self.encrypt_data(json.dumps(self.reminders))
        with open(REMINDERS_FILE, 'w') as f:
            f.write(encrypted)

    def speak(self, text):
        """Speak text with human-like characteristics"""
        self.tts.humanized_speak(text)

    def listen(self):
        """Capture voice input with language support"""
        with sr.Microphone() as source:
            print("Listening...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = self.recognizer.listen(source, timeout=5)
            
            try:
                if self.config['offline_mode']:
                    # Offline recognition would go here (using Vosk or similar)
                    command = "Offline mode not fully implemented"
                else:
                    # Use Google's speech recognition with dynamic language
                    command = self.recognizer.recognize_google(
                        audio, 
                        language=self.get_google_lang_code()
                    )
                
                print(f"You said: {command}")
                return command.lower()
            except sr.UnknownValueError:
                self.speak("Sorry, I didn't quite catch that.")
            except sr.RequestError:
                self.speak("Network error. Switching to offline mode.")
                self.config['offline_mode'] = True
            except Exception as e:
                print(f"Recognition error: {str(e)}")
                
        return ""

    def get_google_lang_code(self):
        """Map our language codes to Google's format"""
        lang_map = {
            'en': 'en-US',
            'am': 'am-ET',
            'om': 'om-ET',
            'ti': 'ti-ET',
            'fr': 'fr-FR',
            'zh': 'zh-CN'
        }
        return lang_map.get(self.current_language, 'en-US')

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
            print(f"Email error: {str(e)}")
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
            for f in [REMINDERS_FILE, CONFIG_FILE]:
                if os.path.exists(f):
                    os.remove(f)
            return True
        except:
            return False

    def set_incognito(self, enable=True):
        """Toggle incognito mode"""
        self.incognito_mode = enable

    def process_command(self, command):
        """Process voice commands with conversational responses"""
        cmd = command.lower()
        response = ""
        
        # System commands
        if 'install' in cmd:
            pkg = re.search(r'install (.+)', cmd)
            if pkg:
                pkg_name = pkg.group(1).strip()
                result = self.run_terminal_command(f"sudo apt install {pkg_name} -y")
                if "Error" not in result:
                    response = f"I've successfully installed {pkg_name} for you."
                else:
                    response = f"Had some trouble installing {pkg_name}. {result}"
            else:
                response = "Please specify which package you'd like me to install."
        
        elif 'update' in cmd or 'upgrade' in cmd:
            result = self.run_terminal_command("sudo apt update && sudo apt upgrade -y")
            if "Error" not in result:
                response = "Your system is now up-to-date with the latest software."
            else:
                response = "Ran into some issues during the update. " + result
        
        elif 'diagnos' in cmd:  # Handles "diagnose" or "diagnostic"
            issues = self.system_diagnostics()
            if not issues:
                response = "Everything looks great! Your system is running smoothly."
            else:
                response = "I found a few things that need attention: " + \
                          ", ".join(issues[:3]) + ". Would you like me to try fixing these?"
        
        # Personal productivity
        elif 'remind' in cmd:
            match = re.search(r'remind me (?:to )?(.+) (?:at|in) (.+)', cmd)
            if match:
                reminder_text = match.group(1).strip()
                time_str = match.group(2).strip()
                remind_time = self.set_reminder(reminder_text, time_str)
                response = f"Okay, I'll remind you about {reminder_text} at {remind_time}."
            else:
                response = "Sure, I can set a reminder. What should I remind you about and when?"
        
        elif 'email' in cmd:
            match = re.search(r'email (.+?) (?:about )?(.+)', cmd)
            if match:
                recipient = match.group(1).strip()
                message = match.group(2).strip()
                if self.send_email(recipient, body=message):
                    response = f"Email sent to {recipient} successfully."
                else:
                    response = "I had trouble sending that email. Please check your email configuration."
            else:
                response = "Sure, who should I send an email to and what should it say?"
        
        # System information
        elif 'system info' in cmd or 'system status' in cmd:
            info = self.system_info()
            response = "Here's your system information: " + info
        
        # Web browsing
        elif 'open' in cmd:
            site = re.search(r'open (.+)', cmd)
            if site:
                site_name = site.group(1).strip()
                if self.open_website(site_name):
                    response = f"Opening {site_name} in your browser now."
                else:
                    response = f"Sorry, I couldn't open {site_name}."
            else:
                response = "Which website would you like me to open?"
        
        # Language control
        elif 'language' in cmd or 'speak' in cmd:
            lang_match = re.search(r'(english|amharic|oromo|tigrigna|french|chinese)', cmd)
            if lang_match:
                lang_code = {
                    'english': 'en',
                    'amharic': 'am',
                    'oromo': 'om',
                    'tigrigna': 'ti',
                    'french': 'fr',
                    'chinese': 'zh'
                }.get(lang_match.group(1).lower(), 'en')
                
                if self.change_language(lang_code):
                    response = f"Switched to {lang_match.group(1)}. How can I assist you?"
                else:
                    response = "I couldn't change languages at the moment. Please try again later."
            else:
                response = "Which language would you like me to use? I support English, Amharic, Oromo, Tigrigna, French, and Chinese."
        
        # Privacy features
        elif 'incognito' in cmd:
            enable = 'enable' in cmd or 'on' in cmd
            self.set_incognito(enable)
            status = "enabled" if enable else "disabled"
            response = f"Incognito mode {status}. I won't store any personal data during this session."
        
        elif 'wipe history' in cmd or 'clear data' in cmd:
            if self.wipe_history():
                response = "All personal data has been securely erased."
            else:
                response = "I encountered an issue while wiping data. Please try again."
        
        # Conversational responses
        elif any(greet in cmd for greet in ['hello', 'hi', 'hey', 'greetings']):
            responses = [
                "Hello! How can I assist you today?",
                "Hi there! What can I do for you?",
                "Greetings! I'm here and ready to help."
            ]
            response = random.choice(responses)
        
        elif any(thanks in cmd for thanks in ['thank', 'thanks', 'appreciate']):
            responses = [
                "You're very welcome! Always happy to help.",
                "My pleasure! Let me know if you need anything else.",
                "Glad I could assist! What else can I do for you?"
            ]
            response = random.choice(responses)
        
        elif 'how are you' in cmd:
            responses = [
                "I'm functioning perfectly, thank you for asking! How can I help you?",
                "Doing great and ready to assist! What can I do for you today?",
                "All systems are optimal! How can I be of service?"
            ]
            response = random.choice(responses)
        
        # Exit command
        elif any(exit_cmd in cmd for exit_cmd in ['exit', 'stop', 'sleep', 'goodbye']):
            self.shutdown_flag = True
            responses = [
                "Goodbye! Feel free to call if you need anything.",
                "Shutting down now. Have a wonderful day!",
                "I'll be here when you need me. Take care!"
            ]
            response = random.choice(responses)
        
        else:
            # Contextual fallback responses
            if 'weather' in cmd:
                response = "I'd be happy to check the weather. Where are you located?"
            elif 'news' in cmd:
                response = "I can fetch the latest news. What category interests you?"
            elif 'time' in cmd:
                current_time = datetime.datetime.now().strftime("%I:%M %p")
                response = f"The current time is {current_time}."
            elif 'date' in cmd:
                current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
                response = f"Today is {current_date}."
            else:
                response = "I'm not quite sure I understood. Could you rephrase or ask 'what can you do' for options?"
        
        # Speak the response if we have one
        if response:
            self.speak(response)
        
        return not self.shutdown_flag

    def main_loop(self):
        """Main interaction loop with conversational opening"""
        openings = [
            "Hello! I'm Raki AI, your personal assistant. How can I help?",
            "Good day! I'm here and ready to assist. What can I do for you?",
            "Raki AI activated. How may I assist you today?"
        ]
        self.speak(random.choice(openings))
        
        while not self.shutdown_flag:
            command = self.listen()
            if command:
                if 'help' in command or 'what can you do' in command:
                    help_msg = "I can help with: Installing software, system updates, diagnostics, " \
                              "setting reminders, sending emails, system information, opening websites, " \
                              "changing languages, privacy controls, and more. What would you like to do?"
                    self.speak(help_msg)
                else:
                    self.process_command(command)

if __name__ == "__main__":
    assistant = RakiAI()
    assistant.main_loop()