/**
 * Localización y ejecución del motor (cadlibre.bridge).
 *
 * En la app instalada se usa `cadlibre-motor.exe`, un ejecutable autónomo
 * generado con PyInstaller: el usuario final no necesita tener Python.
 * En desarrollo se usa el intérprete del venv del proyecto.
 */
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { app } from 'electron';

function raizProyecto(): string {
  if (app.isPackaged) {
    return process.resourcesPath;
  }
  // app/out/main → app → raíz "CAD LIBRE"
  return path.resolve(__dirname, '..', '..', '..');
}

/** Ejecutable autónomo del motor, si está disponible (app instalada). */
function motorEmpaquetado(): string | null {
  const exe = path.join(raizProyecto(), 'motor', 'cadlibre-motor.exe');
  return existsSync(exe) ? exe : null;
}

export function rutaPython(): string {
  if (process.env.CADLIBRE_PYTHON && existsSync(process.env.CADLIBRE_PYTHON)) {
    return process.env.CADLIBRE_PYTHON;
  }
  const venv = path.join(raizProyecto(), '.venv', 'Scripts', 'python.exe');
  if (existsSync(venv)) return venv;
  return 'python';
}

export interface RespuestaBridge {
  ok: boolean;
  error?: string;
  [clave: string]: unknown;
}

/** Ejecuta un comando del bridge y devuelve su respuesta JSON. */
export function ejecutarBridge(argumentos: string[]): Promise<RespuestaBridge> {
  const exe = motorEmpaquetado();
  const programa: string = exe ?? rutaPython();
  const args: string[] = exe ? argumentos : ['-m', 'cadlibre.bridge', ...argumentos];
  return new Promise((resolver) => {
    const proceso = spawn(programa, args, {
      cwd: raizProyecto(),
      windowsHide: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    });
    let salida = '';
    let errores = '';
    proceso.stdout.on('data', (d) => (salida += d.toString('utf-8')));
    proceso.stderr.on('data', (d) => (errores += d.toString('utf-8')));
    proceso.on('error', (e) =>
      resolver({ ok: false, error: `No se pudo ejecutar Python: ${e.message}` })
    );
    proceso.on('close', () => {
      const linea = salida.trim().split('\n').pop() ?? '';
      try {
        resolver(JSON.parse(linea) as RespuestaBridge);
      } catch {
        resolver({
          ok: false,
          error: `Respuesta inválida del motor Python.\n${errores || salida || '(sin salida)'}`
        });
      }
    });
  });
}
