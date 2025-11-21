import { DAOManager } from "@/database/dao";
import {
  CreateTicketData,
  UpdateTicketData,
  Ticket,
} from "@/database/dao/types/ticket";
import { useDatabase } from "@/database/context";
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  useRef,
  useMemo,
  ReactNode,
} from "react";

interface TicketContextType {
  tickets: Ticket[];
  setTickets: React.Dispatch<React.SetStateAction<Ticket[]>>;
  getTicketsByStatus: (status: "open" | "resolved") => Ticket[];
  createTicket: (data: CreateTicketData) => Promise<void>;
  updateTicket: (id: number, data: Partial<UpdateTicketData>) => Promise<void>;
}

const TicketContext = createContext<TicketContextType | undefined>(undefined);

export const useTicket = () => {
  const context = useContext(TicketContext);
  if (!context) {
    throw new Error("useTicket must be used within a TicketProvider");
  }
  return context;
};

export const TicketProvider: React.FC<{ children: ReactNode }> = ({
  children,
}: {
  children: ReactNode;
}) => {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const db = useDatabase();
  const isMounted = useRef(true);

  // Create DAO manager with database from context
  const dao = useMemo(() => new DAOManager(db), [db]);

  useEffect(() => {
    return () => {
      isMounted.current = false;
    };
  }, []);

  // ✅ CORRECT: Load ALL tickets from SQLite (no limit)
  const loadTickets = useCallback(async () => {
    try {
      const allTickets = await dao.ticket.findAll(db);
      if (isMounted.current) {
        setTickets(allTickets);
        console.log(
          `[TicketContext] Loaded ${allTickets.length} tickets from SQLite`,
        );
      }
    } catch (error) {
      console.error("Error loading tickets:", error);
    }
  }, [db, dao]);

  useEffect(() => {
    loadTickets();
  }, [loadTickets]);

  // Filter tickets by status (in-memory operation)
  const getTicketsByStatus = useCallback(
    (status: "open" | "resolved") => {
      return tickets.filter((t: Ticket) => {
        const isResolved = !!t.resolvedAt;
        return status === "resolved" ? isResolved : !isResolved;
      });
    },
    [tickets],
  );

  const createTicket = useCallback(
    async (data: CreateTicketData) => {
      try {
        const newTicket = await dao.ticket.create(db, data);
        if (isMounted.current) {
          setTickets((prev: Ticket[]) => [newTicket, ...prev]);
        }
      } catch (error) {
        console.error("Error creating ticket:", error);
      }
    },
    [db, dao],
  );

  const updateTicket = useCallback(
    async (id: number, data: Partial<UpdateTicketData>) => {
      try {
        const success = await dao.ticket.update(db, id, data);
        if (success && isMounted.current) {
          setTickets((prev: Ticket[]) =>
            prev.map((t) => (t.id === id ? { ...t, ...data } : t)),
          );
        }
      } catch (error) {
        console.error("Error updating ticket:", error);
      }
    },
    [db, dao],
  );

  return (
    <TicketContext.Provider
      value={{
        tickets,
        setTickets,
        getTicketsByStatus,
        createTicket,
        updateTicket,
      }}
    >
      {children}
    </TicketContext.Provider>
  );
};
