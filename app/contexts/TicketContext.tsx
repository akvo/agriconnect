import { DAOManager } from "@/database/dao";
import { CreateTicketData, Ticket } from "@/database/dao/types/ticket";
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

const TicketContext = createContext<any>(null);

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

  const loadTickets = useCallback(async () => {
    try {
      const result = await dao.ticket.findAll(db);
      if (isMounted.current) {
        setTickets(result);
      }
    } catch (error) {
      console.error("Error loading tickets:", error);
    }
  }, [db, dao]);

  useEffect(() => {
    loadTickets();
  }, [loadTickets]);

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
    async (id: number, data: Partial<CreateTicketData>) => {
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
    <TicketContext.Provider value={{ tickets, createTicket, updateTicket }}>
      {children}
    </TicketContext.Provider>
  );
};
