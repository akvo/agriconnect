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
import Search from "@/components/search";
import TicketItem from "@/components/inbox/ticket-item";
import { useAuth } from "@/contexts/AuthContext";
import { Ticket } from "@/database/dao/types/ticket";
import TicketSyncService from "@/services/ticketSync";
import {
  useWebSocket,
  MessageCreatedEvent,
  TicketResolvedEvent,
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
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 10; // default page size to request
  const endReachedTimeout = React.useRef<number | null>(null);
  const isFetchingRef = React.useRef(false); // prevent duplicate fetches
  const isInitialMount = React.useRef(true); // track initial mount
  const db = useDatabase();
  const { isConnected, onMessageCreated, onTicketResolved } = useWebSocket();
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
        const inName = t.customer?.name?.toString().includes(q);
        const inContent = (t.message?.body.toString() || "").includes(q);
        const inTicketId = t.ticketNumber.toLowerCase().includes(q);
        return inName || inContent || inTicketId;
      })
      .sort((a: Ticket, b: Ticket) => {
        // Sort by unreadCount desc, then createdAt desc
        if ((b.unreadCount || 0) !== (a.unreadCount || 0)) {
          return (b.unreadCount || 0) - (a.unreadCount || 0);
        }
        // Then by updatedAt or createdAt desc
        const aTime = a.updatedAt
          ? new Date(a.updatedAt).getTime()
          : new Date(a.createdAt).getTime();
        const bTime = b.updatedAt
          ? new Date(b.updatedAt).getTime()
          : new Date(b.createdAt).getTime();
        return aTime - bTime;
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
      // update local state immediately for responsiveness
      setTickets((prev: Ticket[]) =>
        prev.map((t: Ticket) => (t.id === ticket.id ? updated : t)),
      );
    }
    // Navigate to the chat screen, passing ticketNumber as query param
    const chatName =
      ticket.customer?.name?.trim().length === 0
        ? ticket.customer?.phoneNumber
        : ticket.customer?.name || "Chat";
    router.push({
      pathname: "/chat/[ticketId]",
      params: {
        ticketId: ticket.id,
        ticketNumber: ticket.ticketNumber,
        name: chatName,
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
        }
        if (!append) {
          // Initial load or tab change - show loading
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

      // Find the ticket in current state
      const ticketIndex = tickets.findIndex(
        (t: Ticket) => t.id === event.ticket_id,
      );

      if (ticketIndex !== -1) {
        setTickets((prevTickets: Ticket[]) => {
          const ticket = prevTickets[ticketIndex];
          const newUnreadCount = (ticket.unreadCount || 0) + 1;

          // Update database asynchronously (don't block UI)
          return prevTickets.map((t: Ticket) =>
            t.id === event.ticket_id
              ? {
                  ...t,
                  unreadCount: newUnreadCount,
                  lastMessageId: event.message_id,
                  lastMessage: {
                    body: event.body,
                    timestamp: event.ts,
                  },
                  updatedAt: event.ts,
                }
              : t,
          );
        });

        (async () => {
          try {
            const ticket = tickets[ticketIndex];
            await daoManager.ticket.update(db, ticket.id, {
              unreadCount: (ticket.unreadCount || 0) + 1,
            });

            // Upsert message and update lastMessageId
            const lastMessage = await daoManager.message.findById(
              db,
              event.message_id,
            );
            if (lastMessage) {
              await daoManager.ticket.update(db, ticket.id, {
                lastMessageId: lastMessage.id,
              });
            } else {
              await daoManager.message.upsert(db, {
                id: event.message_id,
                from_source: event.from_source,
                message_sid: `MSG_${event.message_id}`,
                customer_id: event.customer_id || ticket.customer?.id || 0,
                user_id: null,
                body: event.body,
                createdAt: event.ts,
              });
              await daoManager.ticket.update(db, ticket.id, {
                lastMessageId: event.message_id,
              });
            }
          } catch (error) {
            console.error(
              "[Inbox] Error updating ticket/message in DB:",
              error,
            );
          }
        })();
        return;
      } else {
        // Ticket not found in current list - create optimistic ticket
        // Only add if it belongs to the current tab
        const isNewTicket = true; // New tickets are always "open"
        const shouldAdd = activeTab === Tabs.PENDING && isNewTicket;

        if (shouldAdd) {
          console.log("[Inbox] Creating optimistic ticket for new ticket");
          setTickets((prevTickets) => [
            {
              id: event.ticket_id,
              ticketNumber: event.ticket_number || `TICKET-${event.ticket_id}`,
              customerId: event.customer_id || 0,
              messageId: event.message_id,
              status: "open",
              resolvedAt: null,
              resolvedBy: null,
              resolver: null, // No resolver yet for new tickets
              customer: {
                id: event.customer_id || 0,
                name: event.customer_name || event.phone_number,
                phoneNumber: event.phone_number,
              },
              message: {
                id: event.message_id,
                body: event.body,
                timestamp: event.ts,
              },
              lastMessage: {
                body: event.body,
                timestamp: event.ts,
              },
              unreadCount: 1,
              createdAt: event.ts,
              updatedAt: event.ts,
            } as Ticket,
            ...prevTickets,
          ]);
        } else {
          console.log("[Inbox] Ticket belongs to different tab, skipping");
        }

        // Also update DB asynchronously
        (async () => {
          try {
            // Upsert message
            await daoManager.message.upsert(db, {
              id: event.message_id,
              from_source: event.from_source,
              message_sid: `MSG_${event.message_id}`,
              customer_id: event.customer_id || 0,
              user_id: null,
              body: event.body,
              createdAt: event.ts,
            });

            // Create ticket entry
            await daoManager.ticket.upsert(db, {
              id: event.ticket_id,
              ticketNumber: event.ticket_number || `TICKET-${event.ticket_id}`,
              customerId: event.customer_id || 0,
              messageId: event.message_id,
              lastMessageId: event.message_id,
              status: "open",
              createdAt: event.ts,
              updatedAt: event.ts,
              unreadCount: 1,
            });
          } catch (error) {
            console.error(
              "[Inbox] Error creating optimistic ticket/message in DB:",
              error,
            );
          }
        })();
      }
    });

    return unsubscribe;
  }, [onMessageCreated, db, daoManager, activeTab, user, tickets]);

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
      {error && (
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
      )}
      {!loading && (
        <Text style={[typography.body3, { color: themeColors.dark3 }]}>
          No tickets available
        </Text>
      )}
    </View>
  );

  return (
    <View style={styles.container}>
      {/**
       * Connection Status Banner
       * Reconnecting when WebSocket is disconnected and there are tickets
       */}
      {!isConnected && tickets.length > 0 && (
        <View style={styles.connectionBanner}>
          <Text style={[typography.caption1, { color: themeColors.error }]}>
            ⚠️ Reconnecting...
          </Text>
        </View>
      )}

      {/* Tabs */}
      <View style={styles.tabsContainer}>
        <InboxTabs
          activeTab={activeTab}
          onChange={(t: string) => {
            setActiveTab(t as any);
            setLoading(true);
          }}
        />
      </View>

      {/* Search */}
      <View style={{ paddingHorizontal: 16 }}>
        <Search value={query} onChange={setQuery} />
      </View>

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
