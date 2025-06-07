# Raki AI Assistant

Raki AI is a cross-platform, voice-activated personal assistant built in Python. It performs common tasks via natural language input, such as running terminal commands, checking system health, sending emails, and browsing the web.

## 🚀 Features

### 🎤 1. Voice Recognition

- Listens via the system microphone using the `speech_recognition` library.
- Transcribes spoken commands into text using Google Speech Recognition.
- Handles ambient noise and network errors gracefully.

### 🔊 2. Text-to-Speech (TTS)

- Speaks responses using `pyttsx3`, with customizable voice, rate, and volume.
- Offline-capable text-to-speech engine.

### 🧾 3. Terminal Command Execution

- Executes system commands like install and update via the shell.
- Reports success or failure and displays command output.

### ⚙️ 4. System Diagnostics

- Monitors CPU, RAM, and Disk usage with `psutil`.
- Alerts the user if:
  - CPU or RAM > 85%
  - Disk usage > 90%

### 📅 5. Reminders

- Allows the user to set simple text-based reminders.
- Appends reminders to a local `reminders.txt` file.

### 📧 6. Email Sending

- Sends emails via Gmail SMTP.
- Prompts for subject, body, and recipient address.
- Uses the `smtplib` and `email.message` libraries.

### 💻 7. System Info

- Provides OS and version details using the `platform` module.

### 🌐 8. Website Opening

- Opens websites in the default browser using `webbrowser`.
- Automatically constructs full URLs from site names.

### ❌ 9. Voice-Controlled Exit

- Recognizes commands like "exit" or "stop" to quit the assistant.

## ✅ Example Commands

- "Install VLC"
- "Update system"
- "Diagnose"
- "Set reminder take medicine"
- "Send email"
- "Open YouTube"
- "System info"
- "Exit"

## 📌 Notes

- Gmail credentials are hardcoded in the script. **Use environment variables or a secure method in production.**
- Some features may require Linux-like environments (e.g., `sudo apt install`).
- This assistant runs in an infinite loop and is terminated only by a user command.

## 🔧 Requirements

```bash
# Core dependencies
sudo apt install python3-pyaudio festival festvox-kallpc16k

# Python packages
pip install speechrecognition pyttsx3 requests beautifulsoup4 geocoder python-nmap pillow cryptography langdetect

# For Google TTS
pip install gtts playsound

# For Vosk STT
pip install vosk
```

## 👨‍💻 Author

Kidus Bizuneh Desta  
Grade 12 Student, Negele Arsi Kuyera Adventist Secondary School

## 📄 License

This project is open-source and free to use under the MIT License.
```
