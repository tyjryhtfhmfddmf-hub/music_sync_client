import tkinter as tk
import threading
import time
import requests
import pygame

# ---------- SETTINGS ----------
RELAY_URL = "https://music-sync-relay.onrender.com/"  # 🔁 Replace with your Render URL
POLL_INTERVAL = 2        # seconds between receiving checks
KEEP_ALIVE_INTERVAL = 300  # 5 minutes

pygame.mixer.init()

# ---------- AUDIO ----------
def play_song():
    pygame.mixer.music.load("your_song.mp3")
    pygame.mixer.music.play()

def pause_song():
    pygame.mixer.music.pause()

def unpause_song():
    pygame.mixer.music.unpause()

def stop_song():
    pygame.mixer.music.stop()

# ---------- NETWORK ----------
room_code = None
session_active = False

def host_session():
    global room_code, session_active
    try:
        res = requests.post(f"{RELAY_URL}/host", timeout=5)
        room_code = res.json()["room_code"]
        status_label.config(text=f"Hosting session • Room code: {room_code}")
        session_active = True
        start_keep_alive()
        threading.Thread(target=poll_commands, daemon=True).start()
    except Exception as e:
        status_label.config(text=f"Failed to host: {e}")

def join_session():
    global room_code, session_active
    code = room_entry.get().strip()
    if not code:
        status_label.config(text="Please enter a room code.")
        return
    room_code = code
    status_label.config(text=f"Joined room: {room_code}")
    session_active = True
    start_keep_alive()
    threading.Thread(target=poll_commands, daemon=True).start()

def send_command(command):
    if not room_code:
        status_label.config(text="No room active.")
        return
    try:
        requests.post(f"{RELAY_URL}/send/{room_code}", json={"command": command}, timeout=5)
        status_label.config(text=f"Sent: {command}")
    except Exception as e:
        status_label.config(text=f"Send failed: {e}")

def poll_commands():
    global session_active
    while session_active:
        try:
            res = requests.get(f"{RELAY_URL}/receive/{room_code}", timeout=5)
            commands = res.json().get("commands", [])
            for cmd in commands:
                process_command(cmd)
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)

def process_command(cmd):
    cmd = cmd.strip().lower()
    if cmd == "play":
        play_song()
    elif cmd == "pause":
        pause_song()
    elif cmd == "unpause":
        unpause_song()
    elif cmd == "stop":
        stop_song()

# ---------- KEEP ALIVE ----------
def keep_alive():
    while session_active:
        try:
            requests.get(f"{RELAY_URL}/ping", timeout=5)
            print("🟢 Relay pinged (alive)")
        except Exception as e:
            print("🔴 Ping failed:", e)
        time.sleep(KEEP_ALIVE_INTERVAL)

def start_keep_alive():
    threading.Thread(target=keep_alive, daemon=True).start()

# ---------- UI ----------
window = tk.Tk()
window.title("Music Sync (Relay Client)")

frame = tk.Frame(window)
frame.pack(pady=15)

tk.Label(frame, text="Enter Room Code:").pack()
room_entry = tk.Entry(frame)
room_entry.pack(pady=5)

tk.Button(frame, text="Host Session", command=host_session).pack(pady=3)
tk.Button(frame, text="Join Session", command=join_session).pack(pady=3)

control_frame = tk.Frame(window)
control_frame.pack(pady=10)

tk.Button(control_frame, text="Play", command=lambda: send_command("play")).pack(side="left", padx=5)
tk.Button(control_frame, text="Pause", command=lambda: send_command("pause")).pack(side="left", padx=5)
tk.Button(control_frame, text="Unpause", command=lambda: send_command("unpause")).pack(side="left", padx=5)
tk.Button(control_frame, text="Stop", command=lambda: send_command("stop")).pack(side="left", padx=5)

status_label = tk.Label(window, text="Not connected")
status_label.pack(pady=10)

window.mainloop()
