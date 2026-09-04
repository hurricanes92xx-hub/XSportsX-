"""Immediate canonical schedule refresh entrypoint.
Delegates to the production refresh pipeline.
"""
from scripts.refresh_schedules import main

if __name__ == "__main__":
    main()
