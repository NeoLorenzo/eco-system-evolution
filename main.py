#main.py

import pygame
import cProfile 
import pstats
import constants as C
from world import World
from ui import draw_loading_screen
import logger

def initialize_simulation():
    logger.log("Attempting to initialize Pygame...")
    pygame.init()
    logger.log("Pygame initialized successfully.")
    logger.log(f"Creating display surface with width: {C.SCREEN_WIDTH} and height: {C.SCREEN_HEIGHT}")
    screen = pygame.display.set_mode((C.SCREEN_WIDTH, C.SCREEN_HEIGHT))
    pygame.display.set_caption("Eco-System Evolution")
    font = pygame.font.Font(None, C.UI_FONT_SIZE)
    logger.log("Display surface and font created.")
    return screen, font

def run_simulation():
    screen, font = initialize_simulation()
    clock = pygame.time.Clock()
    world = World()
    logger.set_time_manager(world.time_manager)
    world.populate_world()
    world.pre_generate_all_chunks(screen, font)

    logger.log("Starting main simulation loop...")
    logger.log("CONTROLS: [SPACE] to Pause, [0-5] to set Speed, [V] to cycle Views.")
    
    running = True
    while running:
        # --- Get Real Time ---
        # This is how much real-world time has passed.
        # We cap it to prevent a "spiral of death" if a frame takes too long.
        real_delta_seconds = min(clock.tick(C.CLOCK_TICK_RATE) / C.MILLISECONDS_PER_SECOND, 0.25)

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
                if event.key == pygame.K_5: world.time_manager.set_speed(5)

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]: world.camera.pan(-C.CAMERA_PANSPEED_PIXELS, 0)
        if keys[pygame.K_RIGHT]: world.camera.pan(C.CAMERA_PANSPEED_PIXELS, 0)
        if keys[pygame.K_UP]: world.camera.pan(0, -C.CAMERA_PANSPEED_PIXELS)
        if keys[pygame.K_DOWN]: world.camera.pan(0, C.CAMERA_PANSPEED_PIXELS)

        # --- Simulation Logic (The "Update" part) ---
        scaled_delta_time = world.time_manager.get_scaled_delta_time(real_delta_seconds)
        if scaled_delta_time > 0:
            world.update_in_bulk(scaled_delta_time)
        
        # --- Drawing (The "Render" part) ---
        # This part now runs completely independently of the simulation logic loop.
        screen.fill(C.COLOR_VOID)
        world.draw(screen)
        
        time_ui_surface = font.render(world.time_manager.get_display_string(), True, C.COLOR_WHITE)
        screen.blit(time_ui_surface, (C.UI_TIME_DISPLAY_POS_X, C.UI_TIME_DISPLAY_POS_Y))

        pygame.display.flip()

    logger.log("Main simulation loop ended.")

def shutdown_simulation():
    logger.log("Quitting Pygame...")
    pygame.quit()
    logger.log("Simulation ended cleanly.")

def main():
    logger.log("--- Simulation Start ---")
    run_simulation()
    shutdown_simulation()
    logger.log("--- Simulation Exit ---")

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
        stats.print_stats(C.PROFILER_PRINT_LINE_COUNT)