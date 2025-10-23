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
    shuffle_btn.config(text=f"Shuffle: {'ON' if shuffle_mode else 'OFF'}")
    update_status(f"Shuffle {'enabled' if shuffle_mode else 'disabled'}")

# ---------------------------------------
# SONG END DETECTION
# ---------------------------------------
def check_song_end():
    """Check if current song finished, then go to next or loop."""
    for event in pygame.event.get():
        if event.type == SONG_END:
            next_song(auto=True)
    root.after(1000, check_song_end)

# Register a pygame event for when song ends
SONG_END = pygame.USEREVENT + 1
pygame.mixer.music.set_endevent(SONG_END)
shuffled_order = []
