import { useCallback, useEffect, useState } from 'react';
import {
  buildFallbackRuntime,
  createOnlineProvider,
  deleteOnlineProvider,
  fetchAiRuntime,
  setAiMode,
  setAiProvider,
  setOnlineProvider,
  type AiMode,
  type AiRuntimeSnapshot,
} from '../utils/aiProvider';
import { resolveModeAfterChange } from '../utils/aiRuntimeUi';

function applySnapshot(data: AiRuntimeSnapshot): AiRuntimeSnapshot {
  return {
    ...data,
    local: data.local ?? buildFallbackRuntime().local,
    online: data.online ?? buildFallbackRuntime().online,
  };
}

export function useAiRuntime() {
  const [runtime, setRuntime] = useState<AiRuntimeSnapshot>(() => buildFallbackRuntime());
  const [loading, setLoading] = useState(true);
  const [synced, setSynced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const loadRuntime = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchAiRuntime();
      if (!data.mode) {
        throw new Error('Backend не вернул конфигурацию AI');
      }
      setRuntime(applySnapshot(data));
      setSynced(true);
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : 'Ошибка загрузки AI';
      setError(message);
      setSynced(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRuntime();
  }, [loadRuntime]);

  const updateFromResponse = (data: AiRuntimeSnapshot & { success?: boolean; error?: string }) => {
    if (data.mode) {
      setRuntime(applySnapshot(data));
      setSynced(true);
    }
    if (data.error) {
      setError(data.error);
    } else {
      setError('');
    }
    return Boolean(data.success ?? data.mode);
  };

  const changeMode = useCallback(async (mode: AiMode) => {
    setBusy(true);
    setRuntime((prev) => ({ ...prev, mode }));
    try {
      const data = await setAiMode(mode);
      const nextMode = resolveModeAfterChange(mode, data.mode);
      if (nextMode) {
        setRuntime((prev) => applySnapshot({ ...prev, ...data, mode: nextMode }));
        setSynced(true);
      }
      if (data.error) {
        setError(data.error);
      } else {
        setError('');
      }
      return data.success !== false;
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Ошибка смены режима');
      return false;
    } finally {
      setBusy(false);
    }
  }, []);

  const selectLocal = useCallback(async (providerId: string) => {
    setBusy(true);
    try {
      const data = await setAiProvider(providerId);
      if (!data.success) {
        setError(data.error ?? 'Не удалось выбрать локальную модель');
        return false;
      }
      await loadRuntime();
      return true;
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Ошибка выбора модели');
      return false;
    } finally {
      setBusy(false);
    }
  }, [loadRuntime]);

  const selectOnline = useCallback(async (providerId: string) => {
    setBusy(true);
    try {
      const data = await setOnlineProvider(providerId);
      return updateFromResponse(data);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Ошибка выбора онлайн модели');
      return false;
    } finally {
      setBusy(false);
    }
  }, []);

  const addOnlineProvider = useCallback(
    async (payload: { name: string; base_url: string; api_key: string; model_name: string; api_type: 'openai' | 'gemini' }) => {
      setBusy(true);
      try {
        const data = await createOnlineProvider(payload);
        return updateFromResponse(data);
      } catch (saveError) {
        setError(saveError instanceof Error ? saveError.message : 'Ошибка добавления API');
        return false;
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  const removeOnlineProvider = useCallback(async (providerId: string) => {
    setBusy(true);
    try {
      const data = await deleteOnlineProvider(providerId);
      return updateFromResponse(data);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Ошибка удаления API');
      return false;
    } finally {
      setBusy(false);
    }
  }, []);

  return {
    runtime,
    loading,
    synced,
    busy,
    error,
    loadRuntime,
    changeMode,
    selectLocal,
    selectOnline,
    addOnlineProvider,
    removeOnlineProvider,
  };
}
