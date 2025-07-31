#time_manager.py

import constants as C

class TimeManager:
    def __init__(self):
        self.total_sim_seconds = 0.0
        self.is_paused = False
        self.time_multiplier_level = 0
        self.current_multiplier = C.TIME_MULTIPLIERS[self.time_multiplier_level]

    def get_scaled_delta_time(self, real_delta_seconds):
        """Returns how much simulation time should pass based on real time and speed."""
        if self.is_paused:
            return 0.0
        return real_delta_seconds * self.current_multiplier

    def update_total_time(self, scaled_delta_time):
        """Updates the total simulation time counter for UI display."""
        self.total_sim_seconds += scaled_delta_time

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        print(f"Event: Simulation {'paused' if self.is_paused else 'resumed'}.")

    def set_speed(self, level):
        if level in C.TIME_MULTIPLIERS:
            self.time_multiplier_level = level
            self.current_multiplier = C.TIME_MULTIPLIERS[level]
            print(f"Event: Simulation speed set to level {level} (x{self.current_multiplier}).")

    def get_display_string(self):
        days = int(self.total_sim_seconds // 86400)
        hours = int((self.total_sim_seconds % 86400) // 3600)
        minutes = int((self.total_sim_seconds % 3600) // 60)
        seconds = int(self.total_sim_seconds % 60)
        
        time_str = f"Day: {days}, {hours:02d}:{minutes:02d}:{seconds:02d}"
        speed_str = f"Speed: x{self.current_multiplier}"
        if self.is_paused:
            speed_str = "Speed: PAUSED"
            
        return f"{time_str} | {speed_str}"