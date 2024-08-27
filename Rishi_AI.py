import os
import sys
import subprocess
import speech_recognition as sr
import logging
import pygame
import psutil
import getpass
import platform
import pyautogui
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from groq import Groq
from AI_Creds import GROQ_API_KEY

# Get the directory where the executable is located
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

os.chdir(application_path)

# Constants

PING_SOUND_FILE = r"aud\\ls.wav"
PONG_SOUND_FILE = r"aud\\le.wav"

# Initialize the Groq client
client = Groq(api_key=GROQ_API_KEY)

# Setup logging
log_file = "terminal_output.log"
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(message)s')

# Initialize pygame mixer
pygame.mixer.init()

def play_sound(sound_file):
    """Play a sound using pygame."""
    try:
        sound = pygame.mixer.Sound(sound_file)
        sound.play()
    except pygame.error as e:
        print(f"Error playing sound {sound_file}: {e}")

def get_os_type():
    """Detects the operating system and returns 'Windows' or 'Linux/Mac'."""
    return 'Windows' if os.name == 'nt' else 'Linux/Mac'

def get_system_info():
    """Retrieves system information: username, CPU, GPU, and RAM."""
    username = getpass.getuser()
    cpu_info = platform.processor() or "Unknown CPU"
    ram_info = f"{round(psutil.virtual_memory().total / (1024 ** 3), 2)} GB"

    if platform.system() == 'Windows':
        try:
            gpu_info = subprocess.check_output(["wmic", "path", "win32_VideoController", "get", "Caption"], text=True).strip()
        except Exception:
            gpu_info = "GPU info not available"
    elif platform.system() == 'Linux':
        try:
            gpu_info = subprocess.check_output(["lspci", "|", "grep", "VGA"], text=True).strip()
        except Exception:
            gpu_info = "GPU info not available"
    else:
        gpu_info = "GPU info not available"

    return {
        "username": username,
        "cpu": cpu_info,
        "ram": ram_info,
        "gpu": gpu_info
    }

def generate_command(task_description, os_type):
    """Generates a command or multiple commands based on the task description and the detected OS type."""
    system_info = get_system_info()
    
    system_prompt = (
        f"You are a command generation assistant. Based on the task provided, you will generate executable commands for either PowerShell (Windows) or Bash (Linux/Mac). "
        f"The current system information is as follows:\n"
        f"- **Username**: {system_info['username']}\n"
        f"- **CPU**: {system_info['cpu']}\n"
        f"- **RAM**: {system_info['ram']}\n"
        f"- **GPU**: {system_info['gpu']}\n\n"
        "Your responses should be in plain text and formatted as commands that can be directly executed in the specified shell.\n\n"
        "The Python script will detect the operating system and provide you with this information. Depending on whether the OS is Windows or Linux/Mac, you will output commands for the appropriate shell:\n\n"
        "1. **If the OS is Windows**, respond with PowerShell commands.\n"
        "2. **If the OS is Linux or Mac**, respond with Bash commands.\n\n"
        "Make sure that:\n"
        "- The output is a single or multiple commands that can be executed directly (commands should be newline-separated).\n"
        "- Do not include explanations or additional text; only the commands are needed.\n"
        "- Commands should be safe and effective for the given task.\n\n"
        "For example:\n"
        "- **For Windows/PowerShell:** `Get-ChildItem`\n"
        "- **For Linux/Bash:** `ls -l`\n\n"
        "You should **never use default values or placeholders**. If additional information is needed to perform a task, always request this information explicitly using commands.\n"
        "For example, if you need a file path, ask for it as a command instead of using a placeholder path.\n\n"
        "Your responses should be in plain text and formatted as commands that can be directly executed in the specified shell.\n\n"
        "If you need to ask for more information, use the following format:\n"
        "- **Request**: [Information Needed]\n\n"
        "When providing commands, ensure they are appropriate for the task and the environment they are meant to run in. Use pyautogui for tasks requiring GUI interaction."
        "Make sure you give commands in such a way that it doesn't give errors like 'returned non-zero exit status 1\n"
        "If on windows, make sure you Set Execution Policy unrestricted for Powershell before executing commands\n"
        "When it comes to creating any document, don't give sample template file path, just assume the said program is in environment variables and use it directly. Same goes for folders like Documents,Downloads etc\n"
        "When the user asks a question of sorts (for example 'say this', what is '....' ?, 'tell me '.....', and so on'), use system.speech to speak out the answer loud\n"
        "when the user asks you to launch something, just directly launch the exe instead of trying to mention a file path."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Task: {task_description}\nOS Type: {os_type}"}
    ]

    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
            model="llama3-70b-8192"  # Ensure this is the correct model for your API
        )
        response_content = chat_completion.choices[0].message.content.strip()
        
        # Check if the response is a request for more information
        if response_content.startswith("Request:"):
            return {"request": response_content[len("Request:"):].strip(), "commands": None}
        else:
            return {"request": None, "commands": response_content}
    except Exception as e:
        logging.error(f"Error calling Groq API: {e}")
        return {"request": None, "commands": ""}

def execute_command(command, os_type):
    """Executes a single command based on the OS type and logs the output."""
    try:
        if os_type == 'Windows':
            process = subprocess.run(["powershell", "-Command", command], check=True, text=True, capture_output=True)
        else:
            process = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
            
        output = process.stdout
        logging.info(f"Command output:\n{output}")
        print(f"Command output:\n{output}")
    except subprocess.CalledProcessError as e:
        output = e.output
        logging.error(f"Error executing command: {e}")
        logging.error(f"Command output:\n{output}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

def handle_gui_interaction(command):
    """Handles GUI interactions using pyautogui based on the command."""
    try:
        if "type" in command:
            text_to_type = command.split("type")[1].strip()
            pyautogui.typewrite(text_to_type)
        elif "click" in command:
            x, y = map(int, re.findall(r'\d+', command))
            pyautogui.click(x, y)
        elif "alt+f4" in command:
            pyautogui.hotkey('alt', 'f4')
        else:
            logging.error(f"Unknown GUI interaction command: {command}")
    except Exception as e:
        logging.error(f"Error handling GUI interaction: {command}")
        logging.error(f"Error details: {e}")

def execute_commands(commands, os_type):
    """Executes multiple commands based on the OS type and logs the output."""
    with ThreadPoolExecutor() as executor:
        futures = []
        for command in commands:
            command = command.strip()
            if "type" in command or "click" in command or "alt+f4" in command:
                # Handle GUI interaction commands
                futures.append(executor.submit(handle_gui_interaction, command))
            else:
                # Execute non-GUI commands
                futures.append(executor.submit(execute_command, command, os_type))
        
        # Wait for all futures to complete
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logging.error(f"Exception in command execution: {e}")
                print(f"Exception in command execution: {e}")

def handle_quit_command():
    """Handles quit commands and terminates the program."""
    print("Quitting...")
    pygame.mixer.quit()
    sys.exit()

def listen_for_command():
    """Listens for the activation phrases and then listens for further commands."""
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    activation_phrases = ["hey rishi", "yo rishi", "hey laptop", "yo laptop", "hey man", "Hey pc", "yo pc", "yo man", "ay rishi", "ay pc"]
    quit_phrases = ["rishi quit", "quit now"]

    while True:
        with mic as source:
            print("Listening for activation phrase...")
            audio = recognizer.listen(source)

        try:
            text = recognizer.recognize_google(audio).lower()
            print(f"Heard: {text}")

            if any(phrase in text for phrase in quit_phrases):
                handle_quit_command()

            if any(phrase in text for phrase in activation_phrases):
                play_sound(PING_SOUND_FILE)
                print("Activation phrase detected. Listening for commands...")

                # Switch to command listening mode
                while True:
                    with mic as source:
                        print("Listening for command...")
                        audio = recognizer.listen(source)

                    try:
                        command_text = recognizer.recognize_google(audio).lower()
                        print(f"Heard command: {command_text}")

                        if any(phrase in command_text for phrase in quit_phrases):
                            handle_quit_command()

                        os_type = get_os_type()
                        result = generate_command(command_text, os_type)
                        
                        if result["request"]:
                            print(f"Request for more information: {result['request']}")
                        else:
                            commands = result["commands"].split('\n')
                            execute_commands(commands, os_type)
                            play_sound(PONG_SOUND_FILE)

                        # Exit command listening mode and return to activation phrase listening
                        break

                    except sr.UnknownValueError:
                        print("Sorry, I did not understand that.")
                    except sr.RequestError as e:
                        print(f"Error with the speech recognition service: {e}")

        except sr.UnknownValueError:
            print("Sorry, I did not understand that.")
        except sr.RequestError as e:
            print(f"Error with the speech recognition service: {e}")

if __name__ == "__main__":
    listen_for_command()

