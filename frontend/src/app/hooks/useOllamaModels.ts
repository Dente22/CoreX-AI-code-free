import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  deleteOllamaModel,
  fetchOllamaModels,
  fetchOllamaPullProgress,
  startOllamaPull,
  type OllamaModelCatalogItem,
  type OllamaPullProgress,
} from '../utils/aiProvider';

const POLL_INTERVAL_MS = 800;

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function useOllamaModels(enabled = true) {
  const [catalog, setCatalog] = useState<OllamaModelCatalogItem[]>([]);
  const [modelsDir, setModelsDir] = useState('');
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState('');
  const [pullProgress, setPullProgress] = useState<OllamaPullProgress | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError('');
    try {
      const data = await fetchOllamaModels();
      if (data.catalog) {
        setCatalog(data.catalog);
      }
      if (data.models_dir) {
        setModelsDir(data.models_dir);
      }
      if (!data.success && data.error) {
        setError(data.error);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Не удалось загрузить статус моделей');
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    void load();
  }, [load]);

  const installedById = useMemo(() => {
    const map: Record<string, boolean> = {};
    const needsImportById: Record<string, boolean> = {};
    for (const item of catalog) {
      map[item.id] = Boolean(item.installed);
      needsImportById[item.id] = Boolean(item.needs_import);
    }
    return { ready: map, needsImport: needsImportById };
  }, [catalog]);

  const waitForPull = useCallback(async (jobId: string) => {
    while (true) {
      const progress = await fetchOllamaPullProgress(jobId);
      setPullProgress(progress);
      if (progress.done) {
        return progress;
      }
      await sleep(POLL_INTERVAL_MS);
    }
  }, []);

  const pull = useCallback(
    async (providerId: string) => {
      setBusyId(providerId);
      setError('');
      setPullProgress(null);
      try {
        const started = await startOllamaPull(providerId);
        if (!started.success) {
          setError(started.error || 'Не удалось начать скачивание');
          return { success: false, error: started.error };
        }
        const jobId = started.job_id || providerId;
        if (started.progress) {
          setPullProgress(started.progress);
        }
        const finalProgress = await waitForPull(jobId);
        if (!finalProgress.success) {
          setError(finalProgress.error || 'Не удалось скачать модель');
          return { success: false, error: finalProgress.error };
        }
        await load();
        return { success: true };
      } catch (actionError) {
        const message = actionError instanceof Error ? actionError.message : 'Ошибка скачивания';
        setError(message);
        return { success: false, error: message };
      } finally {
        setBusyId('');
        setPullProgress(null);
      }
    },
    [load, waitForPull],
  );

  const remove = useCallback(
    async (providerId: string) => {
      setBusyId(providerId);
      setError('');
      try {
        const result = await deleteOllamaModel(providerId);
        if (!result.success) {
          setError(result.error || result.output || 'Не удалось удалить модель');
          return result;
        }
        await load();
        return result;
      } catch (actionError) {
        const message = actionError instanceof Error ? actionError.message : 'Ошибка удаления';
        setError(message);
        return { success: false, error: message };
      } finally {
        setBusyId('');
      }
    },
    [load],
  );

  return {
    catalog,
    modelsDir,
    loading,
    busyId,
    pullProgress,
    error,
    installedById: installedById.ready,
    needsImportById: installedById.needsImport,
    load,
    pull,
    remove,
  };
}
