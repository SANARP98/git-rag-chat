#!/usr/bin/env node

import { spawnSync } from 'child_process';
import fs from 'fs/promises';
import fsSync from 'fs';
import path from 'path';
import os from 'os';
import readline from 'readline';
import net from 'net';
import http from 'http';

const CONFIG = {
  repoName: 'git-rag-chat',
  repoUrl: 'https://github.com/SANARP98/git-rag-chat.git',
  networkName: 'chroma-net',
  containerName: 'chromadb-vespo',
  imageName: 'chroma-mcp-vespo-patched:latest',
  serverName: 'chromadb_context_vespo',
  chromaStartPort: 8003,
  chromaPortTries: 50,
  chromaReadySeconds: 40
};

const IS_WINDOWS = process.platform === 'win32';

function logInfo(message) {
  console.log(message);
}

function logWarn(message) {
  console.warn(`WARNING: ${message}`);
}

function logError(message) {
  console.error(`ERROR: ${message}`);
}

function commandExists(name) {
  if (IS_WINDOWS) {
    return spawnSync('where', [name], { stdio: 'ignore' }).status === 0;
  }
  return spawnSync('sh', ['-c', `command -v ${name}`], { stdio: 'ignore' }).status === 0;
}

function runCommand(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: options.stdio ?? 'pipe',
    encoding: 'utf-8',
    cwd: options.cwd,
    input: options.input
  });

  if (options.allowFail) {
    return result;
  }

  if (result.status !== 0) {
    const output = `${result.stdout || ''}${result.stderr || ''}`.trim();
    throw new Error(`${command} ${args.join(' ')} failed${output ? `: ${output}` : ''}`);
  }

  return result;
}

function createInterface() {
  return readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });
}

async function prompt(question, defaultValue = null) {
  const rl = createInterface();
  const promptText = defaultValue ? `${question} (default: ${defaultValue}): ` : `${question}: `;
  const answer = await new Promise(resolve => rl.question(promptText, resolve));
  rl.close();

  if (answer.trim() === '' && defaultValue !== null) {
    return defaultValue;
  }
  return answer.trim();
}

async function confirm(question, defaultValue = false) {
  const suffix = defaultValue ? 'Y/n' : 'y/N';
  const answer = (await prompt(`${question} (${suffix})`)).toLowerCase();
  if (!answer) {
    return defaultValue;
  }
  return answer === 'y' || answer === 'yes';
}

async function isPortFree(port) {
  return new Promise(resolve => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => {
      server.close(() => resolve(true));
    });
    server.listen(port, '127.0.0.1');
  });
}

async function findFreePort(startPort, maxTries) {
  for (let port = startPort; port < startPort + maxTries; port += 1) {
    if (await isPortFree(port)) {
      return port;
    }
  }
  throw new Error(`No free port found in range ${startPort}..${startPort + maxTries - 1}`);
}

function resolveDefaultInstallDir() {
  const homeDir = os.homedir();
  return path.join(homeDir, 'Documents');
}

async function ensureDirExists(dirPath) {
  if (!fsSync.existsSync(dirPath)) {
    const shouldCreate = await confirm(`Directory does not exist: ${dirPath}. Create it?`, false);
    if (!shouldCreate) {
      throw new Error('Installation cancelled by user.');
    }
    await fs.mkdir(dirPath, { recursive: true });
  }
}

function ensurePrereqs() {
  const missing = [];
  if (!commandExists('codex')) {
    missing.push('codex CLI');
  }
  if (!commandExists('docker')) {
    missing.push('Docker');
  }
  if (!commandExists('git')) {
    missing.push('Git');
  }
  if (!commandExists('node')) {
    missing.push('Node.js');
  }

  if (missing.length > 0) {
    throw new Error(`Missing prerequisites: ${missing.join(', ')}`);
  }
}

function ensureDockerRunning() {
  const result = runCommand('docker', ['ps'], { allowFail: true });
  if (result.status !== 0) {
    throw new Error('Docker is not running. Please start Docker Desktop and try again.');
  }
}

function toTomlString(value) {
  return `"${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
}

function writeFileIfChanged(filePath, content) {
  const existing = fsSync.existsSync(filePath) ? fsSync.readFileSync(filePath, 'utf-8') : null;
  if (existing !== content) {
    fsSync.mkdirSync(path.dirname(filePath), { recursive: true });
    fsSync.writeFileSync(filePath, content, 'utf-8');
  }
}

function getConfigPath() {
  return path.join(os.homedir(), '.codex', 'config.toml');
}

function stripServerConfig(configContent, serverName) {
  const startRegex = new RegExp(`^\\[mcp_servers\\.${serverName}\\]`, 'm');
  const match = startRegex.exec(configContent);
  if (!match) {
    return configContent.trimEnd();
  }

  const startIndex = match.index;
  const remainder = configContent.slice(startIndex + match[0].length);
  const nextMatch = remainder.match(/^\[/m);
  const endIndex = nextMatch ? startIndex + match[0].length + nextMatch.index : configContent.length;

  const before = configContent.slice(0, startIndex).trimEnd();
  const after = configContent.slice(endIndex).trimStart();

  return [before, after].filter(Boolean).join('\n\n');
}

async function ensureDockerNetwork(networkName) {
  const inspect = runCommand('docker', ['network', 'inspect', networkName], { allowFail: true });
  if (inspect.status !== 0) {
    runCommand('docker', ['network', 'create', networkName], { stdio: 'inherit' });
  }
}

function removeContainerIfExists(containerName) {
  const result = runCommand('docker', ['ps', '-a', '--filter', `name=^${containerName}$`, '--format', '{{.Names}}'], { allowFail: true });
  const existing = (result.stdout || '').trim();
  if (existing) {
    runCommand('docker', ['rm', '-f', containerName], { stdio: 'inherit' });
  }
}

function sleep(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function httpGet(url) {
  return new Promise(resolve => {
    const req = http.get(url, res => {
      res.resume();
      resolve(res.statusCode && res.statusCode >= 200 && res.statusCode < 300);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForChroma(port, maxSeconds) {
  const start = Date.now();
  const url = `http://localhost:${port}/api/v2/heartbeat`;

  while ((Date.now() - start) / 1000 < maxSeconds) {
    if (await httpGet(url)) {
      return;
    }
    sleep(1000);
  }

  throw new Error(`ChromaDB failed to start within ${maxSeconds} seconds.`);
}

function buildImage(patchedPath, imageName) {
  runCommand('docker', ['build', '-t', imageName, '-f', 'Dockerfile', '.'], {
    cwd: patchedPath,
    stdio: 'inherit'
  });
}

function testHandshake(networkName, containerName, imageName) {
  const payload = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}';
  const result = runCommand('docker', [
    'run', '--rm', '-i',
    '--network', networkName,
    '-e', `CHROMA_URL=http://${containerName}:8000`,
    imageName
  ], { input: payload, allowFail: true });

  const combined = `${result.stdout || ''}${result.stderr || ''}`.trim();
  const firstLine = combined.split(/\r?\n/)[0] || '';
  return firstLine;
}

function buildWrapperScript(codexDir) {
  if (IS_WINDOWS) {
    const wrapperPath = path.join(codexDir, 'docker-wrapper.ps1');
    const content = [
      '# Docker wrapper for dynamic workspace mounting in Codex MCP',
      'param(',
      '    [Parameter(ValueFromRemainingArguments)]',
      '    [string[]]$DockerArgs',
      ')',
      '',
      '$ErrorActionPreference = "Stop"',
      '',
      '$WorkspaceDir = $env:PWD',
      'if (-not $WorkspaceDir) {',
      '    $WorkspaceDir = (Get-Location).Path',
      '}',
      '',
      'function ConvertTo-DockerPath {',
      '    param([string]$Path)',
      '    $fullPath = (Resolve-Path $Path -ErrorAction Stop).Path',
      '    $drive = $fullPath.Substring(0, 1).ToLower()',
      '    $restPath = $fullPath.Substring(2) -replace "\\\\", "/"',
      '    return "/$drive$restPath"',
      '}',
      '',
      '$DockerPath = ConvertTo-DockerPath -Path $WorkspaceDir',
      '',
      '$DockerBin = $null',
      'if (Test-Path "C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe") {',
      '    $DockerBin = "C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe"',
      '} elseif (Get-Command docker -ErrorAction SilentlyContinue) {',
      '    $DockerBin = (Get-Command docker).Source',
      '} else {',
      '    Write-Error "Docker command not found"',
      '    exit 1',
      '}',
      '',
      '$ModifiedArgs = @()',
      '$SkipNext = $false',
      '$SkipNextName = $false',
      '$ContainerName = $null',
      '',
      'for ($i = 0; $i -lt $DockerArgs.Count; $i++) {',
      '    $arg = $DockerArgs[$i]',
      '    if ($SkipNextName) {',
      '        $SkipNextName = $false',
      '    } elseif ($SkipNext) {',
      '        $ModifiedArgs += "${DockerPath}:/workspace:ro"',
      '        $SkipNext = $false',
      '    } elseif ($arg -eq "--name" -and ($i + 1) -lt $DockerArgs.Count) {',
      '        $ContainerName = $DockerArgs[$i + 1]',
      '        $ModifiedArgs += $arg',
      '        $ModifiedArgs += $ContainerName',
      '        $SkipNextName = $true',
      '    } elseif ($arg -eq "-v") {',
      '        $ModifiedArgs += $arg',
      '        $SkipNext = $true',
      '    } elseif ($arg -like "*:/workspace:ro" -or $arg -like "*://workspace:ro") {',
      '        $ModifiedArgs += "${DockerPath}:/workspace:ro"',
      '    } else {',
      '        $ModifiedArgs += $arg',
      '    }',
      '}',
      '',
      'if ($ContainerName) {',
      '    & $DockerBin rm -f $ContainerName | Out-Null',
      '}',
      '',
      '& $DockerBin @ModifiedArgs',
      'exit $LASTEXITCODE',
      ''
    ].join('\r\n');
    writeFileIfChanged(wrapperPath, content);
    return wrapperPath;
  }

  const wrapperPath = path.join(codexDir, 'docker-wrapper.sh');
  const content = [
    '#!/bin/bash',
    '# Docker wrapper for dynamic workspace mounting in Codex MCP',
    '',
    'WORKSPACE_DIR="${PWD:-$(pwd)}"',
    '',
    'if [ -x "/usr/local/bin/docker" ]; then',
    '    DOCKER_BIN="/usr/local/bin/docker"',
    'elif command -v docker &> /dev/null; then',
    '    DOCKER_BIN="$(command -v docker)"',
    'else',
    '    echo "Error: docker command not found" >&2',
    '    exit 1',
    'fi',
    '',
    'ARGS=()',
    'SKIP_NEXT=false',
    'SKIP_NEXT_NAME=false',
    'CONTAINER_NAME=""',
    '',
    'for arg in "$@"; do',
    '  if [ "$SKIP_NEXT" = true ]; then',
    '    ARGS+=("${WORKSPACE_DIR}:/workspace:ro")',
    '    SKIP_NEXT=false',
    '  elif [[ "$arg" == "-v" ]]; then',
    '    ARGS+=("$arg")',
    '    SKIP_NEXT=true',
    '  elif [[ "$arg" == "--name" ]]; then',
    '    ARGS+=("$arg")',
    '    SKIP_NEXT_NAME=true',
    '  elif [ "$SKIP_NEXT_NAME" = true ]; then',
    '    CONTAINER_NAME="$arg"',
    '    ARGS+=("$arg")',
    '    SKIP_NEXT_NAME=false',
    '  elif [[ "$arg" == *":/workspace:ro" ]]; then',
    '    ARGS+=("${WORKSPACE_DIR}:/workspace:ro")',
    '  else',
    '    ARGS+=("$arg")',
    '  fi',
    'done',
    '',
    'if [ -n "$CONTAINER_NAME" ]; then',
    '  "$DOCKER_BIN" rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true',
    'fi',
    '',
    'exec "$DOCKER_BIN" "${ARGS[@]}"',
    ''
  ].join('\n');
  writeFileIfChanged(wrapperPath, content);
  fsSync.chmodSync(wrapperPath, 0o755);
  return wrapperPath;
}

function buildConfigSection({
  serverName,
  command,
  args,
  envVars,
  extraComment
}) {
  const header = [
    '',
    '# Patched vespo92 ChromaDB MCP server (single source of truth)',
    `# Auto-configured on ${new Date().toISOString()}`,
    extraComment ? `# ${extraComment}` : null,
    `[mcp_servers.${serverName}]`,
    `command = ${toTomlString(command)}`,
    'args = [',
    `  ${args.map(toTomlString).join(', ')}`,
    ']',
    envVars && envVars.length > 0 ? `env_vars = [${envVars.map(toTomlString).join(', ')}]` : null,
    'startup_timeout_sec = 45',
    'tool_timeout_sec = 180',
    'enabled = true',
    ''
  ].filter(Boolean);

  return header.join('\n');
}

function getDefaultRepoPath() {
  const cwd = process.cwd();
  const candidate = path.join(cwd, 'mcp', 'vespo-patched');
  if (fsSync.existsSync(candidate)) {
    return path.resolve(cwd);
  }

  if (path.basename(cwd) === 'vespo-patched') {
    const repoRoot = path.resolve(cwd, '..', '..');
    const patchedPath = path.join(repoRoot, 'mcp', 'vespo-patched');
    if (fsSync.existsSync(patchedPath)) {
      return repoRoot;
    }
  }

  return null;
}

async function main() {
  logInfo('=== Patched Vespo ChromaDB MCP Server Setup ===');

  ensurePrereqs();
  ensureDockerRunning();

  let repoRoot = getDefaultRepoPath();

  if (!repoRoot) {
    const defaultInstallDir = resolveDefaultInstallDir();
    const installDir = await prompt('Installation directory', defaultInstallDir);
    await ensureDirExists(installDir);

    repoRoot = path.join(installDir, CONFIG.repoName);

    if (fsSync.existsSync(repoRoot)) {
      const overwrite = await confirm(`Repository already exists at ${repoRoot}. Delete and re-clone?`, false);
      if (overwrite) {
        await fs.rm(repoRoot, { recursive: true, force: true });
      }
    }

    if (!fsSync.existsSync(repoRoot)) {
      runCommand('git', ['clone', CONFIG.repoUrl, repoRoot], { stdio: 'inherit' });
    }
  }

  const patchedPath = path.join(repoRoot, 'mcp', 'vespo-patched');
  if (!fsSync.existsSync(patchedPath)) {
    throw new Error(`Patched vespo server not found at ${patchedPath}`);
  }

  await ensureDockerNetwork(CONFIG.networkName);
  const chromaPort = await findFreePort(CONFIG.chromaStartPort, CONFIG.chromaPortTries);

  removeContainerIfExists(CONFIG.containerName);

  runCommand('docker', [
    'run', '-d',
    '--name', CONFIG.containerName,
    '--network', CONFIG.networkName,
    '-p', `${chromaPort}:8000`,
    'chromadb/chroma:latest'
  ], { stdio: 'inherit' });

  logInfo(`ChromaDB container started on port ${chromaPort}. Waiting for readiness...`);

  try {
    await waitForChroma(chromaPort, CONFIG.chromaReadySeconds);
  } catch (error) {
    logWarn(error.message);
  }

  buildImage(patchedPath, CONFIG.imageName);

  const handshake = testHandshake(CONFIG.networkName, CONFIG.containerName, CONFIG.imageName);
  if (handshake.includes('"result"')) {
    logInfo('MCP handshake looks healthy.');
  } else if (handshake) {
    logWarn(`Handshake output: ${handshake}`);
  } else {
    logWarn('Handshake produced no output.');
  }

  const codexDir = path.join(os.homedir(), '.codex');
  const wrapperPath = buildWrapperScript(codexDir);

  const configPath = getConfigPath();
  const existingConfig = fsSync.existsSync(configPath)
    ? fsSync.readFileSync(configPath, 'utf-8')
    : '';
  const cleanedConfig = stripServerConfig(existingConfig, CONFIG.serverName);

  const mcpContainerName = 'chromadb-mcp-server';
  let command = wrapperPath;
  let args = [
    'run', '--rm', '-i',
    '--name', mcpContainerName,
    '--network', CONFIG.networkName,
    '-e', `CHROMA_URL=http://${CONFIG.containerName}:8000`,
    '-e', `CHROMADB_URL=http://${CONFIG.containerName}:8000`,
    '-v', 'PLACEHOLDER:/workspace:ro',
    CONFIG.imageName
  ];
  let envVars = ['PWD'];
  let extraComment = 'Uses dynamic workspace mounting';

  if (IS_WINDOWS) {
    command = 'powershell.exe';
    args = [
      '-NoProfile',
      '-ExecutionPolicy', 'Bypass',
      '-File', wrapperPath,
      ...args
    ];
  }

  const newSection = buildConfigSection({
    serverName: CONFIG.serverName,
    command,
    args,
    envVars,
    extraComment
  });

  const finalConfig = `${cleanedConfig}${cleanedConfig ? '\n\n' : ''}${newSection}`;
  writeFileIfChanged(configPath, finalConfig);

  logInfo('');
  logInfo('Setup complete.');
  logInfo(`Repo: ${repoRoot}`);
  logInfo(`ChromaDB: http://localhost:${chromaPort}`);
  logInfo(`Config: ${configPath}`);
  logInfo(`Wrapper: ${wrapperPath}`);
  logInfo('Next: restart VS Code and start a new Codex chat.');
}

main().catch(error => {
  logError(error.message || String(error));
  process.exit(1);
});
