# -*- coding: utf-8 -*-
"""Punto de entrada para PyInstaller.

Empaqueta cadlibre.bridge en un ejecutable autónomo (cadlibre-motor.exe) que
la aplicación Electron invoca sin necesidad de que el usuario final tenga
Python instalado.
"""

from cadlibre.bridge import main

if __name__ == "__main__":
    main()
