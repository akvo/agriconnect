import { useState, useCallback } from "react";

interface UseAISuggestionReturn {
  aiSuggestion: string | null;
  aiSuggestionLoading: boolean;
  aiSuggestionUsed: boolean;
  setAISuggestion: React.Dispatch<React.SetStateAction<string | null>>;
  setAISuggestionLoading: React.Dispatch<React.SetStateAction<boolean>>;
  setAISuggestionUsed: React.Dispatch<React.SetStateAction<boolean>>;
  handleAcceptSuggestion: (suggestion: string) => void;
}

export const useAISuggestion = (): UseAISuggestionReturn => {
  const [aiSuggestion, setAISuggestion] = useState<string | null>(null);
  const [aiSuggestionLoading, setAISuggestionLoading] =
    useState<boolean>(false);
  const [aiSuggestionUsed, setAISuggestionUsed] = useState<boolean>(false);

  const handleAcceptSuggestion = useCallback((suggestion: string) => {
    setAISuggestion(null);
    setAISuggestionLoading(false);
    setAISuggestionUsed(true);
  }, []);

  return {
    aiSuggestion,
    aiSuggestionLoading,
    aiSuggestionUsed,
    setAISuggestion,
    setAISuggestionLoading,
    setAISuggestionUsed,
    handleAcceptSuggestion,
  };
};
