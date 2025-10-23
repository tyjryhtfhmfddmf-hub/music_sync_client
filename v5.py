# -----------------------------
# IMPORTS
# -----------------------------

import os
import random
import pygame
import json
from tkinter import *
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD
from tkinter import simpledialog, messagebox


# -----------------------------
# ROOT WINDOW
# -----------------------------
root = TkinterDnD.Tk()
root.title("Music Sync App")
root.geometry("500x600")  # Optional: Set window size
root.resizable(False, False)

# ---------------------------------------
# CONFIGURATION
# ---------------------------------------



RELAY_URL = "https://music-sync-relay.onrender.com/"   # change this to your deployed relay
pygame.mixer.init()

LIBRARY_FILE = "library.json"
PLAYLISTS_DIR = "playlists"
os.makedirs(PLAYLISTS_DIR, exist_ok=True)


playlist = []

current_index = 0
paused = False
shuffle_mode = False
loop_mode = False
session_code = None
is_host = False
stop_polling = False



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



library = load_library()


def update_status(text):
    status_label.config(text=f"Status: {text}")



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
            playlist_box.insert(END, os.path.basename(f))

    save_library()
    save_playlist()
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
            playlist_box.insert(END, os.path.basename(path))

    save_library()
    save_playlist()
    update_status(f"Added {added} new songs from folder.")




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
    save_playlist()  # update persistent order
    messagebox.showinfo("Playlist Loaded", f"Loaded '{name}' successfully.")






# ---------------------------------------
# MUSIC CONTROL
# ---------------------------------------
def load_song(file_path):
    global current_index, playlist
    if file_path not in playlist:
        playlist.append(file_path)
    current_index = playlist.index(file_path)
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play()
    refresh_queue_view()
    update_status(f"Playing: {os.path.basename(file_path)}")
    if is_host:
        send_command("play", current_index)

def play_pause_toggle():
    global paused
    if not pygame.mixer.music.get_busy() and not paused and playlist:
        pygame.mixer.music.play()
        update_status(f"Playing: {os.path.basename(playlist[current_index])}")
        if is_host:
            send_command("play", current_index)
    elif not paused:
        pygame.mixer.music.pause()
        paused = True
        update_status("Paused")
        if is_host:
            send_command("pause")
    else:
        pygame.mixer.music.unpause()
        paused = False
        update_status(f"Playing: {os.path.basename(playlist[current_index])}")
        if is_host:
            send_command("unpause")

def next_song(auto=False):
    global current_index, shuffled_order
    if not playlist:
        return
    if loop_mode and auto:
        # Replay the same song
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
        send_command("stop")

def toggle_loop():
    global loop_mode
    loop_mode = not loop_mode
    loop_btn.config(text=f"Loop: {'ON' if loop_mode else 'OFF'}")
    update_status(f"Loop {'enabled' if loop_mode else 'disabled'}")

def toggle_shuffle():
    global shuffle_mode, shuffled_order
    shuffle_mode = not shuffle_mode
    shuffled_order = []
    refresh_queue_view()
    shuffle_btn.config(text=f"Shuffle: {'ON' if shuffle_mode else 'OFF'}")
    update_status(f"Shuffle {'enabled' if shuffle_mode else 'disabled'}")

# ---------------------------------------
# SONG END DETECTION (Tkinter-friendly)
# ---------------------------------------
last_playing_state = False

def check_song_end():
    global last_playing_state
    is_playing = pygame.mixer.music.get_busy()
    queue_list.select_clear(0, END)
    queue_list.select_set(current_index)
    queue_list.see(current_index)


    # Detect the transition from playing → not playing
    if last_playing_state and not is_playing and not paused:
        # Song finished naturally
        handle_song_finished()

    last_playing_state = is_playing
    root.after(1000, check_song_end)  # check every second

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
from tkinterdnd2 import DND_FILES, TkinterDnD


queue_frame = Frame(root)
queue_frame.pack(pady=10)

Label(queue_frame, text="🎵 Up Next (Drag to Reorder)").pack()

queue_list = Listbox(queue_frame, width=50, selectmode=SINGLE)
queue_list.pack()

# Internal drag tracking variables
drag_start_index = None

def on_drag_start(event):
    global drag_start_index
    widget = event.widget
    drag_start_index = widget.nearest(event.y)

def on_drag_motion(event):
    pass  # optional highlight effect later

def on_drag_drop(event):
    global drag_start_index, current_index
    widget = event.widget
    drop_index = widget.nearest(event.y)
    if drop_index == drag_start_index or drag_start_index is None:
        return

    # Track the currently playing song *before* reorder
    current_song = playlist[current_index] if 0 <= current_index < len(playlist) else None

    # Move the dragged song
    song = playlist.pop(drag_start_index)
    playlist.insert(drop_index, song)

    # Update current_index based on where the current song moved to
    if current_song in playlist:
        current_index = playlist.index(current_song)

    refresh_queue_view()
    queue_list.select_clear(0, END)
    queue_list.select_set(drop_index)
    queue_list.see(current_index)
    drag_start_index = None

# Bind events
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
    global session_code, is_host, stop_polling
    try:
        res = requests.post(f"{RELAY_URL}/create_session")
        data = res.json()
        session_code = data.get("session_code")
        is_host = True
        stop_polling = False
        update_status(f"Hosting Session: {session_code}")
    except Exception as e:
        update_status(f"Error hosting: {e}")

def join_session():
    global session_code, is_host, stop_polling
    code = join_entry.get().strip()
    if not code:
        messagebox.showinfo("Join Session", "Enter a valid session code.")
        return
    session_code = code
    is_host = False
    stop_polling = False
    update_status(f"Joined Session: {session_code}")
    threading.Thread(target=poll_commands, daemon=True).start()

def send_command(cmd, index=None):
    if not session_code:
        return
    payload = {"session_code": session_code, "command": cmd}
    if index is not None:
        payload["index"] = index
    try:
        requests.post(f"{RELAY_URL}/send_command", json=payload, timeout=3)
    except:
        pass

def poll_commands():
    global stop_polling
    while not stop_polling and session_code and not is_host:
        try:
            res = requests.get(f"{RELAY_URL}/get_command/{session_code}", timeout=5)
            if res.status_code == 200:
                data = res.json()
                cmd = data.get("command")
                index = data.get("index")
                if cmd == "play" and index is not None:
                    file = playlist[index]
                    pygame.mixer.music.load(file)
                    pygame.mixer.music.play()
                    update_status(f"Playing (remote): {os.path.basename(file)}")
                elif cmd == "pause":
                    pygame.mixer.music.pause()
                    update_status("Paused (remote)")
                elif cmd == "unpause":
                    pygame.mixer.music.unpause()
                    update_status("Resumed (remote)")
                elif cmd == "stop":
                    pygame.mixer.music.stop()
                    update_status("Stopped (remote)")
        except:
            pass
        time.sleep(1)

# ---------------------------------------
# TKINTER UI
# ---------------------------------------


playlist_box = Listbox(root, width=55, height=10)
playlist_box.pack(pady=10)

top_frame = Frame(root)
top_frame.pack()

add_btn = Button(top_frame, text="Add Files", command=add_songs)
add_folder_btn = Button(top_frame, text="Add Folder", command=add_folder)
add_btn.grid(row=0, column=0, padx=5)
add_folder_btn.grid(row=0, column=1, padx=5)

controls_frame = Frame(root)
controls_frame.pack(pady=10)
prev_btn = Button(controls_frame, text="⏮", command=prev_song)
play_btn = Button(controls_frame, text="▶️ / ⏸", command=play_pause_toggle)
next_btn = Button(controls_frame, text="⏭", command=next_song)
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
shuffle_btn = Button(bottom_frame, text="Shuffle: OFF", command=toggle_shuffle)
loop_btn.grid(row=0, column=0, padx=10)
shuffle_btn.grid(row=0, column=1, padx=10)

network_frame = LabelFrame(root, text="Network Sync")
network_frame.pack(pady=10)
host_btn = Button(network_frame, text="Host Session", command=host_session)
join_label = Label(network_frame, text="Join Code:")
join_entry = Entry(network_frame, width=15)
join_btn = Button(network_frame, text="Join", command=join_session)
host_btn.grid(row=0, column=0, padx=5, pady=5)
join_label.grid(row=1, column=0)
join_entry.grid(row=1, column=1, padx=5)
join_btn.grid(row=1, column=2, padx=5)

status_label = Label(root, text="Status: Idle", anchor="w")
status_label.pack(fill="x", padx=10, pady=10)

check_song_end()
load_playlist()
root.mainloop()
