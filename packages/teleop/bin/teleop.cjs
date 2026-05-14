#!/usr/bin/env node
/**
 * npm wrapper: runs the Python `teleop` stack (after `pip install teleopsh` or `pip install -e .`).
 */
const { spawn, spawnSync } = require('child_process');
const fs = require('fs');

/**
 * @returns {string[] | null} argv0-style command, e.g. ['py', '-3'] or ['C:\\venv\\Scripts\\python.exe']
 */
function findPythonCmd() {
  if (process.env.TELEOP_PYTHON) {
    const p = process.env.TELEOP_PYTHON;
    if (fs.existsSync(p)) return [p];
    console.error(`[teleop] TELEOP_PYTHON is set but file not found: ${p}`);
  }
  const candidates = [['py', '-3'], ['python3'], ['python']];
  for (const cmd of candidates) {
    const r = spawnSync(cmd[0], [...cmd.slice(1), '-c', 'import sys; sys.exit(0)'], {
      encoding: 'utf8',
    });
    if (r.status === 0) return cmd;
  }
  return null;
}

function pythonHasTeleop(cmd) {
  const r = spawnSync(cmd[0], [...cmd.slice(1), '-c', 'import importlib.util as u; import sys; sys.exit(0 if u.find_spec("teleop") else 1)'], {
    encoding: 'utf8',
  });
  return r.status === 0;
}

/** Strip leading `--` tokens (npx passes them through; Python argparse rejects them). */
function forwardArgsFromArgv(argv) {
  let out = argv.slice(2);
  while (out.length && out[0] === '--') {
    out = out.slice(1);
  }
  return out;
}

function main() {
  const cmd = findPythonCmd();
  if (!cmd) {
    console.error(
      '[teleop] No Python 3 found on PATH. Install Python 3.10+ or set TELEOP_PYTHON to your interpreter.'
    );
    process.exit(1);
  }

  if (!pythonHasTeleop(cmd)) {
    console.error(`[teleop] Python module "teleop" is not installed for: ${cmd.join(' ')}
Install from this repo:
  ${cmd.join(' ')} -m pip install -e .
Or after publishing to PyPI:
  ${cmd.join(' ')} -m pip install teleopsh
`);
    process.exit(1);
  }

  const child = spawn(cmd[0], [...cmd.slice(1), '-m', 'teleop', ...forwardArgsFromArgv(process.argv)], {
    stdio: 'inherit',
    env: { ...process.env },
  });
  child.on('exit', (code, signal) => {
    if (signal) process.kill(process.pid, signal);
    else process.exit(code ?? 1);
  });
}

main();
