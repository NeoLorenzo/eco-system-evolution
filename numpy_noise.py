#numpy_noise.py

import numpy as np

GRADIENT_VECTORS = np.array([[0, 1], [0, -1], [1, 0], [-1, 0]])

def perlin_noise_2d(p, x, y, freq=1.0, octaves=1, persistence=0.5, lacunarity=2.0):
    """
    Generate 2D Perlin noise using a pre-computed permutation table.
    
    Args:
        p: The pre-shuffled permutation table.
        x, y: 2D numpy arrays of the same shape representing coordinates.
        # ... (other args are the same)
    """
    # The permutation table 'p' is now passed in, not created here.
    
    # Coordinates
    xi = x.astype(int)
    yi = y.astype(int)

    # Internal coordinates
    xf = x - xi
    yf = y - yi

    # Fade function
    u = fade(xf)
    v = fade(yf)

    # Noise components
    total_noise = np.zeros(x.shape)
    amplitude = 1.0
    
    # We don't need to modify freq inside the loop for this implementation
    # The coordinate scaling handles it.

    for _ in range(octaves):
        px0 = xi % 256
        px1 = (px0 + 1) % 256
        py0 = yi % 256
        py1 = (py0 + 1) % 256

        # Gradients
        g00 = gradient(p[p[px0] + py0], xf, yf)
        g01 = gradient(p[p[px0] + py1], xf, yf - 1)
        g10 = gradient(p[p[px1] + py0], xf - 1, yf)
        g11 = gradient(p[p[px1] + py1], xf - 1, yf - 1)

        # Interpolation
        x1 = lerp(g00, g10, u)
        x2 = lerp(g01, g11, u)
        octave_noise = lerp(x1, x2, v)
        
        total_noise += octave_noise * amplitude
        
        amplitude *= persistence
        
        # Update coordinates for next octave by increasing frequency
        x, y = x * lacunarity, y * lacunarity
        xi, yi = x.astype(int), y.astype(int)
        xf, yf = x - xi, y - yi
        u, v = fade(xf), fade(yf)

    return total_noise

def lerp(a, b, x):
    "Linear interpolation."
    return a + x * (b - a)

def fade(t):
    "6t^5 - 15t^4 + 10t^3"
    return t * t * t * (t * (t * 6 - 15) + 10)

def gradient(h, x, y):
    """Grad converts h to the right gradient vector and return the dot product with (x,y)"""
    # --- MODIFIED: Use the pre-defined constant instead of creating a new array ---
    g = GRADIENT_VECTORS[h % 4]
    return g[..., 0] * x + g[..., 1] * y