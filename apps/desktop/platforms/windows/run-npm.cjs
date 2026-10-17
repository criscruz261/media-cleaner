// Give npm lifecycle scripts one unambiguous Windows PATH containing this Node.
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const nodeDirectory = path.dirname(process.execPath);
const npmCli = path.join(nodeDirectory, 'node_modules', 'npm', 'bin', 'npm-cli.js');
if (!fs.existsSync(npmCli)) throw new Error(`Missing npm CLI: ${npmCli}`);
const env = {};
const paths = [nodeDirectory];
for (const [key, value] of Object.entries(process.env)) {
  // Windows ignores case, but Node's child-process environment can contain
  // both PATH and Path; only one reaches the child. Merge them explicitly.
  if (key.toLowerCase() === 'path') paths.push(...value.split(';'));
  else env[key] = value;
}
env.Path = [...new Set(paths.filter(Boolean))].join(';');
env.PATHEXT = '.COM;.EXE;.BAT;.CMD';
const shell = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'cmd.exe');
// Avoid an inherited custom script-shell hiding Node from install scripts.
env.npm_config_script_shell = shell;
const probe = spawnSync(shell, ['/d', '/s', '/c', 'node --version'], { env, encoding: 'utf8' });
if (probe.error || probe.status !== 0) {
  throw new Error(`npm child process cannot find Node.js: ${probe.error || probe.stderr}`);
}
const result = spawnSync(process.execPath, [npmCli, ...process.argv.slice(2)], { env, stdio: 'inherit' });
if (result.error) throw result.error;
process.exit(result.status === null ? 1 : result.status);
