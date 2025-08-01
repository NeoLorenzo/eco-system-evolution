#ui.py

import pygame
import constants as C

def draw_loading_screen(screen, font, progress, total):
    """Draws a progress bar and loading text."""
    screen.fill(C.COLOR_BLACK)

    # Render text
    text_surface = font.render("Loading World...", True, C.COLOR_WHITE)
    text_rect = text_surface.get_rect(center=(C.SCREEN_WIDTH / 2, C.SCREEN_HEIGHT / 2 - C.UI_LOADING_TEXT_OFFSET_Y))
    screen.blit(text_surface, text_rect)

    # Draw progress bar
    bar_x = (C.SCREEN_WIDTH - C.UI_LOADING_BAR_WIDTH) / 2
    bar_y = (C.SCREEN_HEIGHT - C.UI_LOADING_BAR_HEIGHT) / 2
    
    progress_ratio = progress / total
    current_bar_width = C.UI_LOADING_BAR_WIDTH * progress_ratio

    # Background of the bar
    pygame.draw.rect(screen, C.COLOR_LOADING_BAR_BG, (bar_x, bar_y, C.UI_LOADING_BAR_WIDTH, C.UI_LOADING_BAR_HEIGHT))
    # Foreground of the bar
    pygame.draw.rect(screen, C.COLOR_LOADING_BAR_FG, (bar_x, bar_y, current_bar_width, C.UI_LOADING_BAR_HEIGHT))

    pygame.display.flip()