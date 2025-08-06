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
            'net_energy': []
        }
        self.focused_plant_id = None
        log.log("GraphingManager initialized.")

    def set_focused_plant(self, plant_id):
        """
        Sets a new plant to focus on, clearing old data.
        """
        if self.focused_plant_id != plant_id:
            self.focused_plant_id = plant_id
            self.data['time_days'].clear()
            self.data['net_energy'].clear()
            log.log(f"[GraphingManager] Now tracking Plant ID: {plant_id}. Data cleared.")

    def clear_focus(self):
        """
        Stops tracking a plant. The data is kept for plotting.
        """
        log.log(f"[GraphingManager] Stopped tracking Plant ID: {self.focused_plant_id}. Data will be plotted on exit.")
        self.focused_plant_id = None

    def add_data_point(self, time_seconds, net_energy):
        """
        Adds a single time-stamped data point to the dataset.
        """
        time_days = time_seconds / 86400.0 # Convert seconds to days for the plot
        self.data['time_days'].append(time_days)
        self.data['net_energy'].append(net_energy)

    def has_data(self):
        """
        Checks if any data has been collected.
        """
        return len(self.data['time_days']) > 0

    def generate_and_save_graph(self):
        """
        Uses matplotlib to generate, display, and save a line graph of the collected data.
        """
        if not self.has_data():
            log.log("[GraphingManager] No data collected, skipping plot generation.")
            return

        log.log(f"[GraphingManager] Generating plot with {len(self.data['time_days'])} data points...")
        
        fig, ax = plt.subplots(figsize=(12, 7))
        
        ax.plot(self.data['time_days'], self.data['net_energy'], label='Net Energy')
        
        # Add a horizontal line at y=0 to clearly show profit/loss
        ax.axhline(0, color='r', linestyle='--', linewidth=0.8, label='Break-even Point')

        # --- Formatting ---
        ax.set_title('Focused Plant: Net Energy Production Over Time')
        ax.set_xlabel('Time (Simulation Days)')
        ax.set_ylabel('Net Energy Gained per Hour (Joules)')
        ax.grid(True, which='both', linestyle='--', linewidth=0.5)
        ax.legend()
        
        # Improve layout
        fig.tight_layout()

        # Save the figure to a file
        try:
            file_path = 'focused_plant_energy_graph.png'
            fig.savefig(file_path)
            log.log(f"[GraphingManager] Graph saved to {file_path}")
        except Exception as e:
            log.log(f"[GraphingManager] ERROR: Could not save graph. Reason: {e}")

        # Display the plot in a new window
        plt.show()