# logger.py

# This will hold a reference to the game's TimeManager instance.
_time_manager = None

def set_time_manager(tm):
    """Sets the global time manager for the logger to use."""
    global _time_manager
    _time_manager = tm

def log(message):
    """Prints a message with a simulation timestamp if available."""
    # Check if the time manager has been set and the simulation has started.
    if _time_manager and _time_manager.total_sim_seconds > 0:
        sim_seconds = _time_manager.total_sim_seconds
        days = int(sim_seconds // 86400)
        hours = int((sim_seconds % 86400) // 3600)
        minutes = int((sim_seconds % 3600) // 60)
        
        # Format the timestamp string.
        time_str = f"[Day {days:03d} {hours:02d}:{minutes:02d}]"
        print(f"{time_str} {message}")
    else:
        # For messages logged before the main loop starts.
        print(f"[Sim Start] {message}")