import tkinter as tk
import customtkinter
from tkinter import messagebox
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
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'YOUR_GEMINI_API_KEY')
OBSIDIAN_API_KEY = os.environ.get('OBSIDIAN_API_KEY', 'YOUR_OBSIDIAN_API_KEY')
OBSIDIAN_API_URL = os.environ.get('OBSIDIAN_API_URL', 'https://127.0.0.1:2724')

if _HAS_GENAI and GEMINI_API_KEY and GEMINI_API_KEY != 'YOUR_GEMINI_API_KEY':
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Warning: failed to configure Google Generative AI client: {e}", file=sys.stderr)
        _HAS_GENAI = False

selected_image_path = None
welcome_label = None

# --- HELPER FUNCTIONS ---
def get_obsidian_headers():
    return {'Authorization': f'Bearer {OBSIDIAN_API_KEY}'}

def hide_welcome_message():
    global welcome_label
    if welcome_label:
        welcome_label.destroy()
        welcome_label = None

# --- OBSIDIAN FUNCTIONS ---
def read_note(note_title):
    # This function and other Obsidian functions (save, delete) remain the same.
    # ... (code for read_note, save_note, delete_note is unchanged)
    if not note_title:
        return
    hide_welcome_message()
    note_path = f"/vault/{requests.utils.quote(note_title)}.md"
    try:
        response = requests.get(OBSIDIAN_API_URL + note_path, headers=get_obsidian_headers(), verify=False)
        response.raise_for_status()
        chat_box.delete("1.0", "end")
        chat_box.insert("0.0", response.text)
        status_label.configure(text=f"Successfully loaded '{note_title}'.")
    except requests.exceptions.RequestException:
        messagebox.showerror("API Error", f"Note '{note_title}' not found or API issue.")
        status_label.configure(text=f"Error loading '{note_title}'.")

def save_note(note_title):
    content = chat_box.get("1.0", "end-1c").strip()
    if not content or (welcome_label is not None):
        return
    if not note_title:
        return
    note_path = f"/vault/{requests.utils.quote(note_title)}.md"
    try:
        response = requests.put(OBSIDIAN_API_URL + note_path, headers=get_obsidian_headers(), data=content.encode('utf-8'), verify=False)
        response.raise_for_status()
        messagebox.showinfo("Success", f"Note '{note_title}' has been saved.")
        status_label.configure(text=f"Note '{note_title}' saved successfully.")
    except requests.exceptions.RequestException as e:
        messagebox.showerror("API Error", f"Failed to save note: {e}")
        status_label.configure(text="Error saving note.")

def delete_note(note_title):
    if not note_title:
        return
    if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to permanently delete '{note_title}'?"):
        return
    hide_welcome_message()
    note_path = f"/vault/{requests.utils.quote(note_title)}.md"
    try:
        response = requests.delete(OBSIDIAN_API_URL + note_path, headers=get_obsidian_headers(), verify=False)
        response.raise_for_status()
        chat_box.delete("1.0", "end")
        messagebox.showinfo("Success", f"Note '{note_title}' has been deleted.")
        status_label.configure(text=f"Note '{note_title}' deleted.")
    except requests.exceptions.RequestException as e:
        messagebox.showerror("API Error", f"Failed to delete note: {e}")
        status_label.configure(text="Error deleting note.")

# --- CORE LOGIC ---
def parse_command(prompt_snippet):
    system_prompt = "..." # Kept for brevity
    try:
        # --- DYNAMICALLY GET SELECTED MODEL ---
        # Use the faster flash model for quick command parsing
        parser_model = genai.GenerativeModel('gemini-flash-latest')
        response = parser_model.generate_content(system_prompt + "\nUser: " + prompt_snippet)
        json_response = response.text.strip().replace("`", "").replace("json", "")
        return json.loads(json_response)
    except Exception:
        return {"action": "ask_gemini", "filename": None}

def ask_gemini_for_answer(prompt):
    global selected_image_path
    hide_welcome_message()
    
    chat_box.delete("1.0", "end")
    chat_box.insert("end", f"👤 You:\n{prompt}\n\n")
    status_label.configure(text="Asking Gemini...")
    app.update_idletasks()
    
    try:
        content_to_send = [prompt]
        if selected_image_path:
            img = Image.open(selected_image_path)
            content_to_send.append(img)

        # --- DYNAMICALLY GET SELECTED MODEL ---
        # Get the user's choice from the dropdown menu variable
        selected_model_name = model_selection_var.get()
        chat_model = genai.GenerativeModel(selected_model_name)
        
        response = chat_model.generate_content(content_to_send)
        chat_box.insert("end", f"✨ Gemini:\n{response.text}")
        status_label.configure(text="Ready.")
    except Exception as e:
        messagebox.showerror("Gemini API Error", f"An error occurred: {e}")
        status_label.configure(text="Error with Gemini request.")
    finally:
        selected_image_path = None

def handle_prompt():
    prompt = prompt_entry.get().strip()
    if not prompt:
        return

    prompt_entry.delete(0, "end")
    status_label.configure(text="Parsing command...")

    prompt_snippet_for_parsing = prompt[:100]
    command = parse_command(prompt_snippet_for_parsing)

    action = command.get("action")
    filename = command.get("filename")

    if action == "save_note":
        save_note(filename)
    elif action == "read_note":
        read_note(filename)
    elif action == "delete_note":
        delete_note(filename)
    else:
        ask_gemini_for_answer(prompt)

def start_handle_prompt_thread(event=None):
    thread = threading.Thread(target=handle_prompt, daemon=True)
    thread.start()

def attach_image():
    global selected_image_path
    filepath = customtkinter.filedialog.askopenfilename(title="Select an image", filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp")])
    if filepath:
        selected_image_path = filepath
        status_label.configure(text=f"Image ready: {os.path.basename(filepath)}")
        prompt_entry.focus()

# --- BUILD UI ---
app = customtkinter.CTk()
app.title('Gemini Obsidian Helper')
app.geometry('800x600')

app.grid_columnconfigure(0, weight=1)
app.grid_rowconfigure(0, weight=1)

chat_frame = customtkinter.CTkFrame(app, corner_radius=0)
chat_frame.grid(row=0, column=0, sticky="nsew")

chat_box = customtkinter.CTkTextbox(chat_frame, wrap=tk.WORD, font=("", 16), corner_radius=0, border_width=0)
chat_box.pack(fill="both", expand=True)

welcome_font = customtkinter.CTkFont(size=32, weight="bold")
welcome_label = customtkinter.CTkLabel(chat_frame, text="What can I help with?", font=welcome_font, fg_color="transparent")
welcome_label.place(relx=0.5, rely=0.4, anchor="center")

input_frame = customtkinter.CTkFrame(app, corner_radius=0)
input_frame.grid(row=1, column=0, padx=0, pady=0, sticky="ew")
input_frame.grid_columnconfigure(1, weight=1)

attach_button = customtkinter.CTkButton(input_frame, text="📎", command=attach_image, width=40, font=("", 18))
attach_button.grid(row=0, column=0, padx=10, pady=10)

prompt_entry = customtkinter.CTkEntry(input_frame, placeholder_text="Ask a question or give a command...", font=("", 16), height=40)
prompt_entry.grid(row=0, column=1, padx=0, pady=10, sticky="ew")
prompt_entry.bind("<Return>", start_handle_prompt_thread)

send_button = customtkinter.CTkButton(input_frame, text="➤", command=start_handle_prompt_thread, width=40, height=40, font=("", 20))
send_button.grid(row=0, column=2, padx=10, pady=10)

# --- NEW: MODEL SELECTION WIDGETS ---
model_frame = customtkinter.CTkFrame(app, corner_radius=0)
model_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0,5))

model_label = customtkinter.CTkLabel(model_frame, text="Model:")
model_label.pack(side="left", padx=(10,5))

# Variable to store the current selection
model_selection_var = customtkinter.StringVar(value="gemini-pro-latest")

model_menu = customtkinter.CTkOptionMenu(model_frame, 
                                         values=["gemini-pro-latest", "gemini-flash-latest"],
                                         variable=model_selection_var)
model_menu.pack(side="left", padx=5)
# --- END NEW WIDGETS ---

# Status Bar - moved to the last row
status_frame = customtkinter.CTkFrame(app, corner_radius=0, height=25)
status_frame.grid(row=3, column=0, sticky="ew") # Now at row 3
status_label = customtkinter.CTkLabel(status_frame, text='Ready', anchor='w')
status_label.pack(side="left", padx=10)

if __name__ == '__main__':
    prompt_entry.focus()
    app.mainloop()
