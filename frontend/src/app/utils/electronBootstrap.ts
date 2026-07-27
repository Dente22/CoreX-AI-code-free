export {
  resolveProjectRoot,
  resolvePythonCommand,
  resolvePythonSpawnArgs,
  shouldEnableAutoUpdates,
  resolveBackendHealthTimeoutMs,
  shouldOpenWindowBeforeBackend,
  COREX_OLLAMA_PORT,
  parseWindowsListeningPid,
  killPidTreeSync,
  killCoreXOllamaSync,
  killCoreXRuntimeSync,
  collectDescendantPids,
  parseWmicProcessRows,
  killZombieLlamaServersSync,
} from '../../../electronBootstrap.cjs';

export type {
  PathJoin,
  ExistsSync,
  ResolveProjectRootOptions,
  ResolvePythonCommandOptions,
  ResolvePythonSpawnArgsOptions,
  ShouldEnableAutoUpdatesOptions,
  ResolveBackendHealthTimeoutMsOptions,
} from './electronBootstrapTypes';
