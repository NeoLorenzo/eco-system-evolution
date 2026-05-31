# Ecosystem Evolution (Public Archive)

## Project Status

This repository is now a **public archive**.

Development has been **halted**, the simulation is **not in a playable state**, and no further updates are planned for this Python version.

## About

Ecosystem Evolution is a Python-based simulation project focused on modeling ecosystem behavior with an emphasis on plant life, growth, competition, and long-timescale dynamics.  
It explores interactions between energy systems, environmental factors, structural growth, and simple ecological rules.

The project was built as an experimental large-scope simulation and served as a major learning step in simulation-oriented programming.

## Archive Note From The Author

Ecosystem Evolution was an important milestone in my development journey, and I believe it was one of the first major, large-scope simulation projects I ever embarked on. The project began while I was walking around in the south of Portugal, observing trees, and becoming fascinated by how these seemingly simple biological organisms are actually highly intricate systems.

This line of thinking was similar to what led me to start the genetic ant colony simulation project, which was my first programming project. However, Ecosystem Evolution attempted to simulate much larger, more macro-level systems. Because of the project's complexity, and because my enthusiasm for it eventually faded, it is not in a playable state and will probably never be touched again, at least not in its Python version.

Python is a great programming language, but over the years I have learned that it is not always the most effective tool for building these kinds of systems. Concepts from this simulation may still inspire future simulation projects, but I do not think I will ever make another project solely focused on plant life.

This project also taught me an important lesson about the difference between 2D and 3D systems, and about the complexity of trying to simulate 3D systems in a 2D way. It also planted one of the first seeds for my future interest in Unity development. I do not think I was at a stage where I felt comfortable diving deeply into Unity and all of its systems, but this project was definitely a step toward being able to handle bigger and more complicated development environments.

## What This Repository Contains

- A Python simulation loop built with `pygame`.
- Plant-focused lifecycle and energy modeling.
- Environmental sampling systems (temperature, humidity, elevation/terrain).
- Spatial partitioning (`quadtree`) and competition logic.
- Data management and performance-oriented structures using `numpy`.
- Supporting managers for time, logging, and graph generation.

## High-Level Structure

- `main.py`: Application entry point and simulation loop.
- `world.py`: Core world orchestration, scheduling, and bulk updates.
- `creatures.py`: Creature models (plants/animals) and lifecycle logic.
- `plant_manager.py`: Plant data storage and vectorized update operations.
- `environment.py`: Terrain/environment generation and rendering helpers.
- `quadtree.py`: Spatial indexing for neighborhood queries.
- `time_manager.py`: Time scaling and pause/speed controls.
- `graphing_manager.py`: Post-run graph output support.
- `constants.py`: Global simulation and tuning constants.

## Controls (Current Build)

- `SPACE`: Pause/unpause simulation time.
- `0-5`: Change simulation speed multiplier.
- `V`: Cycle environment view modes.
- Arrow keys: Pan camera.
- Mouse wheel / right click (as implemented): Zoom controls.
- Left click on plant: Focus debug logging for that plant.

## Running Locally

No polished setup or release pipeline is maintained for this archive. If you still want to inspect or run it:

1. Use Python 3.x in a local virtual environment.
2. Install required dependencies (for example `pygame`, `numpy`, and graphing dependencies if used).
3. Run:

```bash
python main.py
```

Because this repository is archived, setup issues and runtime issues may exist and are not guaranteed to be fixed.

## Why It Is Archived

- Scope grew significantly over time.
- Simulation complexity became difficult to maintain in this form.
- Motivation shifted to other projects and tools.
- Future simulation ideas are more likely to move toward game-engine-based workflows (for example, Unity) instead of continuing this Python codebase.

## License / Usage

This repository is published for historical, educational, and reference purposes.  
If you fork or reuse parts of it, please treat it as experimental archive code rather than actively supported software.

