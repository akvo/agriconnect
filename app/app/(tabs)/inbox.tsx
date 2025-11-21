import React, {
  useMemo,
  useState,
  useCallback,
  useEffect,
  useRef,
} from "react";
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
import { useNetwork } from "@/contexts/NetworkContext";
import { useTicket } from "@/contexts/TicketContext";
import { MESSAGE_CREATED, ticketEmitter } from "@/utils/ticketEvents";

const Tabs = {
  PENDING: "open",
  RESPONDED: "resolved",
} as const;

const Inbox: React.FC = () => {
  const { initTab } = useLocalSearchParams<{
    initTab?: (typeof Tabs)[keyof typeof Tabs];
  }>();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<(typeof Tabs)[keyof typeof Tabs]>(
    initTab || Tabs.PENDING,
  );
  const [query, setQuery] = useState("");

  // ✅ FIX: Separate page state per tab (not shared)
  const [pageState, setPageState] = useState({ open: 1, resolved: 1 });
  const page = pageState[activeTab];

  const [loading, setLoading] = useState(false); // Changed to false - use cache first
  const [refreshing, setRefreshing] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 10; // default page size to request
  const endReachedTimeout = useRef<number | null>(null);
  const isFetchingRef = useRef(false); // prevent duplicate fetches
  const isInitialMount = useRef(true); // track initial mount
  const hasLoadedTab = useRef({ open: false, resolved: false }); // track which tabs have been loaded
  const db = useDatabase();
  const { isConnected, onMessageCreated, onTicketResolved } = useWebSocket();
  const { isOnline } = useNetwork();
  const { tickets, setTickets, getTicketsByStatus, loadMoreResolved } =
    useTicket();
  const daoManager = useMemo(() => new DAOManager(db), [db]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();

    // ✅ Get tickets for current tab from TicketContext (in-memory filter)
    const tabTickets = getTicketsByStatus(activeTab);

    // Apply search filter
    const searchFiltered = !q
      ? tabTickets
      : tabTickets.filter((t: Ticket) => {
          const inName = t.customer?.name?.toString().toLowerCase().includes(q);
          const inContent = (t.message?.body.toString() || "")
            .toLowerCase()
            .includes(q);
          const inTicketId = t.ticketNumber.toLowerCase().includes(q);
          return inName || inContent || inTicketId;
        });

    // Sort: unreadCount DESC, updatedAt DESC, createdAt DESC
    return searchFiltered.sort((a: Ticket, b: Ticket) => {
      // Sort by unreadCount desc first
      if ((b.unreadCount || 0) !== (a.unreadCount || 0)) {
        return (b.unreadCount || 0) - (a.unreadCount || 0);
      }
      // Then by updatedAt desc
      if (a?.updatedAt && b?.updatedAt && activeTab === Tabs.PENDING) {
        return (
          new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        );
      }
      // Finally by id desc as fallback
      return b.id - a.id;
    });
  }, [activeTab, query, getTicketsByStatus]);
  const { user } = useAuth();

  const onPressTicket = async (ticket: Ticket) => {
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
      // update unreadCount in database
      await daoManager.ticket.update(db, ticket.id, {
        unreadCount: _unreadCount,
      });
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

      isFetchingRef.current = true;

      try {
        setError(null);
        if (isRefreshing) {
          setRefreshing(true);
        }
        if (!append && p === 1) {
          setLoading(true);
        }

        console.log(
          `[Inbox] Fetching ${tab} tickets from API (page ${p}, append: ${append})`,
        );

        // Use TicketSyncService to fetch from API and store to SQLite
        const syncResult = await TicketSyncService.getTickets(
          db,
          tab,
          p,
          pageSize,
          user?.id,
        );

        const total: number = syncResult.total;
        const size: number = syncResult.size;
        const currentPage: number = syncResult.page;

        // Compute hasMore using total and size
        const totalPages = Math.ceil(total / size);
        setHasMore(currentPage < totalPages);

        // ✅ CRITICAL: Reload ALL tickets from SQLite into TicketContext
        const allTickets = await daoManager.ticket.findAll(db);
        setTickets(allTickets);

        // ✅ Mark this tab as loaded (even if empty)
        hasLoadedTab.current[tab] = true;

        console.log(
          `[Inbox] Loaded ${syncResult.tickets.length} tickets from ${syncResult.source}`,
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
    [user?.id, db, setTickets, daoManager],
  );

  // Shared message handler for both WebSocket and ticketEmitter
  const handleMessageCreated = useCallback(
    async (event: MessageCreatedEvent) => {
      // Find the ticket in current state
      const ticketIndex = tickets.findIndex(
        (t: Ticket) => t.id === event.ticket_id,
      );

      if (ticketIndex !== -1) {
        // ✅ FIX: Use functional setState and calculate newUnreadCount from fresh state
        let newUnreadCount = 0;
        let ticketId = 0;

        setTickets((prevTickets: Ticket[]) => {
          const ticket = prevTickets[ticketIndex];

          // Check if this message is already the last message (prevent duplicate increments)
          if (ticket.lastMessageId === event.message_id) {
            console.log(
              `[Inbox] Message ${event.message_id} already processed for ticket ${event.ticket_id}, skipping duplicate`,
            );
            return prevTickets;
          }

          // ✅ Calculate newUnreadCount from FRESH state (not stale closure)
          newUnreadCount = (ticket.unreadCount || 0) + 1;
          ticketId = ticket.id;

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

        // ✅ FIX: Use the SAME calculated value for DB update (not recalculated from stale state)
        (async () => {
          try {
            await daoManager.ticket.update(db, ticketId, {
              unreadCount: newUnreadCount, // ✅ Use same value as state update
            });

            // Upsert message and update lastMessageId
            const lastMessage = await daoManager.message.findById(
              db,
              event.message_id,
            );
            if (lastMessage) {
              await daoManager.ticket.update(db, ticketId, {
                lastMessageId: lastMessage.id,
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
        // ✅ FIX: New ticket should have unreadCount: 1 (initial message is unread)
        console.log("[Inbox] Creating optimistic ticket for new ticket", event);
        setTickets((prevTickets: Ticket[]) => {
          // Check if ticket already exists (prevent duplicates from multiple event sources)
          const alreadyExists = prevTickets.some(
            (t: Ticket) => t.id === event.ticket_id,
          );
          if (alreadyExists) {
            console.log(
              "[Inbox] Ticket already exists in list, skipping duplicate",
            );
            return prevTickets;
          }

          return [
            {
              id: event.ticket_id,
              ticketNumber: event.ticket_number || `TICKET-${event.ticket_id}`,
              customerId: event.customer_id || 0,
              messageId: event.message_id,
              lastMessageId: event.message_id, // ✅ Set lastMessageId for duplicate check
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
              unreadCount: 1, // ✅ FIX: Changed from 0 to 1 (initial message is unread)
              createdAt: event.ts,
              updatedAt: event.ts,
            } as Ticket,
            ...prevTickets,
          ];
        });
      }
    },
    [tickets, setTickets, daoManager, db],
  );

  // Subscribe to WebSocket message_created events
  useEffect(() => {
    const unsubscribe = onMessageCreated(handleMessageCreated);
    return unsubscribe;
  }, [onMessageCreated, handleMessageCreated]);

  // Subscribe to ticketEmitter (fallback for push notifications)
  useEffect(() => {
    const handleTicketEmitterMessage = async (data: any) => {
      console.log("[Inbox] ticketEmitter MESSAGE_CREATED received:", data);

      // Convert push notification data to MessageCreatedEvent format
      const event: MessageCreatedEvent = {
        ticket_id: parseInt(data.ticketId),
        message_id: parseInt(data.messageId),
        phone_number: data.phone_number || "",
        body: data.body || "",
        from_source: 1, // CUSTOMER
        ts: new Date().toISOString(),
        ticket_number: data.ticketNumber,
        sender_name: data.name,
        customer_id: data.customer_id,
        customer_name: data.name,
      };

      // Call the same handler as WebSocket
      await handleMessageCreated(event);
    };

    ticketEmitter.on(MESSAGE_CREATED, handleTicketEmitterMessage);

    return () => {
      ticketEmitter.off(MESSAGE_CREATED, handleTicketEmitterMessage);
    };
  }, [handleMessageCreated]);

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
  }, [onTicketResolved, tickets, db, daoManager, activeTab, setTickets]);

  // ✅ CORRECT: Tab switching uses cache, only depend on activeTab
  useEffect(() => {
    const isInitial = isInitialMount.current;

    if (isInitial) {
      isInitialMount.current = false;
    }

    // ✅ Check if we've already loaded data for this tab (even if empty)
    if (hasLoadedTab.current[activeTab]) {
      console.log(
        `[Inbox] Tab ${activeTab} already loaded, using cache - NO API CALL`,
      );
      setLoading(false);
      return;
    }

    // ✅ Only fetch if this tab has never been loaded
    console.log(
      `[Inbox] First time loading ${activeTab} tab, fetching from API...`,
    );
    setPageState((prev) => ({ ...prev, [activeTab]: 1 }));
    setHasMore(true);
    setError(null);
    fetchTickets(activeTab, 1, false);
  }, [activeTab, fetchTickets]); // ✅ Only activeTab dependency

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
              setPageState((prev) => ({ ...prev, [activeTab]: 1 }));
              setHasMore(true);
              setError(null);
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
      {isOnline && !isConnected && tickets.length > 0 && (
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
          if (loading || !hasMore || isFetchingRef.current) {
            return;
          }
          if (endReachedTimeout.current) {
            window.clearTimeout(endReachedTimeout.current);
          }
          // schedule page increment after 200ms; if another call comes in the window it'll reset
          endReachedTimeout.current = window.setTimeout(async () => {
            // Cache-first pagination for resolved tab
            if (activeTab === Tabs.RESPONDED) {
              // Try loading more resolved tickets from cache first (no API call)
              const resolvedTickets = getTicketsByStatus(Tabs.RESPONDED);
              const hasMoreInCache = await loadMoreResolved(
                resolvedTickets.length,
              );

              if (!hasMoreInCache) {
                // No more in cache, fetch from API
                console.log(
                  `[Inbox] Cache exhausted, fetching from API (page ${page + 1})`,
                );
                const nextPage = page + 1;
                setPageState((prev) => ({ ...prev, [activeTab]: nextPage }));
                fetchTickets(activeTab, nextPage, true);
              }
            } else {
              // Open tab: Fetch from API (all open tickets already in cache)
              const nextPage = page + 1;
              console.log(`[Inbox] Loading next page: ${nextPage}`);
              setPageState((prev) => ({ ...prev, [activeTab]: nextPage }));
              fetchTickets(activeTab, nextPage, true);
            }
            endReachedTimeout.current = null;
          }, 200);
        }}
        refreshing={refreshing}
        onRefresh={() => {
          if (!isOnline) {
            console.log(`[Inbox] Offline - cannot refresh ${activeTab} tab`);
            return;
          }
          // pull-to-refresh: reset to first page and fetch
          console.log(`[Inbox] Pull-to-refresh for ${activeTab} tab`);
          hasLoadedTab.current[activeTab] = false; // Reset loaded flag to allow refresh
          setPageState((prev) => ({ ...prev, [activeTab]: 1 }));
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
