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

export interface SavedGroup {
  id: number;
  name: string;
  contact_count: number;
  crop_types: number[] | null;
  age_groups: string[] | null;
  created_at: string;
}

export interface GroupMember {
  customer_id: number;
  phone_number: string;
  full_name: string | null;
  crop_type: CropType | null;
}

export interface GroupDetail {
  id: number;
  name: string;
  contacts: GroupMember[];
  crop_types: number[] | null;
  age_groups: string[] | null;
  created_at?: string | null;
  contact_count?: number | null;
}

interface BroadcastContextType {
  selectedMembers: GroupMember[];
  setSelectedMembers: (members: GroupMember[], callback?: () => void) => void;
  addMember: (member: GroupMember) => void;
  removeMember: (memberId: number) => void;
  clearMembers: () => void;
  selectedCropTypes: number[];
  setSelectedCropTypes: (cropTypes: number[]) => void;
  selectedAgeGroups: string[];
  setSelectedAgeGroups: (ageGroups: string[]) => void;
  // Shared data
  cropTypes: CropType[];
  setCropTypes: (cropTypes: CropType[]) => void;
  activeGroup: GroupDetail | null;
  setActiveGroup: (group: GroupDetail | null) => void;
}

const BroadcastContext = createContext<BroadcastContextType | undefined>(
  undefined,
);

export const BroadcastProvider = ({ children }: { children: ReactNode }) => {
  const [selectedMembers, setSelectedMembersState] = useState<GroupMember[]>(
    [],
  );
  const [selectedCropTypes, setSelectedCropTypes] = useState<number[]>([]);
  const [selectedAgeGroups, setSelectedAgeGroups] = useState<string[]>([]);
  const [cropTypes, setCropTypes] = useState<CropType[]>([]);
  const [activeGroup, setActiveGroup] = useState<GroupDetail | null>(null);
  const callbackRef = useRef<(() => void) | null>(null);

  // Call the callback after state updates
  useEffect(() => {
    if (callbackRef.current) {
      const callback = callbackRef.current;
      callbackRef.current = null;
      callback();
    }
  }, [selectedMembers]);

  const setSelectedMembers = (
    members: GroupMember[],
    callback?: () => void,
  ) => {
    if (callback) {
      callbackRef.current = callback;
    }
    setSelectedMembersState(members);
  };

  const addMember = (member: GroupMember) => {
    setSelectedMembersState((prev) => {
      // Avoid duplicates
      if (prev.some((m) => m.customer_id === member.customer_id)) {
        return prev;
      }
      return [...prev, member];
    });
  };

  const removeMember = (memberId: number) => {
    setSelectedMembersState((prev) =>
      prev.filter((m) => m.customer_id !== memberId),
    );
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
        selectedCropTypes,
        setSelectedCropTypes,
        selectedAgeGroups,
        setSelectedAgeGroups,
        cropTypes,
        setCropTypes,
        activeGroup,
        setActiveGroup,
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
