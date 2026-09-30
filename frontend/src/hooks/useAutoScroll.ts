import { useCallback, useEffect, useRef, useState } from 'react';

export interface AutoScrollState {
  containerRef: React.RefObject<HTMLDivElement>;
  unseenCount: number;
  onScroll: () => void;
  scrollToBottom: () => void;
}

/**
 * Keeps the log pinned to the newest row, but never fights the operator: as soon
 * as they scroll up, pinning is released and the new-row count is surfaced.
 */
export function useAutoScroll(dependency: unknown, thresholdPx = 48): AutoScrollState {
  const containerRef = useRef<HTMLDivElement>(null);
  const [pinned, setPinned] = useState(true);
  const [unseenCount, setUnseenCount] = useState(0);
  const lastCountRef = useRef(0);

  const handleScroll = useCallback(() => {
    const element = containerRef.current;
    if (!element) {
      return;
    }
    const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
    const atBottom = distance <= thresholdPx;
    setPinned(atBottom);
    if (atBottom) {
      setUnseenCount(0);
    }
  }, [thresholdPx]);

  const onScroll = useCallback(() => {
    handleScroll();
  }, [handleScroll]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return;
    }
    if (pinned) {
      element.scrollTop = element.scrollHeight;
      setUnseenCount(0);
    }
  }, [dependency, pinned]);

  useEffect(() => {
    const count = Array.isArray(dependency) ? dependency.length : 0;
    if (lastCountRef.current !== 0 && count > lastCountRef.current && !pinned) {
      setUnseenCount((previous) => previous + (count - lastCountRef.current));
    }
    lastCountRef.current = count;
  }, [dependency, pinned]);

  const scrollToBottom = useCallback(() => {
    const element = containerRef.current;
    if (element) {
      element.scrollTop = element.scrollHeight;
    }
    setPinned(true);
    setUnseenCount(0);
  }, []);

  return { containerRef, unseenCount, onScroll, scrollToBottom };
}
