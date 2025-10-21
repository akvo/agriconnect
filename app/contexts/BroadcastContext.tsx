import React, {
  createContext,
  useContext,
  useState,
  ReactNode,
  useEffect,
  useRef,
} from "react";

// Customer type matching the one from broadcast/index.tsx
export interface CropType {
  id: number;
  name: string;
}

export interface Customer {
  id: number;
  full_name: string | null;
  phone_number: string;
  language: string;
  crop_type: CropType | null;
  age_group: string | null;
  administrative: {
    id: number | null;
    name: string | null;
    path: string | null;
  };
}

interface BroadcastContextType {
  selectedMembers: Customer[];
  setSelectedMembers: (members: Customer[], callback?: () => void) => void;
  addMember: (member: Customer) => void;
  removeMember: (memberId: number) => void;
  clearMembers: () => void;
}

const BroadcastContext = createContext<BroadcastContextType | undefined>(
  undefined,
);

export const BroadcastProvider = ({ children }: { children: ReactNode }) => {
  const [selectedMembers, setSelectedMembersState] = useState<Customer[]>([]);
  const callbackRef = useRef<(() => void) | null>(null);

  // Call the callback after state updates
  useEffect(() => {
    if (callbackRef.current) {
      const callback = callbackRef.current;
      callbackRef.current = null;
      callback();
    }
  }, [selectedMembers]);

  const setSelectedMembers = (members: Customer[], callback?: () => void) => {
    if (callback) {
      callbackRef.current = callback;
    }
    setSelectedMembersState(members);
  };

  const addMember = (member: Customer) => {
    setSelectedMembersState((prev) => {
      // Avoid duplicates
      if (prev.some((m) => m.id === member.id)) {
        return prev;
      }
      return [...prev, member];
    });
  };

  const removeMember = (memberId: number) => {
    setSelectedMembersState((prev) => prev.filter((m) => m.id !== memberId));
  };

  const clearMembers = () => {
    setSelectedMembersState([]);
  };

  return (
    <BroadcastContext.Provider
      value={{
        selectedMembers,
        setSelectedMembers,
        addMember,
        removeMember,
        clearMembers,
      }}
    >
      {children}
    </BroadcastContext.Provider>
  );
};

export const useBroadcast = () => {
  const context = useContext(BroadcastContext);
  if (context === undefined) {
    throw new Error("useBroadcast must be used within a BroadcastProvider");
  }
  return context;
};
