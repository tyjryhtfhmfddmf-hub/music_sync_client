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
        # REMOVED the lines that added to the playlist

    save_library()
    # REMOVED save_playlist()
    refresh_library_view()
    # REMOVED refresh_queue_view()
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
        # REMOVED the lines that added to the playlist

    save_library()
    # REMOVED save_playlist()
    refresh_library_view()
    # REMOVED refresh_queue_view()
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



def add_selected_to_queue():
    """Add the selected song from the library to the 'Up Next' queue."""
    selection = playlist_box.curselection()
    if not selection:
        messagebox.showinfo("Add Song", "Please select a song from the library to add.")
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
    if room_code and session_active:
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
        if room_code and session_active:
            send_command("pause", current_index)
    else:
        pygame.mixer.music.unpause()
        paused = False
        update_status(f"Playing: {os.path.basename(playlist[current_index])}")
        if room_code and session_active:
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
    # Send command if in a network session
    if room_code and session_active:
        send_command("next", current_index)


def prev_song():
    global current_index
    if not playlist:
        return
    current_index = (current_index - 1) % len(playlist)
    refresh_queue_view()
    load_song(playlist[current_index])
    # Send command if in a network session
    if room_code and session_active:
        send_command("prev", current_index)


def stop_song():
    pygame.mixer.music.stop()
    update_status("Stopped")
    if room_code and session_active:
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





def remove_from_queue():
    """Remove the selected song from the 'Up Next' queue."""
    global current_index
    
    selection = queue_list.curselection()
    if not selection:
        messagebox.showinfo("Remove Song", "Please select a song from the 'Up Next' queue to remove.")
        return
    
    index_to_remove = selection[0]
    
    # Check if we are removing the currently playing song
    if index_to_remove == current_index:
        stop_song() # Stop playback
        current_index = -1 # Reset current_index
        
    # Pop the song from the playlist
    removed_song = playlist.pop(index_to_remove)
    
    # Adjust current_index if a song *before* the playing song was removed
    if current_index > index_to_remove:
        current_index -= 1
        
    refresh_queue_view()
    save_playlist()
    update_status(f"Removed from queue: {os.path.basename(removed_song)}")


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

# Custom Scale class to prevent clicking to jump but allow dragging
class SmoothScale(ttk.Scale):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Unbind the default click-to-jump behavior on the trough
        self.bind("<Button-1>", self._on_click)
    
    def _on_click(self, event):
        # Get the slider's position
        style = ttk.Style()
        slider_length = style.lookup('Horizontal.Scale.slider', 'sliderlength') or 30
        
        # Check if click is on the slider itself (allow it) or the trough (block it)
        slider_pos = self.winfo_width() * float(self.get())
        
        # If clicking near the slider thumb, allow normal behavior
        if abs(event.x - slider_pos) < slider_length / 2:
            return  # Allow the default behavior (dragging)
        
        # Otherwise, block click-to-jump on the trough
        return "break"

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

# --- NEW FRAME for listbox + button ---
queue_list_frame = Frame(queue_frame)
queue_list_frame.pack()

queue_list = Listbox(queue_list_frame, width=48, height=10, selectmode=SINGLE) # Adjusted width/height
queue_list.pack(side=LEFT, fill=Y)

# --- NEW BUTTON ---
remove_btn_frame = Frame(queue_list_frame)
remove_btn_frame.pack(side=LEFT, fill=Y, padx=(5,0))

remove_from_queue_btn = Button(remove_btn_frame, text="✖", command=remove_from_queue, font=("Arial", 14), width=2, fg="red")
remove_from_queue_btn.pack(anchor="center", expand=True)
# --- END NEW BUTTON ---

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
# LIBRARY & PLAYLIST SYNC FUNCTIONS
# ---------------------------------------

def sync_current_playlist():
    """Send current playlist to all connected clients."""
    if not room_code or not session_active:
        update_status("Not in a network session")
        return
    
    if not playlist:
        messagebox.showinfo("No Playlist", "No songs in queue to share.")
        return
    
    # Confirm before sending
    response = messagebox.askyesno(
        "Share Playlist",
        f"Share your current queue ({len(playlist)} songs) with all connected clients?"
    )
    
    if not response:
        return
    
    playlist_data = {
        "playlist": playlist,
        "current_index": current_index
    }
    
    send_command("sync_playlist", data=playlist_data)
    messagebox.showinfo("Playlist Shared", f"Your playlist ({len(playlist)} songs) has been shared!")
    update_status(f"Playlist synced ({len(playlist)} songs)")


def compare_libraries():
    """Request library comparison from all clients."""
    if not room_code or not session_active:
        messagebox.showinfo("Not Connected", "You must be in a network session to compare libraries.")
        return
    
    if not library:
        messagebox.showinfo("Empty Library", "Your library is empty. Add some songs first!")
        return
    
    # Request library from others
    send_command("request_library")
    
    update_status("Requesting library from other clients...")


def send_library_comparison(is_reply=False):
    """Send our library info for comparison."""
    if not room_code or not session_active:
        print("⚠️ Cannot send library: Not in active session")
        return
    
    if not library:
        print("⚠️ Cannot send library: Library is empty")
        return
    
    # Get just the filenames for comparison
    library_filenames = [os.path.basename(song) for song in library]
    
    comparison_data = {
        "library_count": len(library),
        "library_filenames": library_filenames,
        "is_reply": is_reply  # <-- Add the flag to the data payload
    }
    
    send_command("library_comparison", data=comparison_data)
    # Added is_reply to the print statement for better debugging
    print(f"✅ Sent library comparison: {len(library)} songs (is_reply: {is_reply})")


def compare_playlists(received_playlist):
    """Compare received playlist with local library."""
    missing_songs = []
    
    for song_path in received_playlist:
        song_name = os.path.basename(song_path)
        # Check if we have this song in our library
        local_match = any(os.path.basename(local_song) == song_name for local_song in library)
        
        if not local_match:
            missing_songs.append(song_name)
    
    if missing_songs:
        missing_text = "\n".join(missing_songs[:10])  # Show first 10
        if len(missing_songs) > 10:
            missing_text += f"\n... and {len(missing_songs) - 10} more"
        
        messagebox.showwarning(
            "Missing Songs",
            f"⚠️ You are missing {len(missing_songs)} songs from this playlist:\n\n{missing_text}\n\n"
            "You may experience playback issues."
        )


def show_library_comparison(data):
    """Show library comparison results in a dialog."""
    remote_count = data.get("library_count", 0)
    remote_filenames = set(data.get("library_filenames", []))
    local_filenames = set(os.path.basename(song) for song in library)
    
    # Find differences
    only_local = local_filenames - remote_filenames
    only_remote = remote_filenames - local_filenames
    common = local_filenames & remote_filenames
    
    # --- FIX 1: Ignore self-comparison ---
    # If there are no differences in either direction,
    # it means we are comparing our library to itself.
    if not only_local and not only_remote:
        print("✅ Ignoring self-comparison library report.")
        return  # Don't show a popup for our own library!
    # --- END FIX 1 ---

    # --- FIX 2: Improved percentage calculation ---
    # Calculate percentage relative to *our* library
    local_percent = int(len(common) / max(len(local_filenames), 1) * 100)
    # Calculate percentage relative to *their* library
    remote_percent = int(len(common) / max(remote_count, 1) * 100)

    # Create comparison message
    msg = f"📊 Library Comparison Results\n"
    msg += f"{'='*50}\n\n"
    msg += f"Your library: {len(library)} songs\n"
    msg += f"Their library: {remote_count} songs\n"
    msg += f"Songs in common: {len(common)}\n"
    msg += f"  • That's {local_percent}% of YOUR library\n"
    msg += f"  • That's {remote_percent}% of THEIR library\n\n"
    # --- END FIX 2 ---
    
    if only_local:
        msg += f"🎵 Songs only YOU have: {len(only_local)}\n"
        sample = list(only_local)[:8]
        msg += "  • " + "\n  • ".join(sample)
        if len(only_local) > 8:
            msg += f"\n  ... and {len(only_local) - 8} more\n"
        msg += "\n"
    else:
        msg += "✅ They have all your songs!\n\n"
    
    if only_remote:
        msg += f"🎵 Songs only THEY have: {len(only_remote)}\n"
        sample = list(only_remote)[:8]
        msg += "  • " + "\n  • ".join(sample)
        if len(only_remote) > 8:
            msg += f"\n  ... and {len(only_remote) - 8} more"
    else:
        msg += "✅ You have all their songs!"
    
    # Create a custom dialog window
    comparison_window = Toplevel(root)
    comparison_window.title("Library Comparison")
    comparison_window.geometry("550x450")
    comparison_window.resizable(True, True)
    
    # Add scrollbar
    text_frame = Frame(comparison_window)
    text_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
    
    scrollbar = Scrollbar(text_frame)
    scrollbar.pack(side=RIGHT, fill=Y)
    
    text_widget = Text(text_frame, wrap=WORD, yscrollcommand=scrollbar.set, font=("Courier", 10))
    text_widget.pack(side=LEFT, fill=BOTH, expand=True)
    scrollbar.config(command=text_widget.yview)
    
    text_widget.insert(1.0, msg)
    text_widget.config(state=DISABLED)
    
    Button(comparison_window, text="Close", command=comparison_window.destroy, width=15).pack(pady=10)
    
    update_status("Library comparison complete")
    

def wake_up_server():
    """Manually wake up the relay server."""
    update_status("Waking up relay server...")
    try:
        res = requests.get(f"{RELAY_URL}/ping", timeout=30)
        if res.status_code == 200:
            messagebox.showinfo("Server Awake", "Relay server is now awake and ready!")
            update_status("Relay server is awake")
        else:
            messagebox.showwarning("Server Issue", f"Server responded with status: {res.status_code}")
            update_status("Server may have issues")
    except requests.exceptions.Timeout:
        messagebox.showerror("Timeout", "Server is still sleeping or unreachable. Wait 30 seconds and try again.")
        update_status("Server wake-up timeout")
    except Exception as e:
        messagebox.showerror("Error", f"Could not reach server:\n\n{str(e)}")
        update_status(f"Server error: {e}")


# ---------------------------------------
# NETWORK RELAY FUNCTIONS
# ---------------------------------------

def host_session():
    global room_code, session_active, is_host
    try:
        update_status("Connecting to relay server...")
        res = requests.post(f"{RELAY_URL}/host", timeout=30)  # Increased timeout for cold start
        data = res.json()
        room_code = data["room_code"]
        is_host = True
        session_active = True
        update_status(f"Hosting session • Room code: {room_code}")
        start_keep_alive()
        threading.Thread(target=poll_commands, daemon=True).start()
    except requests.exceptions.Timeout:
        update_status("Connection timeout - relay server may be sleeping. Try again in 30 seconds.")
        messagebox.showerror("Connection Timeout", 
            "The relay server is not responding (it may be sleeping).\n\n"
            "Please wait 30 seconds and try again.\n\n"
            "Tip: Keep the server awake by pinging it regularly.")
    except Exception as e:
        update_status(f"Failed to host: {e}")
        messagebox.showerror("Connection Failed", f"Could not connect to relay server:\n\n{str(e)}")


def join_session():
    global room_code, session_active, is_host
    code = room_entry.get().strip()
    if not code:
        update_status("Please enter a room code.")
        return
    try:
        update_status("Connecting to relay server...")
        res = requests.post(f"{RELAY_URL}/join/{code}", timeout=30)  # Increased timeout
        if res.status_code == 200:
            room_code = code
            is_host = False
            session_active = True
            update_status(f"Joined room: {room_code}")
            start_keep_alive()
            threading.Thread(target=poll_commands, daemon=True).start()
        else:
            update_status("Room not found.")
            messagebox.showerror("Room Not Found", f"Room code '{code}' does not exist.")
    except requests.exceptions.Timeout:
        update_status("Connection timeout - relay server may be sleeping. Try again in 30 seconds.")
        messagebox.showerror("Connection Timeout", 
            "The relay server is not responding (it may be sleeping).\n\n"
            "Please wait 30 seconds and try again.")
    except Exception as e:
        update_status(f"Join failed: {e}")
        messagebox.showerror("Connection Failed", f"Could not connect to relay server:\n\n{str(e)}")


def send_command(command, index=None, data=None):
    """Send a command to the relay server."""
    if not room_code or not session_active:
        print("⚠️ Cannot send command: Not in active session")
        return
    try:
        payload = {"command": command}
        if index is not None:
            payload["index"] = index
        if data is not None:
            payload["data"] = data
        
        response = requests.post(f"{RELAY_URL}/send/{room_code}", json=payload, timeout=5)
        print(f"📤 Sent command: {command} (status: {response.status_code})")
        
        if response.status_code != 200:
            print(f"⚠️ Server response: {response.text}")
    except Exception as e:
        print(f"❌ Send failed: {e}")


def poll_commands():
    """Poll for commands from the relay server."""
    global session_active
    consecutive_errors = 0
    max_consecutive_errors = 3
    last_poll_timestamp = 0  # <-- NEW: Track last poll time
    
    while session_active:
        try:
            # <-- MODIFIED: Send 'since' timestamp
            res = requests.get(
                f"{RELAY_URL}/receive/{room_code}?since={last_poll_timestamp}", 
                timeout=10
            )
            
            data = res.json()
            commands = data.get("commands", [])
            
            # <-- NEW: Update timestamp to server's time
            # We use the server's returned time to avoid clock-skew issues
            new_timestamp = data.get("timestamp")
            if new_timestamp:
                last_poll_timestamp = new_timestamp
            else:
                # Fallback in case 'timestamp' is missing
                print("⚠️ Server did not return a timestamp, using local time.")
                last_poll_timestamp = time.time()

            
            if commands:
                print(f"📥 Received {len(commands)} command(s)")
            for cmd_data in commands:
                print(f"📥 Processing: {cmd_data}")
                process_command(cmd_data)
            
            # Reset error counter on success
            consecutive_errors = 0
            
        except requests.exceptions.Timeout:
            consecutive_errors += 1
            print(f"⚠️ Poll timeout ({consecutive_errors}/{max_consecutive_errors})")
            if consecutive_errors >= max_consecutive_errors:
                root.after(0, lambda: update_status("⚠️ Connection unstable - relay may be sleeping"))
        except Exception as e:
            consecutive_errors += 1
            print(f"❌ Poll error ({consecutive_errors}/{max_consecutive_errors}): {e}")
            if consecutive_errors >= max_consecutive_errors:
                root.after(0, lambda: update_status("⚠️ Connection lost to relay server"))
        
        time.sleep(POLL_INTERVAL)


def process_command(cmd_data):
    """Process a received command."""
    global current_index, paused, playlist
    
    if isinstance(cmd_data, str):
        command = cmd_data
        index = None
        data = None
    else:
        command = cmd_data.get("command", "")
        index = cmd_data.get("index")
        data = cmd_data.get("data")
    
    print(f"Processing command: {command}, index: {index}, data: {data is not None}")
    
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
    elif command == "next" and index is not None:
        if 0 <= index < len(playlist):
            current_index = index
            pygame.mixer.music.load(playlist[current_index])
            pygame.mixer.music.play()
            paused = False
            refresh_queue_view()
            update_status(f"Skipped to: {os.path.basename(playlist[current_index])}")
    elif command == "prev" and index is not None:
        if 0 <= index < len(playlist):
            current_index = index
            pygame.mixer.music.load(playlist[current_index])
            pygame.mixer.music.play()
            paused = False
            refresh_queue_view()
            update_status(f"Previous: {os.path.basename(playlist[current_index])}")
    elif command == "sync_playlist":
        if data is not None:
            # Receive synced playlist
            received_playlist = data.get("playlist", [])
            received_index = data.get("current_index", 0)
            
            # --- THIS IS THE FIX ---
            # If the received playlist is identical to our current one,
            # we are the sender (or already in sync). Ignore it.
            if received_playlist == playlist:
                print("✅ Ignoring self-sent or identical playlist sync.")
                return
            # --- END FIX ---

            # Compare and show what's missing
            compare_playlists(received_playlist)
            
            # Ask user if they want to adopt the synced playlist
            response = messagebox.askyesno(
                "Sync Playlist",
                # Updated text to be more generic
                f"A new playlist is being shared ({len(received_playlist)} songs).\n\n"
                "Do you want to sync your queue to match?"
            )
            
            if response:
                playlist = received_playlist.copy()
                current_index = received_index if 0 <= received_index < len(playlist) else 0
                refresh_queue_view()
                save_playlist()
                update_status("Playlist synced successfully!")
        else:
            print("⚠️ sync_playlist received but data is None")
    elif command == "request_library":
        # Someone requested our library, send it back
        print("📨 Received library request, sending our library...")
        send_library_comparison(is_reply=True)
    elif command == "library_comparison":
        if data is not None:
            is_reply = data.get("is_reply", False)
            # Received someone's library, show comparison
            print(f"📨 Received library data: {data.get('library_count', 0)} songs (is_reply: {is_reply})")
            show_library_comparison(data)
            
            # Only auto-reply if this wasn't already a reply (prevent loop)
            if not is_reply:
                print("📤 Auto-replying with our library...")
                send_library_comparison(is_reply=True)
            else:
                print("✅ This was a reply, not sending another response (loop prevention)")
        else:
            print("⚠️ library_comparison received but data is None")
            print(f"Full command data: {cmd_data}")


def keep_alive():
    """Keep the relay server connection alive."""
    while session_active:
        try:
            requests.get(f"{RELAY_URL}/ping", timeout=10)
            print("🟢 Relay pinged (alive)")
        except requests.exceptions.Timeout:
            print("🟡 Ping timeout - server may be slow")
        except Exception as e:
            print(f"🔴 Ping failed: {e}")
        time.sleep(KEEP_ALIVE_INTERVAL)


def start_keep_alive():
    threading.Thread(target=keep_alive, daemon=True).start()


# ---------------------------------------
# TKINTER UI
# ---------------------------------------

# ---------------------------------------
# TKINTER UI
# ---------------------------------------

# Library Section
library_frame = LabelFrame(root, text="📚 Library") # Updated text
library_frame.pack(pady=5, padx=10, fill=BOTH)

# Create a sub-frame to hold listbox and button
lib_list_frame = Frame(library_frame)
lib_list_frame.pack(pady=5, padx=5, fill=X)

playlist_box = Listbox(lib_list_frame, width=52, height=8) # Slightly reduced width
playlist_box.pack(side=LEFT, fill=BOTH, expand=True)
playlist_box.bind("<Double-Button-1>", on_library_double_click)

# Add a frame for the add button
lib_btn_frame = Frame(lib_list_frame)
lib_btn_frame.pack(side=LEFT, fill=Y, padx=(5,0))

add_to_queue_btn = Button(lib_btn_frame, text="✚", command=add_selected_to_queue, font=("Arial", 16), width=2)
add_to_queue_btn.pack(anchor="center", expand=True)

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

# Wake up server button
wake_frame = Frame(network_frame)
wake_frame.grid(row=0, column=0, columnspan=3, pady=5)

wake_btn = Button(wake_frame, text="⚡ Wake Up Server", command=wake_up_server, bg="#FFA500")
wake_btn.pack(side=LEFT, padx=5)

Label(wake_frame, text="(Click this first if server is sleeping)", font=("Arial", 8), fg="gray").pack(side=LEFT)

# Session controls
session_frame = Frame(network_frame)
session_frame.grid(row=1, column=0, columnspan=3, pady=5)

host_btn = Button(session_frame, text="Host Session", command=host_session)
host_btn.pack(side=LEFT, padx=5)

join_label = Label(session_frame, text="Join Code:")
join_label.pack(side=LEFT, padx=5)

room_entry = Entry(session_frame, width=15)
room_entry.pack(side=LEFT, padx=5)

join_btn = Button(session_frame, text="Join", command=join_session)
join_btn.pack(side=LEFT, padx=5)

# Sync controls
sync_frame = Frame(network_frame)
sync_frame.grid(row=2, column=0, columnspan=3, pady=5)

Label(sync_frame, text="Sync Options:").pack(side=LEFT, padx=5)

sync_playlist_btn = Button(sync_frame, text="📤 Share Playlist", command=sync_current_playlist)
sync_playlist_btn.pack(side=LEFT, padx=5)

compare_lib_btn = Button(sync_frame, text="📊 Compare Libraries", command=compare_libraries)
compare_lib_btn.pack(side=LEFT, padx=5)

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
