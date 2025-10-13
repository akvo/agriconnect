import React, { useMemo, useState, useCallback, useEffect } from "react";
import {
  StyleSheet,
  Text,
  View,
  FlatList,
  ActivityIndicator,
} from "react-native";
import { useRouter, useLocalSearchParams } from "expo-router";
import { useDatabase } from "@/database/context";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";
import InboxTabs from "@/components/inbox/tabs-button";
import Search from "@/components/inbox/search";
import TicketItem from "@/components/inbox/ticket-item";
import { useAuth } from "@/contexts/AuthContext";
import { Ticket } from "@/database/dao/types/ticket";
import TicketSyncService from "@/services/ticketSync";
import { useTicket } from "@/contexts/TicketContext";
import {
  useWebSocket,
  MessageCreatedEvent,
  TicketResolvedEvent,
  TicketCreatedEvent,
} from "@/contexts/WebSocketContext";
import { DAOManager } from "@/database/dao";

const Tabs = {
  PENDING: "open",
  RESPONDED: "resolved",
} as const;

const Inbox: React.FC = () => {
  const { initTab } = useLocalSearchParams<{
    initTab?: (typeof Tabs)[keyof typeof Tabs];
  }>();
  const router = useRouter();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [activeTab, setActiveTab] = useState<(typeof Tabs)[keyof typeof Tabs]>(
    initTab || Tabs.PENDING,
  );
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 10; // default page size to request
  const endReachedTimeout = React.useRef<number | null>(null);
  const isFetchingRef = React.useRef(false); // prevent duplicate fetches
  const isInitialMount = React.useRef(true); // track initial mount
  const db = useDatabase();
  const { updateTicket } = useTicket();
  const { isConnected, onMessageCreated, onTicketResolved, onTicketCreated } =
    useWebSocket();
  const daoManager = useMemo(() => new DAOManager(db), [db]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tickets
      .filter((t: Ticket) => {
        const isResolved = !!t.resolvedAt;
        if (activeTab === Tabs.PENDING && isResolved) {
          return false;
        }
        if (activeTab === Tabs.RESPONDED && !isResolved) {
          return false;
        }

        if (!q) {
          return true;
        }
        const inName = t.customer?.name.toString().includes(q);
        const inContent = (t.message?.body.toString() || "").includes(q);
        const inTicketId = t.ticketNumber.toLowerCase().includes(q);
        return inName || inContent || inTicketId;
      })
      .sort((a: Ticket, b: Ticket) => {
        // Sort by unreadCount desc, then createdAt desc
        if ((b.unreadCount || 0) !== (a.unreadCount || 0)) {
          return (b.unreadCount || 0) - (a.unreadCount || 0);
        }
        // Sort by updatedAt desc if available, else createdAt desc
        const aTime = a.updatedAt
          ? new Date(a.updatedAt).getTime()
          : new Date(a.createdAt).getTime();
        const bTime = b.updatedAt
          ? new Date(b.updatedAt).getTime()
          : new Date(b.createdAt).getTime();
        return bTime - aTime;
      });
  }, [tickets, activeTab, query]);
  const { user } = useAuth();

  const onPressTicket = (ticket: Ticket) => {
    // update unreadCount
    if (ticket.unreadCount && ticket.unreadCount > 0) {
      const _unreadCount = 0;
      const updated = {
        ...ticket,
        unreadCount: _unreadCount,
      };
      updateTicket(ticket.id, { unreadCount: _unreadCount });
      // update local state immediately for responsiveness
      setTickets((prev: Ticket[]) =>
        prev.map((t: Ticket) => (t.id === ticket.id ? updated : t)),
      );
    }
    // Navigate to the chat screen, passing ticketNumber as query param
    router.push({
      pathname: "/chat",
      params: {
        ticketNumber: ticket.ticketNumber,
        name: ticket.customer?.name || "Chat",
        messageId: ticket.message?.id || undefined,
      },
    });
  };

  const fetchTickets = useCallback(
    async (
      tab: (typeof Tabs)[keyof typeof Tabs],
      p: number,
      append: boolean = false,
      isRefreshing: boolean = false,
    ) => {
      // Prevent concurrent fetches
      if (isFetchingRef.current) {
        return;
      }

      if (!user?.accessToken) {
        return;
      }

      isFetchingRef.current = true;

      try {
        setError(null);
        if (isRefreshing) {
          setRefreshing(true);
        } else {
          setLoading(true);
        }

        // Use TicketSyncService to fetch tickets (local-first approach)
        const syncResult = await TicketSyncService.getTickets(
          db,
          user.accessToken,
          tab,
          p,
          pageSize,
          user.id,
        );

        const fetched: Ticket[] = syncResult.tickets || [];
        const total: number = syncResult.total;
        const size: number = syncResult.size;
        const currentPage: number = syncResult.page;

        // Compute hasMore using total and size
        const totalPages = Math.ceil(total / size);
        setHasMore(currentPage < totalPages);

        setTickets((prev: Ticket[]) =>
          append ? [...prev, ...fetched] : fetched,
        );
      } catch (error) {
        console.error("Failed to fetch tickets:", error);
        setError((error as Error)?.message || "Failed to fetch tickets");
      } finally {
        setLoading(false);
        setRefreshing(false);
        isFetchingRef.current = false;
      }
    },
    [user?.accessToken, pageSize, db, user?.id],
  );

  // Handle real-time message_created events
  useEffect(() => {
    const unsubscribe = onMessageCreated(async (event: MessageCreatedEvent) => {
      console.log("[Inbox] Received message_created event:", event);

      try {
        // Find the ticket in local state
        const ticketIndex = tickets.findIndex(
          (t: Ticket) => t.id === event.ticket_id,
        );

        if (ticketIndex !== -1) {
          const ticket = tickets[ticketIndex];

          // Update ticket in SQLite database
          // Increment unread count and update last message
          const newUnreadCount = (ticket.unreadCount || 0) + 1;
          await daoManager.ticket.update(db, ticket.id, {
            unreadCount: newUnreadCount,
          });

          // Update local state immediately for instant UI update
          setTickets((prev: Ticket[]) =>
            prev.map((t: Ticket) =>
              t.id === event.ticket_id
                ? {
                    ...t,
                    unreadCount: newUnreadCount,
                    lastMessage: {
                      content: event.body,
                      timestamp: event.ts,
                    },
                    updatedAt: event.ts,
                  }
                : t,
            ),
          );

          console.log(
            `[Inbox] Updated ticket ${event.ticket_id} with new message`,
          );
        } else {
          // Ticket not in current list, might need to refresh
          console.log(
            `[Inbox] Ticket ${event.ticket_id} not found in current list`,
          );
          // Optionally fetch the ticket if it's a new one
          if (activeTab === Tabs.PENDING && page === 1) {
            // Refresh first page to include new ticket
            fetchTickets(activeTab, 1, false, false);
          }
        }
      } catch (error) {
        console.error("[Inbox] Error handling message_created event:", error);
      }
    });

    return unsubscribe;
  }, [
    onMessageCreated,
    tickets,
    db,
    daoManager,
    activeTab,
    page,
    fetchTickets,
  ]);

  // Handle real-time ticket_resolved events
  useEffect(() => {
    const unsubscribe = onTicketResolved(async (event: TicketResolvedEvent) => {
      console.log("[Inbox] Received ticket_resolved event:", event);

      try {
        // Find the ticket in local state
        const ticket = tickets.find((t: Ticket) => t.id === event.ticket_id);

        if (ticket) {
          // Update ticket in SQLite database
          await daoManager.ticket.update(db, ticket.id, {
            resolvedAt: event.resolved_at,
            status: "resolved",
          });

          // Update local state immediately
          if (activeTab === Tabs.PENDING) {
            // Remove from pending list
            setTickets((prev: Ticket[]) =>
              prev.filter((t: Ticket) => t.id !== event.ticket_id),
            );
            console.log(
              `[Inbox] Removed resolved ticket ${event.ticket_id} from pending list`,
            );
          } else {
            // Update in resolved list
            setTickets((prev: Ticket[]) =>
              prev.map((t: Ticket) =>
                t.id === event.ticket_id
                  ? {
                      ...t,
                      resolvedAt: event.resolved_at,
                      status: "resolved",
                      updatedAt: event.resolved_at,
                    }
                  : t,
              ),
            );
            console.log(
              `[Inbox] Updated ticket ${event.ticket_id} in resolved list`,
            );
          }
        } else {
          console.log(
            `[Inbox] Ticket ${event.ticket_id} not found in current list`,
          );
        }
      } catch (error) {
        console.error("[Inbox] Error handling ticket_resolved event:", error);
      }
    });

    return unsubscribe;
  }, [onTicketResolved, tickets, db, daoManager, activeTab]);

  // Handle real-time ticket_created events
  useEffect(() => {
    const unsubscribe = onTicketCreated(async (event: TicketCreatedEvent) => {
      console.log("[Inbox] Received ticket_created event:", event);

      try {
        // Only refresh if we're on the first page of pending tickets
        // to avoid disrupting pagination
        if (activeTab === Tabs.PENDING && page === 1) {
          console.log("[Inbox] Refreshing ticket list for new ticket");
          // Refetch tickets to include the new one
          await fetchTickets(activeTab, 1, false, false);
        }
      } catch (error) {
        console.error("[Inbox] Error handling ticket_created event:", error);
      }
    });

    return unsubscribe;
  }, [onTicketCreated, activeTab, page, fetchTickets]);

  // Reset list when tab changes
  useEffect(() => {
    // On initial mount, just fetch - don't reset
    if (isInitialMount.current) {
      isInitialMount.current = false;
      fetchTickets(activeTab, 1, false);
      return;
    }

    // On subsequent tab changes, reset everything
    setPage(1);
    setTickets([]);
    setHasMore(true);
    setError(null);
    // Fetch first page for new tab
    fetchTickets(activeTab, 1, false);
  }, [activeTab, fetchTickets]);

  // Fetch when page changes (but not on initial mount or tab change)
  useEffect(() => {
    // Skip if page is 1 (already handled by tab change effect)
    if (page === 1) {
      return;
    }
    // Skip if refreshing
    if (refreshing) {
      return;
    }
    // Skip if there's an error
    if (error) {
      return;
    }

    fetchTickets(activeTab, page, true);
  }, [page, activeTab, fetchTickets, refreshing, error]);

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      {error ? (
        <View style={{ alignItems: "center" }}>
          <Text style={[typography.body3, { color: themeColors.error }]}>
            {" "}
            {error}
          </Text>
          <Text
            onPress={() => {
              // retry
              setPage(1);
              setTickets([]);
              setHasMore(true);
              fetchTickets(activeTab, 1, false);
            }}
            style={[
              typography.body3,
              { color: themeColors.dark1, marginTop: 8 },
            ]}
          >
            Retry
          </Text>
        </View>
      ) : (
        <Text style={[typography.body3, { color: themeColors.dark3 }]}>
          No tickets available
        </Text>
      )}
    </View>
  );

  return (
    <View style={styles.container}>
      {/* Connection Status Indicator */}
      {!isConnected && (
        <View style={styles.connectionBanner}>
          <Text style={[typography.caption, { color: themeColors.error }]}>
            ⚠️ Reconnecting...
          </Text>
        </View>
      )}

      {/* Tabs */}
      <View style={styles.tabsContainer}>
        <InboxTabs
          activeTab={activeTab}
          onChange={(t: string) => setActiveTab(t as any)}
        />
      </View>

      {/* Search */}
      <Search value={query} onChange={setQuery} />

      {/* List */}
      <FlatList<Ticket>
        data={filtered}
        keyExtractor={(item: Ticket) => String(item.id)}
        renderItem={({ item }: { item: Ticket }) => (
          <TicketItem ticket={item} onPress={onPressTicket} />
        )}
        ListEmptyComponent={renderEmpty}
        contentContainerStyle={{ padding: 16, paddingBottom: 120 }}
        onEndReachedThreshold={0.5}
        onEndReached={() => {
          // debounce rapid calls
          if (loading || !hasMore) {
            return;
          }
          if (endReachedTimeout.current) {
            window.clearTimeout(endReachedTimeout.current);
          }
          // schedule page increment after 200ms; if another call comes in the window it'll reset
          endReachedTimeout.current = window.setTimeout(() => {
            setPage((prev: number) => prev + 1);
            endReachedTimeout.current = null;
          }, 200);
        }}
        refreshing={refreshing}
        onRefresh={() => {
          // pull-to-refresh: reset to first page and fetch
          setPage(1);
          setTickets([]);
          setHasMore(true);
          setError(null);
          fetchTickets(activeTab, 1, false, true);
        }}
        ListFooterComponent={() =>
          loading ? (
            <View style={styles.footer}>
              <ActivityIndicator size="small" color={themeColors.dark3} />
            </View>
          ) : null
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: themeColors.background,
  },
  connectionBanner: {
    backgroundColor: themeColors["green-50"],
    paddingVertical: 4,
    paddingHorizontal: 16,
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: themeColors["green-200"],
  },
  tabsContainer: {
    padding: 16,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingVertical: 32,
  },
  footer: {
    paddingVertical: 16,
    alignItems: "center",
  },
});

export default Inbox;
