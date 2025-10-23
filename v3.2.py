# ---------------------------------------
# MUSIC CONTROL
# ---------------------------------------

shuffle_bag = []  # keeps track of shuffled order

def refill_shuffle_bag():
    global shuffle_bag
    shuffle_bag = list(range(len(playlist)))
    random.shuffle(shuffle_bag)

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
    monitor_playback()

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

def next_song():
    global current_index, shuffle_bag
    if not playlist:
        return
    if shuffle_mode:
        if not shuffle_bag:
            refill_shuffle_bag()
        current_index = shuffle_bag.pop()
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
    global shuffle_mode
    shuffle_mode = not shuffle_mode
    shuffle_btn.config(text=f"Shuffle: {'ON' if shuffle_mode else 'OFF'}")
    update_status(f"Shuffle {'enabled' if shuffle_mode else 'disabled'}")
    if shuffle_mode:
        refill_shuffle_bag()

def play_selected():
    selected = playlist_box.curselection()
    if not selected:
        messagebox.showinfo("No Selection", "Select a song to play.")
        return
    file = playlist[selected[0]]
    load_song(file)

def monitor_playback():
    """Check if the song ended; loop or go to next automatically."""
    def check():
        while pygame.mixer.music.get_busy():
            time.sleep(0.5)
        if loop_mode:
            pygame.mixer.music.play()
        else:
            next_song()
    threading.Thread(target=check, daemon=True).start()
