# -*- coding: utf-8 -*-
"""Interfaz gráfica de CAD LIBRE (Tkinter, tema negro + verde neón)."""

from __future__ import annotations

import os
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, ttk

from . import __version__
from .converter import VERSIONES_SEGURAS, VERSION_SALIDA_DEFECTO
from .pipeline import motor_disponible, procesar

NEGRO = "#0d0d0d"
PANEL = "#161616"
VERDE = "#39ff14"
GRIS = "#bbbbbb"
ROJO = "#ff5555"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"CAD LIBRE {__version__} — DWG → DXF georreferenciado")
        self.geometry("860x640")
        self.configure(bg=NEGRO)
        self.archivos: list[str] = []
        self.carpeta_salida: str | None = None
        self._construir()
        self._estado_motor()

    # ------------------------------------------------------------------ UI
    def _construir(self):
        tk.Label(
            self, text="CAD LIBRE", font=("Segoe UI", 22, "bold"),
            fg=VERDE, bg=NEGRO,
        ).pack(pady=(14, 0))
        tk.Label(
            self,
            text="Convierte DWG a DXF conservando coordenadas, capas, bloques,"
                 " textos, cotas y georreferenciación. Sin mover ni escalar nada.",
            font=("Segoe UI", 10), fg=GRIS, bg=NEGRO, wraplength=780,
        ).pack(pady=(2, 10))

        barra = tk.Frame(self, bg=NEGRO)
        barra.pack(fill="x", padx=16)
        self._boton(barra, "➕ Agregar DWG…", self._agregar).pack(side="left")
        self._boton(barra, "🗀 Carpeta de salida…", self._elegir_salida).pack(
            side="left", padx=8
        )
        tk.Label(barra, text="Versión DXF:", fg=GRIS, bg=NEGRO).pack(
            side="left", padx=(16, 4)
        )
        self.version = tk.StringVar(value=VERSION_SALIDA_DEFECTO)
        combo = ttk.Combobox(
            barra, textvariable=self.version, values=list(VERSIONES_SEGURAS),
            state="readonly", width=10,
        )
        combo.pack(side="left")
        self.btn_convertir = self._boton(
            barra, "⚡ CONVERTIR", self._convertir, destacado=True
        )
        self.btn_convertir.pack(side="right")

        self.lista = tk.Listbox(
            self, bg=PANEL, fg="white", selectbackground=VERDE,
            selectforeground=NEGRO, height=6, borderwidth=0,
            highlightthickness=1, highlightbackground="#2a2a2a",
        )
        self.lista.pack(fill="x", padx=16, pady=(10, 4))

        self.log = tk.Text(
            self, bg=PANEL, fg=GRIS, insertbackground=VERDE, borderwidth=0,
            highlightthickness=1, highlightbackground="#2a2a2a",
            font=("Consolas", 9), state="disabled",
        )
        self.log.tag_configure("ok", foreground=VERDE)
        self.log.tag_configure("error", foreground=ROJO)
        self.log.pack(fill="both", expand=True, padx=16, pady=(4, 8))

        self.estado = tk.Label(
            self, text="", anchor="w", fg=GRIS, bg=NEGRO, font=("Segoe UI", 9)
        )
        self.estado.pack(fill="x", padx=16, pady=(0, 10))

    def _boton(self, padre, texto, comando, destacado=False):
        return tk.Button(
            padre, text=texto, command=comando,
            bg=VERDE if destacado else PANEL,
            fg=NEGRO if destacado else "white",
            activebackground="#2ecc0e" if destacado else "#222222",
            activeforeground=NEGRO if destacado else VERDE,
            font=("Segoe UI", 10, "bold" if destacado else "normal"),
            relief="flat", padx=14, pady=6, cursor="hand2",
        )

    # -------------------------------------------------------------- acciones
    def _estado_motor(self):
        motor = motor_disponible()
        if motor:
            self.estado.config(text=f"Motor de conversión: {motor}", fg=GRIS)
        else:
            self.estado.config(
                text="⚠ ODA File Converter no está instalado — descárguelo gratis en "
                     "opendesign.com/guestfiles/oda_file_converter "
                     "(los DXF sí pueden procesarse sin él).",
                fg=ROJO,
            )

    def _agregar(self):
        rutas = filedialog.askopenfilenames(
            title="Seleccione archivos DWG o DXF",
            filetypes=[("Dibujos CAD", "*.dwg *.dxf"), ("DWG", "*.dwg"), ("DXF", "*.dxf")],
        )
        for ruta in rutas:
            if ruta not in self.archivos:
                self.archivos.append(ruta)
                self.lista.insert("end", ruta)

    def _elegir_salida(self):
        carpeta = filedialog.askdirectory(title="Carpeta de salida")
        if carpeta:
            self.carpeta_salida = carpeta
            self._escribir(f"Carpeta de salida: {carpeta}\n")

    def _convertir(self):
        if not self.archivos:
            self._escribir("Agregue al menos un archivo DWG.\n", "error")
            return
        self.btn_convertir.config(state="disabled")
        threading.Thread(target=self._trabajo, daemon=True).start()

    def _trabajo(self):
        for ruta in list(self.archivos):
            try:
                resultado = procesar(ruta, self.carpeta_salida, self.version.get())
                self._escribir("\n" + resultado.reporte() + "\n", "ok")
            except Exception as e:
                self._escribir(f"\n✘ {os.path.basename(ruta)}: {e}\n", "error")
                traceback.print_exc()
        self.after(0, lambda: self.btn_convertir.config(state="normal"))

    def _escribir(self, texto, etiqueta=None):
        def _hacer():
            self.log.config(state="normal")
            self.log.insert("end", texto, etiqueta)
            self.log.see("end")
            self.log.config(state="disabled")
        self.after(0, _hacer)


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
