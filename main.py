#main.py

import pygame
import cProfile 
import pstats
import constants as C
from world import World
from ui import draw_loading_screen

def initialize_simulation():
    print("Attempting to initialize Pygame...")
    pygame.init()
    print("Pygame initialized successfully.")
    print(f"Creating display surface with width: {C.SCREEN_WIDTH} and height: {C.SCREEN_HEIGHT}")
    screen = pygame.display.set_mode((C.SCREEN_WIDTH, C.SCREEN_HEIGHT))
    pygame.display.set_caption("Eco-System Evolution")
    font = pygame.font.Font(None, 36)
    print("Display surface and font created.")
    return screen, font

def run_simulation():
    screen, font = initialize_simulation()
    clock = pygame.time.Clock()
    world = World()
    world.populate_world()
    world.pre_generate_all_chunks(screen, font)

    print("Starting main simulation loop...")
    print("CONTROLS: [SPACE] to Pause, [0-4] to set Speed, [V] to cycle Views.")
    
    time_accumulator = 0.0
    
    running = True
    while running:
        # --- Get Real Time ---
        # This is how much real-world time has passed.
        # We cap it to prevent a "spiral of death" if a frame takes too long.
        real_delta_seconds = min(clock.tick(C.CLOCK_TICK_RATE) / 1000.0, 0.25)

        # --- Event Handling (No Change) ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: world.handle_click(event.pos)
                elif event.button == 3 or event.button == 4: world.camera.zoom_in()
                elif event.button == 5: world.camera.zoom_out()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_v: world.toggle_environment_view()
                if event.key == pygame.K_SPACE: world.time_manager.toggle_pause()
                if event.key == pygame.K_0: world.time_manager.set_speed(0)
                if event.key == pygame.K_1: world.time_manager.set_speed(1)
                if event.key == pygame.K_2: world.time_manager.set_speed(2)
                if event.key == pygame.K_3: world.time_manager.set_speed(3)
                if event.key == pygame.K_4: world.time_manager.set_speed(4)

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]: world.camera.pan(-C.CAMERA_PANSPEED_PIXELS, 0)
        if keys[pygame.K_RIGHT]: world.camera.pan(C.CAMERA_PANSPEED_PIXELS, 0)
        if keys[pygame.K_UP]: world.camera.pan(0, -C.CAMERA_PANSPEED_PIXELS)
        if keys[pygame.K_DOWN]: world.camera.pan(0, C.CAMERA_PANSPEED_PIXELS)

        # --- Simulation Logic (The "Update" part) ---
        scaled_delta_time = world.time_manager.get_scaled_delta_time(real_delta_seconds)
        time_accumulator += scaled_delta_time
        
        while time_accumulator >= C.SIMULATION_TICK_INTERVAL_SECONDS:
            world.update(C.SIMULATION_TICK_INTERVAL_SECONDS)
            world.time_manager.update_total_time(C.SIMULATION_TICK_INTERVAL_SECONDS)
            time_accumulator -= C.SIMULATION_TICK_INTERVAL_SECONDS
        
        # --- Drawing (The "Render" part) ---
        # This part now runs completely independently of the simulation logic loop.
        screen.fill(C.COLOR_VOID)
        world.draw(screen)
        
        time_ui_surface = font.render(world.time_manager.get_display_string(), True, C.COLOR_WHITE)
        screen.blit(time_ui_surface, (10, 10))

        pygame.display.flip()

    print("Main simulation loop ended.")

def shutdown_simulation():
    print("Quitting Pygame...")
    pygame.quit()
    print("Simulation ended cleanly.")

# --- NEW: Create a main function to be profiled ---
def main():
    print("--- Simulation Start ---")
    run_simulation()
    shutdown_simulation()
    print("--- Simulation Exit ---")

if __name__ == '__main__':
    # --- NEW: Profiler execution block ---
    profiler = cProfile.Profile()
    try:
        profiler.run('main()')
    except SystemExit:
        # This allows the simulation to exit cleanly without a profiler error
        pass
    finally:
        print("\n\n--- PROFILER REPORT ---")
        stats = pstats.Stats(profiler)
        # Sort the stats by the cumulative time spent in each function
        stats.sort_stats(pstats.SortKey.CUMULATIVE)
        # Print the top 15 results
        stats.print_stats(15)