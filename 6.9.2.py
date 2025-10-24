# -----------------------------
# IMPORTS
# -----------------------------

import os
import random
import pygame
import json
import threading, time, requests
from tkinter import *
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD
from tkinter import simpledialog, ttk


# -----------------------------
# ROOT WINDOW
# -----------------------------
root = TkinterDnD.Tk()
root.title("Music Sync App")
root.geometry("500x800")
root.resizable(False, False)

# ---------------------------------------
# CONFIGURATION
# ---------------------------------------

RELAY_URL = "https://music-sync-relay.onrender.com"   # change this to your deployed relay
POLL_INTERVAL = 2  # seconds between polling for commands
KEEP_ALIVE_INTERVAL = 30  # seconds between keep-alive pings

pygame.mixer.init()

LIBRARY_FILE = "library.json"
PLAYLISTS_DIR = "playlists"
os.makedirs(PLAYLISTS_DIR, exist_ok=True)
current_index = 0
paused = False
shuffle_mode = False
loop_mode = False
shuffled_order = []
room_code = None
session_active = False
is_host = False


# ---------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------

def load_library():
    if os.path.exists(LIBRARY_FILE):
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return data.get("songs", [])
            except json.JSONDecodeError:
                return []
    return []


def save_library():
    with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
        json.dump({"songs": library}, f, indent=2)


def save_playlist():
    """Save current playlist order to a persistent file."""
    with open("current_playlist.json", "w", encoding="utf-8") as f:
        json.dump({"playlist": playlist, "current_index": current_index}, f, indent=2)


def load_saved_playlist():
    """Load the last saved playlist state."""
    if os.path.exists("current_playlist.json"):
        try:
            with open("current_playlist.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("playlist", []), data.get("current_index", 0)
        except json.JSONDecodeError:
            return [], 0
    return [], 0


playlist = []
library = load_library()


def update_status(text):
    status_label.config(text=f"Status: {text}")


def refresh_library_view():
    """Refresh the library listbox to show all songs in the library."""
    playlist_box.delete(0, END)
    for song in library:
        playlist_box.insert(END, os.path.basename(song))


def add_songs():
    files = filedialog.askopenfilenames(
        title="Select Songs",
        filetypes=(("Audio Files", "*.mp3;*.wav;*.ogg"), ("All Files", "*.*"))
    )

    added = 0
    for f in files:
        if f not in library:
            library.append(f)
            added += 1
        if f not in playlist:
            playlist.append(f)

    save_library()
    save_playlist()
    refresh_library_view()
    refresh_queue_view()
    update_status(f"Added {added} new songs to library.")


def add_folder():
    folder = filedialog.askdirectory(title="Select Folder")
    if not folder:
        return

    files = [f for f in os.listdir(folder) if f.lower().endswith(('.mp3', '.wav', '.ogg'))]
    added = 0

    for file in files:
        path = os.path.join(folder, file)
        if path not in library:
            library.append(path)
            added += 1
        if path not in playlist:
            playlist.append(path)

    save_library()
    save_playlist()
    refresh_library_view()
    refresh_queue_view()
    update_status(f"Added {added} new songs from folder.")


def on_library_double_click(event):
    """Add a song from the library to the playlist when double-clicked."""
    selection = playlist_box.curselection()
    if not selection:
        return
    
    index = selection[0]
    if index < len(library):
        song_path = library[index]
        if song_path not in playlist:
            playlist.append(song_path)
            save_playlist()
            refresh_queue_view()
            update_status(f"Added to queue: {os.path.basename(song_path)}")
        else:
            update_status(f"Already in queue: {os.path.basename(song_path)}")


def save_current_as_playlist():
    if not playlist:
        messagebox.showinfo("Save Playlist", "No songs in the queue to save.")
        return

    name = simpledialog.askstring("Save Playlist", "Enter a playlist name:")
    if not name:
        return

    data = {"name": name, "songs": playlist}
    filepath = os.path.join(PLAYLISTS_DIR, f"{name}.json")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    messagebox.showinfo("Playlist Saved", f"Saved as '{name}' successfully.")


def load_playlist_from_file():
    files = [f for f in os.listdir(PLAYLISTS_DIR) if f.endswith(".json")]
    if not files:
        messagebox.showinfo("Load Playlist", "No playlists found.")
        return

    name = simpledialog.askstring(
        "Load Playlist",
        "Available playlists:\n" + "\n".join(files) + "\n\nEnter playlist name (without .json):"
    )

    if not name:
        return

    filepath = os.path.join(PLAYLISTS_DIR, f"{name}.json")
    if not os.path.exists(filepath):
        messagebox.showerror("Error", "Playlist not found.")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    global playlist, current_index
    playlist = data.get("songs", [])
    current_index = 0 if playlist else -1
    refresh_queue_view()
    save_playlist()
    messagebox.showinfo("Playlist Loaded", f"Loaded '{name}' successfully.")


# ---------------------------------------
# MUSIC CONTROL
# ---------------------------------------
def load_song(file_path):
    global current_index, playlist, paused
    if file_path not in playlist:
        playlist.append(file_path)
    current_index = playlist.index(file_path)
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play()
    paused = False
    refresh_queue_view()
    update_status(f"Playing: {os.path.basename(file_path)}")
    if is_host:
        send_command("play", current_index)


def play_pause_toggle():
    global paused, current_index
    if not playlist:
        update_status("No songs in playlist")
        return
    
    if not pygame.mixer.music.get_busy() and not paused:
        # Start playing from current index
        if current_index < 0 or current_index >= len(playlist):
            current_index = 0
        load_song(playlist[current_index])
    elif not paused:
        pygame.mixer.music.pause()
        paused = True
        update_status("Paused")
        if is_host:
            send_command("pause", current_index)
    else:
        pygame.mixer.music.unpause()
        paused = False
        update_status(f"Playing: {os.path.basename(playlist[current_index])}")
        if is_host:
            send_command("unpause", current_index)


def next_song(auto=False):
    global current_index, shuffled_order
    if not playlist:
        return
    if loop_mode and auto:
        pygame.mixer.music.play()
        return
    if shuffle_mode:
        if not shuffled_order:
            shuffled_order = random.sample(range(len(playlist)), len(playlist))
        current_index = shuffled_order.pop(0)
    else:
        current_index = (current_index + 1) % len(playlist)
    refresh_queue_view()
    load_song(playlist[current_index])


def prev_song():
    global current_index
    if not playlist:
        return
    current_index = (current_index - 1) % len(playlist)
    refresh_queue_view()
    load_song(playlist[current_index])


def stop_song():
    pygame.mixer.music.stop()
    update_status("Stopped")
    if is_host:
        send_command("stop", current_index)


def toggle_loop():
    global loop_mode
    loop_mode = not loop_mode
    loop_btn.config(text=f"Loop: {'ON' if loop_mode else 'OFF'}")
    update_status(f"Loop {'enabled' if loop_mode else 'disabled'}")


def shuffle_playlist():
    global playlist, current_index
    if not playlist:
        return

    current_song = None
    if current_index != -1 and current_index < len(playlist):
        current_song = playlist[current_index]

    random.shuffle(playlist)

    if current_song and current_song in playlist:
        playlist.remove(current_song)
        playlist.insert(0, current_song)
        current_index = 0

    refresh_queue_view()
    save_playlist()
    update_status("Playlist shuffled.")


# --------------- Volume Control ---------------
volume_frame = Frame(root)
volume_frame.pack(pady=5)

volume_label = Label(volume_frame, text="Volume:")
volume_label.pack(side=LEFT, padx=5)

# Mute button state
is_muted = False
volume_before_mute = 0.7

def toggle_mute():
    """Toggle mute on/off."""
    global is_muted, volume_before_mute
    if is_muted:
        # Unmute - restore previous volume
        pygame.mixer.music.set_volume(volume_before_mute)
        volume_slider.set(volume_before_mute)
        mute_btn.config(text="🔊 Mute")
        is_muted = False
        update_status(f"Unmuted - Volume: {int(volume_before_mute * 100)}%")
    else:
        # Mute - save current volume and set to 0
        volume_before_mute = volume_slider.get()
        pygame.mixer.music.set_volume(0)
        mute_btn.config(text="🔇 Unmute")
        is_muted = True
        update_status("Muted")

mute_btn = Button(volume_frame, text="🔊 Mute", command=toggle_mute, width=10)
mute_btn.pack(side=LEFT, padx=5)

# Custom Scale class to prevent clicking to jump
class SmoothScale(ttk.Scale):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


volume_slider = SmoothScale(volume_frame, from_=0, to=1, orient="horizontal", value=0.7, length=180,
                            command=lambda v: set_volume(float(v)))
volume_slider.pack(side=LEFT, padx=5)


def set_volume(value):
    """Set the playback volume (0.0 to 1.0)."""
    global is_muted, volume_before_mute
    try:
        val = float(value)
        pygame.mixer.music.set_volume(val)
        
        # Update mute button if volume changed while muted
        if is_muted and val > 0:
            is_muted = False
            mute_btn.config(text="🔊 Mute")
        
        # Save volume (but not if muted)
        if not is_muted:
            volume_before_mute = val
            with open("settings.json", "w") as f:
                json.dump({"volume": val}, f)
        
        update_status(f"Volume: {int(val * 100)}%")
    except Exception as e:
        update_status(f"Volume error: {e}")


# Load saved volume
try:
    with open("settings.json", "r") as f:
        settings = json.load(f)
        last_volume = settings.get("volume", 0.7)
        volume_before_mute = last_volume
        pygame.mixer.music.set_volume(last_volume)
        volume_slider.set(last_volume)
except FileNotFoundError:
    pygame.mixer.music.set_volume(0.7)
    volume_before_mute = 0.7


# ---------------------------------------
# SONG END DETECTION
# ---------------------------------------
last_playing_state = False


def check_song_end():
    global last_playing_state
    is_playing = pygame.mixer.music.get_busy()
    
    if playlist and 0 <= current_index < len(playlist):
        queue_list.select_clear(0, END)
        queue_list.select_set(current_index)
        queue_list.see(current_index)

    if last_playing_state and not is_playing and not paused:
        handle_song_finished()

    last_playing_state = is_playing
    root.after(1000, check_song_end)


def handle_song_finished():
    """Called automatically when a song ends."""
    global loop_mode
    if loop_mode:
        pygame.mixer.music.play()
    else:
        next_song(auto=True)


# ---------------------------------------
# QUEUE (Up Next) with Drag-and-Drop
# ---------------------------------------
queue_frame = Frame(root)
queue_frame.pack(pady=10)

Label(queue_frame, text="🎵 Up Next (Drag to Reorder)").pack()

queue_list = Listbox(queue_frame, width=50, selectmode=SINGLE)
queue_list.pack()

drag_start_index = None


def on_drag_start(event):
    global drag_start_index
    widget = event.widget
    drag_start_index = widget.nearest(event.y)


def on_drag_motion(event):
    pass


def on_drag_drop(event):
    global drag_start_index, current_index
    widget = event.widget
    drop_index = widget.nearest(event.y)
    if drop_index == drag_start_index or drag_start_index is None:
        return

    current_song = playlist[current_index] if 0 <= current_index < len(playlist) else None

    song = playlist.pop(drag_start_index)
    playlist.insert(drop_index, song)

    if current_song in playlist:
        current_index = playlist.index(current_song)

    refresh_queue_view()
    save_playlist()
    queue_list.select_clear(0, END)
    queue_list.select_set(drop_index)
    if 0 <= current_index < len(playlist):
        queue_list.see(current_index)
    drag_start_index = None


queue_list.bind("<Button-1>", on_drag_start)
queue_list.bind("<B1-Motion>", on_drag_motion)
queue_list.bind("<ButtonRelease-1>", on_drag_drop)


def refresh_queue_view():
    queue_list.delete(0, END)
    if not playlist:
        return
    for i, song in enumerate(playlist):
        display = os.path.basename(song)
        if i == current_index:
            display = f"▶ {display}"
        queue_list.insert(END, display)


# ---------------------------------------
# NETWORK RELAY FUNCTIONS
# ---------------------------------------

def host_session():
    global room_code, session_active, is_host
    try:
        res = requests.post(f"{RELAY_URL}/host", timeout=5)
        data = res.json()
        room_code = data["room_code"]
        is_host = True
        session_active = True
        update_status(f"Hosting session • Room code: {room_code}")
        start_keep_alive()
        threading.Thread(target=poll_commands, daemon=True).start()
    except Exception as e:
        update_status(f"Failed to host: {e}")


def join_session():
    global room_code, session_active, is_host
    code = room_entry.get().strip()
    if not code:
        update_status("Please enter a room code.")
        return
    try:
        res = requests.post(f"{RELAY_URL}/join/{code}", timeout=5)
        if res.status_code == 200:
            room_code = code
            is_host = False
            session_active = True
            update_status(f"Joined room: {room_code}")
            start_keep_alive()
            threading.Thread(target=poll_commands, daemon=True).start()
        else:
            update_status("Room not found.")
    except Exception as e:
        update_status(f"Join failed: {e}")


def send_command(command, index=None):
    """Send a command to the relay server."""
    if not room_code or not is_host:
        return
    try:
        payload = {"command": command}
        if index is not None:
            payload["index"] = index
        requests.post(f"{RELAY_URL}/send/{room_code}", json=payload, timeout=5)
        print(f"Sent command: {command}")
    except Exception as e:
        print(f"Send failed: {e}")


def poll_commands():
    """Poll for commands from the relay server."""
    global session_active
    while session_active:
        try:
            res = requests.get(f"{RELAY_URL}/receive/{room_code}", timeout=5)
            data = res.json()
            commands = data.get("commands", [])
            for cmd_data in commands:
                process_command(cmd_data)
        except Exception as e:
            print(f"Poll error: {e}")
        time.sleep(POLL_INTERVAL)


def process_command(cmd_data):
    """Process a received command."""
    global current_index, paused
    
    if isinstance(cmd_data, str):
        command = cmd_data
        index = None
    else:
        command = cmd_data.get("command", "")
        index = cmd_data.get("index")
    
    print(f"Processing command: {command}, index: {index}")
    
    if command == "play" and index is not None:
        if 0 <= index < len(playlist):
            current_index = index
            pygame.mixer.music.load(playlist[current_index])
            pygame.mixer.music.play()
            paused = False
            refresh_queue_view()
            update_status(f"Playing: {os.path.basename(playlist[current_index])}")
    elif command == "pause":
        pygame.mixer.music.pause()
        paused = True
        update_status("Paused")
    elif command == "unpause":
        pygame.mixer.music.unpause()
        paused = False
        update_status("Resumed")
    elif command == "stop":
        pygame.mixer.music.stop()
        update_status("Stopped")


def keep_alive():
    """Keep the relay server connection alive."""
    while session_active:
        try:
            requests.get(f"{RELAY_URL}/ping", timeout=5)
            print("🟢 Relay pinged (alive)")
        except Exception as e:
            print("🔴 Ping failed:", e)
        time.sleep(KEEP_ALIVE_INTERVAL)


def start_keep_alive():
    threading.Thread(target=keep_alive, daemon=True).start()


# ---------------------------------------
# TKINTER UI
# ---------------------------------------

# Library Section
library_frame = LabelFrame(root, text="📚 Library (Double-click to add to queue)")
library_frame.pack(pady=5, padx=10, fill=BOTH)

playlist_box = Listbox(library_frame, width=55, height=8)
playlist_box.pack(pady=5)
playlist_box.bind("<Double-Button-1>", on_library_double_click)

top_frame = Frame(root)
top_frame.pack()

add_btn = Button(top_frame, text="Add Files", command=add_songs)
add_folder_btn = Button(top_frame, text="Add Folder", command=add_folder)
add_btn.grid(row=0, column=0, padx=5)
add_folder_btn.grid(row=0, column=1, padx=5)

controls_frame = Frame(root)
controls_frame.pack(pady=10)
prev_btn = Button(controls_frame, text="⮜", command=prev_song)
play_btn = Button(controls_frame, text="▶️ / ⏸", command=play_pause_toggle)
next_btn = Button(controls_frame, text="⮞", command=next_song)
stop_btn = Button(controls_frame, text="⏹", command=stop_song)

Button(root, text="💾 Save Playlist", command=save_current_as_playlist).pack(pady=2)
Button(root, text="📂 Load Playlist", command=load_playlist_from_file).pack(pady=2)

prev_btn.grid(row=0, column=0, padx=5)
play_btn.grid(row=0, column=1, padx=5)
next_btn.grid(row=0, column=2, padx=5)
stop_btn.grid(row=0, column=3, padx=5)

bottom_frame = Frame(root)
bottom_frame.pack(pady=10)
loop_btn = Button(bottom_frame, text="Loop: OFF", command=toggle_loop)
shuffle_btn = Button(bottom_frame, text="Shuffle", command=shuffle_playlist)
loop_btn.grid(row=0, column=0, padx=10)
shuffle_btn.grid(row=0, column=1, padx=10)

network_frame = LabelFrame(root, text="Network Sync")
network_frame.pack(pady=10)
host_btn = Button(network_frame, text="Host Session", command=host_session)
join_label = Label(network_frame, text="Join Code:")
room_entry = Entry(network_frame, width=15)
join_btn = Button(network_frame, text="Join", command=join_session)
host_btn.grid(row=0, column=0, padx=5, pady=5)
join_label.grid(row=1, column=0)
room_entry.grid(row=1, column=1, padx=5)
join_btn.grid(row=1, column=2, padx=5)

status_label = Label(root, text="Status: Idle", anchor="w")
status_label.pack(fill="x", padx=10, pady=10)

# Initialize the app with saved data
refresh_library_view()

# Load the last playlist state
saved_playlist, saved_index = load_saved_playlist()
if saved_playlist:
    playlist = saved_playlist
    current_index = saved_index if 0 <= saved_index < len(playlist) else 0
    refresh_queue_view()
    update_status("Loaded previous session")

check_song_end()
root.mainloop()
