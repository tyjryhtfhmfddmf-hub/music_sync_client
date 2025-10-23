import tkinter as tk
from tkinter import filedialog, messagebox
import pygame
import random
import os

# Initialize mixer
pygame.mixer.init()

# --- Global State ---
playlist = []
current_index = 0
paused = False
shuffle_mode = False
loop_mode = False


# --- Core Music Functions ---
def load_song(file_path):
    global current_index, playlist
    if file_path not in playlist:
        playlist.append(file_path)
    current_index = playlist.index(file_path)
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play()
    update_status(f"Playing: {os.path.basename(file_path)}")


def play_pause_toggle():
    global paused
    if not pygame.mixer.music.get_busy() and not paused and playlist:
        pygame.mixer.music.play()
        update_status(f"Playing: {os.path.basename(playlist[current_index])}")
    elif not paused:
        pygame.mixer.music.pause()
        paused = True
        update_status("Paused")
    else:
        pygame.mixer.music.unpause()
        paused = False
        update_status(f"Playing: {os.path.basename(playlist[current_index])}")


def next_song():
    global current_index
    if not playlist:
        return
    if shuffle_mode:
        current_index = random.randint(0, len(playlist) - 1)
    else:
        current_index = (current_index + 1) % len(playlist)
    load_song(playlist[current_index])


def prev_song():
    global current_index
    if not playlist:
        return
    current_index = (current_index - 1) % len(playlist)
    load_song(playlist[current_index])


def stop_song():
    pygame.mixer.music.stop()
    update_status("Stopped")


def toggle_loop():
    global loop_mode
    loop_mode = not loop_mode
    loop_btn.config(text=f"Loop: {'ON' if loop_mode else 'OFF'}")
    update_status(f"Loop {'enabled' if loop_mode else 'disabled'}")


def toggle_shuffle():
    global shuffle_mode
    shuffle_mode = not shuffle_mode
    shuffle_btn.config(text=f"Shuffle: {'ON' if shuffle_mode else 'OFF'}")
    update_status(f"Shuffle {'enabled' if shuffle_mode else 'disabled'}")


def add_songs():
    files = filedialog.askopenfilenames(
        title="Select Songs",
        filetypes=(("Audio Files", "*.mp3;*.wav;*.ogg"), ("All Files", "*.*"))
    )
    for f in files:
        if f not in playlist:
            playlist.append(f)
            playlist_box.insert(tk.END, os.path.basename(f))


def play_selected():
    selected = playlist_box.curselection()
    if not selected:
        messagebox.showinfo("No Selection", "Please select a song to play.")
        return
    file = playlist[selected[0]]
    load_song(file)


def update_status(text):
    status_label.config(text=f"Status: {text}")


# --- Tkinter UI ---
root = tk.Tk()
root.title("Music Sync - Local Test Build")
root.geometry("400x400")
root.resizable(False, False)

playlist_box = tk.Listbox(root, width=50, height=10)
playlist_box.pack(pady=10)

add_btn = tk.Button(root, text="Add Songs", command=add_songs)
add_btn.pack(pady=2)

controls_frame = tk.Frame(root)
controls_frame.pack(pady=5)

play_btn = tk.Button(controls_frame, text="▶️ Play / Pause", command=play_pause_toggle)
prev_btn = tk.Button(controls_frame, text="⏮ Prev", command=prev_song)
next_btn = tk.Button(controls_frame, text="⏭ Next", command=next_song)
stop_btn = tk.Button(controls_frame, text="⏹ Stop", command=stop_song)

prev_btn.grid(row=0, column=0, padx=5)
play_btn.grid(row=0, column=1, padx=5)
next_btn.grid(row=0, column=2, padx=5)
stop_btn.grid(row=0, column=3, padx=5)

bottom_frame = tk.Frame(root)
bottom_frame.pack(pady=10)

loop_btn = tk.Button(bottom_frame, text="Loop: OFF", command=toggle_loop)
shuffle_btn = tk.Button(bottom_frame, text="Shuffle: OFF", command=toggle_shuffle)
loop_btn.grid(row=0, column=0, padx=10)
shuffle_btn.grid(row=0, column=1, padx=10)

status_label = tk.Label(root, text="Status: Idle", anchor="w")
status_label.pack(fill="x", padx=10, pady=5)

root.mainloop()
