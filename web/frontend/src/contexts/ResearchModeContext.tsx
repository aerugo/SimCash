import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

interface ResearchModeContextType {
  researchMode: boolean;
  toggleResearchMode: () => void;
  /** Get the appropriate label based on current mode */
  label: (game: string, research: string) => string;
}

const ResearchModeContext = createContext<ResearchModeContextType | null>(null);

const STORAGE_KEY = 'simcash-research-mode';

export function ResearchModeProvider({ children }: { children: ReactNode }) {
  const [researchMode, setResearchMode] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) === 'true'; } catch { return false; }
  });

  const toggleResearchMode = useCallback(() => {
    setResearchMode(prev => {
      const next = !prev;
      try { localStorage.setItem(STORAGE_KEY, String(next)); } catch { /* noop */ }
      return next;
    });
  }, []);

  const label = useCallback((game: string, research: string) => {
    return researchMode ? research : game;
  }, [researchMode]);

  return (
    <ResearchModeContext.Provider value={{ researchMode, toggleResearchMode, label }}>
      {children}
    </ResearchModeContext.Provider>
  );
}

export function useResearchMode() {
  const ctx = useContext(ResearchModeContext);
  if (!ctx) throw new Error('useResearchMode must be used within ResearchModeProvider');
  return ctx;
}
