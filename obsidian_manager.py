import tkinter as tk
import customtkinter
from tkinter import messagebox, simpledialog
import os
import requests
import sys
import json
import threading
from PIL import Image, UnidentifiedImageError

# --- INITIALIZE CUSTOMTKINTER ---
customtkinter.set_appearance_mode("dark")
customtkinter.set_default_color_theme("blue")

# --- SCRIPT SETUP ---
try:
    import google.generativeai as genai
    _HAS_GENAI = True
except ImportError:
    genai = None
    _HAS_GENAI = False

# --- CONFIGURATION ---
class Config:
    def __init__(self):
        self.config_file = "config.json"
        self.defaults = {
            "GEMINI_API_KEY": "YOUR_GEMINI_API_KEY",
            "OBSIDIAN_API_KEY": "YOUR_OBSIDIAN_API_KEY",
            "OBSIDIAN_API_URL": "http://127.0.0.1:27123/"
        }
        self.load()

    def load(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = self.defaults
            self.save()

    def save(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get(self, key):
        return self.config.get(key)

    def set(self, key, value):
        self.config[key] = value
        self.save()

config = Config()

# --- API CLIENTS ---
def configure_gemini():
    global _HAS_GENAI
    api_key = config.get("GEMINI_API_KEY")
    if _HAS_GENAI and api_key and "YOUR_GEMINI_API_KEY" not in api_key:
        try:
            genai.configure(api_key=api_key)
            return True
        except Exception as e:
            print(f"Warning: failed to configure Google Generative AI client: {e}", file=sys.stderr)
            _HAS_GENAI = False
            return False
    return False

configure_gemini()

def get_obsidian_headers():
    return {'Authorization': f'Bearer {config.get("OBSIDIAN_API_KEY")}'}

# --- UI ---
class GeminiApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("Gemini Obsidian Helper")
        self.geometry("800x600")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- TOP BAR ---
        self.top_bar = customtkinter.CTkFrame(self, fg_color="transparent")
        self.top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.top_bar.grid_columnconfigure(0, weight=1)

        self.model_selection_var = customtkinter.StringVar(value="gemini-pro-latest")
        self.model_menu = customtkinter.CTkOptionMenu(self.top_bar,values=["gemini-pro-latest", "gemini-flash-latest"],variable=self.model_selection_var,width=150,height=40,font=("", 17))
        self.model_menu.grid(row=0, column=1, sticky="e")

        self.settings_button = customtkinter.CTkButton(self.top_bar, text="⚙️", command=self.open_settings, width=40, height=40, font=("", 20))
        self.settings_button.grid(row=0, column=2, sticky="e", padx=(10,0))

        # --- CHAT DISPLAY ---
        self.chat_display = customtkinter.CTkScrollableFrame(self, corner_radius=0, fg_color="#1A1A1A")
        self.chat_display.grid(row=1, column=0, sticky="nsew", padx = (10,10))
        self.chat_display.grid_columnconfigure(0, weight=1)

        # --- INPUT FRAME ---
        self.input_frame = customtkinter.CTkFrame(self, corner_radius=0)
        self.input_frame.grid(row=2, column=0, padx=0, pady=0, sticky="ew")
        self.input_frame.grid_columnconfigure(1, weight=1)

        self.attachment_label = customtkinter.CTkLabel(self.input_frame, text="", font=("", 12))
        self.attachment_label.grid(row=1, column=1, padx=10, pady=0, sticky="w")

        self.prompt_entry = customtkinter.CTkEntry(self.input_frame, placeholder_text="Enter your prompt...", font=("", 16), height=40)
        self.prompt_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        self.prompt_entry.bind("<Return>", self.send_prompt)

        self.attach_button = customtkinter.CTkButton(self.input_frame, text="📁", command=self.attach_file, width=40, height=40, font=("", 25))
        self.attach_button.grid(row=0, column=0, padx=10, pady=20)

        self.send_button = customtkinter.CTkButton(self.input_frame, text="➤", command=self.send_prompt, width=40, height=40, font=("", 20))
        self.send_button.grid(row=0, column=2, padx=10, pady=10)

        self.attached_file_path = None

    def add_chat_bubble(self, sender, text):
        if sender == "You":
            bubble_color = "#0078FF"  # Blue for user
            anchor = "e"
            justify = "right"
        else:
            bubble_color = "#4A4A4A"  # Gray for Gemini
            anchor = "w"
            justify = "left"

        bubble_frame = customtkinter.CTkFrame(self.chat_display, fg_color=bubble_color, corner_radius=10)
        bubble_frame.grid(sticky=anchor, padx=10, pady=5)

        text_label = customtkinter.CTkLabel(bubble_frame, text=text, wraplength=600, justify=justify, font=("", 14))
        text_label.pack(padx=10, pady=5)

        self.update_idletasks()
        self.chat_display._parent_canvas.yview_moveto(1.0)
        return text_label

    def attach_file(self):
        file_path = customtkinter.filedialog.askopenfilename()
        if file_path:
            self.attached_file_path = file_path
            self.attachment_label.configure(text=os.path.basename(file_path))

    def send_prompt(self, event=None):
        prompt = self.prompt_entry.get().strip()
        if not prompt and not self.attached_file_path:
            return

        if self.attached_file_path:
            try:
                with open(self.attached_file_path, 'r') as f:
                    file_content = f.read()
                prompt = f"{prompt}\n\n--- Attached File: {os.path.basename(self.attached_file_path)} ---\n{file_content}"
            except Exception as e:
                self.add_chat_bubble("Gemini", f"Error reading file: {e}")
                return

        self.add_chat_bubble("You", prompt)
        self.prompt_entry.delete(0, "end")
        self.attachment_label.configure(text="")
        self.attached_file_path = None


        if not _HAS_GENAI:
            self.add_chat_bubble("Gemini", "Gemini AI is not configured. Please check your API key in the settings.")
            return

        thinking_label = self.add_chat_bubble("Gemini", "Thinking...")
        threading.Thread(target=self.get_gemini_response, args=(prompt, thinking_label)).start()

    def get_gemini_response(self, prompt, thinking_label):
        try:
            model = genai.GenerativeModel(self.model_selection_var.get())
            response = model.generate_content(prompt)
            self.update_chat_box(response.text, thinking_label)
        except Exception as e:
            self.update_chat_box(f"Error: {e}", thinking_label)

    def update_chat_box(self, text, thinking_label):
        thinking_label.configure(text=text)


    def open_settings(self):
        settings_window = customtkinter.CTkToplevel(self)
        settings_window.title("Settings")
        settings_window.geometry("400x300")

        gemini_api_key_label = customtkinter.CTkLabel(settings_window, text="Gemini API Key:")
        gemini_api_key_label.pack(pady=5)
        gemini_api_key_entry = customtkinter.CTkEntry(settings_window, width=350)
        gemini_api_key_entry.insert(0, config.get("GEMINI_API_KEY"))
        gemini_api_key_entry.pack(pady=5)

        obsidian_api_key_label = customtkinter.CTkLabel(settings_window, text="Obsidian API Key:")
        obsidian_api_key_label.pack(pady=5)
        obsidian_api_key_entry = customtkinter.CTkEntry(settings_window, width=350)
        obsidian_api_key_entry.insert(0, config.get("OBSIDIAN_API_KEY"))
        obsidian_api_key_entry.pack(pady=5)

        obsidian_api_url_label = customtkinter.CTkLabel(settings_window, text="Obsidian API URL:")
        obsidian_api_url_label.pack(pady=5)
        obsidian_api_url_entry = customtkinter.CTkEntry(settings_window, width=350)
        obsidian_api_url_entry.insert(0, config.get("OBSIDIAN_API_URL"))
        obsidian_api_url_entry.pack(pady=5)

        def save_settings():
            config.set("GEMINI_API_KEY", gemini_api_key_entry.get())
            config.set("OBSIDIAN_API_KEY", obsidian_api_key_entry.get())
            config.set("OBSIDIAN_API_URL", obsidian_api_url_entry.get())
            configure_gemini()
            settings_window.destroy()

        save_button = customtkinter.CTkButton(settings_window, text="Save", command=save_settings)
        save_button.pack(pady=20)


if __name__ == "__main__":
    app = GeminiApp()
    app.mainloop()