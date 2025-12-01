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

// Hybrid Pagination Configuration
// Open tickets are naturally bounded (~50-500 max), safe to load all
// Resolved tickets grow indefinitely, need pagination for scalability
const OPEN_PAGE_SIZE = 10; // Load ALL open tickets (bounded by customers)
const RESOLVED_PAGE_SIZE = 10; // Load 10 resolved tickets at a time (unbounded growth)

interface TicketContextType {
  tickets: Ticket[];
  setTickets: React.Dispatch<React.SetStateAction<Ticket[]>>;
  getTicketsByStatus: (status: "open" | "resolved") => Ticket[];
  loadMoreResolved: (currentCount: number) => Promise<boolean>;
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

  // Hybrid Loading Strategy
  // Load ALL open tickets (bounded) + first 10 resolved (paginated)
  const loadTickets = useCallback(async () => {
    try {
      // Load ALL open tickets (naturally bounded by customer count ~50-500)
      const openResult = await dao.ticket.findByStatus(
        db,
        "open",
        1,
        OPEN_PAGE_SIZE,
      );

      // Load first 10 resolved tickets (paginated for scalability)
      const resolvedResult = await dao.ticket.findByStatus(
        db,
        "resolved",
        1,
        RESOLVED_PAGE_SIZE,
      );

      // Combine both results
      const combined = [...openResult.tickets, ...resolvedResult.tickets];

      if (isMounted.current) {
        setTickets(combined);
        console.log(
          `[TicketContext] Loaded ${openResult.tickets.length} open + ${resolvedResult.tickets.length} resolved tickets from SQLite (hybrid strategy)`,
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

  // Load more resolved tickets from cache (pagination)
  // This method loads the next page of resolved tickets from SQLite WITHOUT hitting the API
  const loadMoreResolved = useCallback(
    async (currentResolvedCount: number): Promise<boolean> => {
      try {
        // Calculate next page number based on current count
        const nextPage =
          Math.floor(currentResolvedCount / RESOLVED_PAGE_SIZE) + 1;

        console.log(
          `[TicketContext] Loading more resolved tickets from cache (page ${nextPage}, current count: ${currentResolvedCount})`,
        );

        // Fetch next page from SQLite cache
        const resolvedResult = await dao.ticket.findByStatus(
          db,
          "resolved",
          nextPage,
          RESOLVED_PAGE_SIZE,
        );

        if (resolvedResult.tickets.length > 0) {
          // ✅ Filter out duplicates before appending
          if (isMounted.current) {
            setTickets((prev: Ticket[]) => {
              const existingIds = new Set(prev.map((t) => t.id));
              const newTickets = resolvedResult.tickets.filter(
                (t) => !existingIds.has(t.id),
              );

              if (newTickets.length > 0) {
                console.log(
                  `[TicketContext] Loaded ${newTickets.length} more resolved tickets from cache (${resolvedResult.tickets.length - newTickets.length} duplicates filtered)`,
                );
                return [...prev, ...newTickets];
              } else {
                console.log(
                  "[TicketContext] All tickets from page already exist (duplicates filtered)",
                );
                return prev;
              }
            });
          }
          return true; // Has more tickets
        } else {
          console.log("[TicketContext] No more resolved tickets in cache");
          return false; // No more tickets
        }
      } catch (error) {
        console.error("Error loading more resolved tickets:", error);
        return false;
      }
    },
    [db, dao],
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
        loadMoreResolved,
        createTicket,
        updateTicket,
      }}
    >
      {children}
    </TicketContext.Provider>
  );
};
