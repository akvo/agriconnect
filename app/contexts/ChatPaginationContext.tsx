import React, { createContext, useContext, useState, ReactNode } from "react";

type Store = Record<string, number>;

type ContextShape = {
  getVisibleDayCount: (ticketId?: string) => number;
  setVisibleDayCountFor: (ticketId: string | undefined, value: number) => void;
};

const ChatPaginationContext = createContext<ContextShape>({
  getVisibleDayCount: () => 0,
  setVisibleDayCountFor: () => {},
});

export const ChatPaginationProvider = ({
  children,
}: {
  children?: ReactNode;
}) => {
  const [store, setStore] = useState<Store>({});

  const getVisibleDayCount = (ticketId?: string) => {
    const key = ticketId ?? "global";
    return store[key] ?? 0;
  };

  const setVisibleDayCountFor = (
    ticketId: string | undefined,
    value: number,
  ) => {
    const key = ticketId ?? "global";
    setStore((s: Store) => ({ ...s, [key]: value }));
  };

  return (
    <ChatPaginationContext.Provider
      value={{ getVisibleDayCount, setVisibleDayCountFor }}
    >
      {children}
    </ChatPaginationContext.Provider>
  );
};

export const useChatPagination = () => useContext(ChatPaginationContext);
