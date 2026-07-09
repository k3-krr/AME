import { useState, useCallback } from 'react';

export const useStream = () => {
  const [streamData, setStreamData] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  const resetStream = useCallback(() => {
    setStreamData('');
    setLoading(false);
  }, []);

  return {
    streamData,
    loading,
    setStreamData,
    setLoading,
    resetStream,
  };
};
