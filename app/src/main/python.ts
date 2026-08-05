/**
 * Localización y ejecución del motor Python (cadlibre.bridge).
 *
 * Orden de búsqueda del intérprete:
 *   1. Variable de entorno CADLIBRE_PYTHON
 *   2. El venv del proyecto: <raíz>/.venv/Scripts/python.exe
 *   3. "python" del PATH
 *
 * El paquete `cadlibre` vive en la raíz del proyecto (junto a app/) en
 * desarrollo, o en resources/cadlibre cuando la app está empaquetada.
 */
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { app } from 'electron';

function raizProyecto(): string {
  if (app.isPackaged) {
    return process.resourcesPath; // resources/cadlibre
  }
  // app/out/main → app → raíz "CAD LIBRE"
  return path.resolve(__dirname, '..', '..', '..');
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
  return new Promise((resolver) => {
    const proceso = spawn(rutaPython(), ['-m', 'cadlibre.bridge', ...argumentos], {
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
