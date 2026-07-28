export type PathJoin = (...parts: string[]) => string;
export type ExistsSync = (target: string) => boolean;

export interface ResolveProjectRootOptions {
  isPackaged: boolean;
  resourcesPath: string;
  dirname: string;
  joinPath?: PathJoin;
}

export interface ResolvePythonCommandOptions {
  isPackaged: boolean;
  resourcesPath: string;
  platform: NodeJS.Platform | string;
  projectRoot?: string;
  env?: Record<string, string | undefined>;
  existsSync?: ExistsSync;
  joinPath?: PathJoin;
}

export interface ResolvePythonSpawnArgsOptions {
  pythonCommand: string;
  platform: NodeJS.Platform | string;
  mainPy: string;
  port: number | string;
}

export interface ShouldEnableAutoUpdatesOptions {
  isDev: boolean;
  updateUrl?: string | null;
}

export interface ResolveBackendHealthTimeoutMsOptions {
  hasEmbeddedPython?: boolean;
  isPackaged?: boolean;
}
