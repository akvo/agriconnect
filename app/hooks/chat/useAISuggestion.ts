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

export const useAISuggestion = (
  setText: React.Dispatch<React.SetStateAction<string>>,
): UseAISuggestionReturn => {
  const [aiSuggestion, setAISuggestion] = useState<string | null>(null);
  const [aiSuggestionLoading, setAISuggestionLoading] = useState<boolean>(false);
  const [aiSuggestionUsed, setAISuggestionUsed] = useState<boolean>(false);

  const handleAcceptSuggestion = useCallback(
    (suggestion: string) => {
      setText(suggestion);
      setAISuggestion(null);
      setAISuggestionLoading(false);
      setAISuggestionUsed(true);
    },
    [setText],
  );

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
