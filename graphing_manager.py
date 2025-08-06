# graphing_manager.py

import matplotlib.pyplot as plt
import logger as log

class GraphingManager:
    """
    Handles the collection of time-series data for a focused creature
    and generates a plot after the simulation ends.
    """
    def __init__(self):
        self.data = {
            'time_days': [],
            'net_energy': [],
            'height': [],
            'radius': []
        }
        self.focused_plant_id = None
        log.log("GraphingManager initialized.")

    def set_focused_plant(self, plant_id):
        """
        Sets a new plant to focus on, clearing old data.
        """
        if self.focused_plant_id != plant_id:
            self.focused_plant_id = plant_id
            for key in self.data:
                self.data[key].clear()
            log.log(f"[GraphingManager] Now tracking Plant ID: {plant_id}. All data series cleared.")

    def clear_focus(self):
        """
        Stops tracking a plant. The data is kept for plotting.
        """
        log.log(f"[GraphingManager] Stopped tracking Plant ID: {self.focused_plant_id}. Data will be plotted on exit.")
        self.focused_plant_id = None

    def add_data_point(self, time_seconds, net_energy, height, radius):
        """
        Adds a single time-stamped data point to all data series.
        """
        time_days = time_seconds / 86400.0 # Convert seconds to days for the plot
        self.data['time_days'].append(time_days)
        self.data['net_energy'].append(net_energy)
        self.data['height'].append(height)
        self.data['radius'].append(radius)

    def has_data(self):
        """
        Checks if any data has been collected.
        """
        return len(self.data['time_days']) > 0

    def generate_and_save_energy_graph(self):
        """
        Uses matplotlib to generate a line graph of the plant's net energy.
        """
        log.log(f"[GraphingManager] Generating energy plot with {len(self.data['time_days'])} data points...")
        
        fig, ax = plt.subplots(figsize=(12, 7))
        
        ax.plot(self.data['time_days'], self.data['net_energy'], label='Net Energy')
        
        ax.axhline(0, color='r', linestyle='--', linewidth=0.8, label='Break-even Point')

        ax.set_title('Focused Plant: Net Energy Production Over Time')
        ax.set_xlabel('Time (Simulation Days)')
        ax.set_ylabel('Net Energy Gained per Hour (Joules)')
        ax.grid(True, which='both', linestyle='--', linewidth=0.5)
        ax.legend()
        
        fig.tight_layout()

        try:
            file_path = 'focused_plant_energy_graph.png'
            fig.savefig(file_path)
            log.log(f"[GraphingManager] Energy graph saved to {file_path}")
        except Exception as e:
            log.log(f"[GraphingManager] ERROR: Could not save energy graph. Reason: {e}")

    def generate_and_save_growth_graph(self):
        """
        Uses matplotlib to generate and save a line graph of the plant's growth (height and radius).
        """
        log.log("[GraphingManager] Generating growth plot...")
        
        fig, ax1 = plt.subplots(figsize=(12, 7))
        ax1.set_title('Focused Plant: Growth Over Time')
        ax1.set_xlabel('Time (Simulation Days)')
        ax1.grid(True, which='both', linestyle='--', linewidth=0.5)

        # --- Plot 1: Height on the left axis (ax1) ---
        ax1.set_ylabel('Height (cm)', color='tab:blue')
        # The plot command returns a list of Line2D objects; we capture the first one.
        line1, = ax1.plot(self.data['time_days'], self.data['height'], color='tab:blue', label='Height (cm)')
        ax1.tick_params(axis='y', labelcolor='tab:blue')

        # --- Plot 2: Radius on the right axis (ax2) ---
        ax2 = ax1.twinx()  
        ax2.set_ylabel('Canopy Radius (cm)', color='tab:green')
        # Capture the second line object
        line2, = ax2.plot(self.data['time_days'], self.data['radius'], color='tab:green', label='Radius (cm)')
        ax2.tick_params(axis='y', labelcolor='tab:green')

        # --- Unified Legend ---
        # Use the captured line objects (handles) to create a single, correct legend.
        ax1.legend(handles=[line1, line2], loc='upper left')

        fig.tight_layout()

        try:
            file_path = 'focused_plant_growth_graph.png'
            fig.savefig(file_path)
            log.log(f"[GraphingManager] Growth graph saved to {file_path}")
        except Exception as e:
            log.log(f"[GraphingManager] ERROR: Could not save growth graph. Reason: {e}")

    def generate_and_save_graphs(self):
        """
        Generates, saves, and displays all configured graphs if data exists.
        """
        if not self.has_data():
            log.log("[GraphingManager] No data collected, skipping plot generation.")
            return

        self.generate_and_save_energy_graph()
        self.generate_and_save_growth_graph()

        plt.show()