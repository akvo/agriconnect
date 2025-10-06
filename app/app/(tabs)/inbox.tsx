import React, { useMemo, useState, useCallback, useEffect } from "react";
import {
  StyleSheet,
  Text,
  View,
  FlatList,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import { useSQLiteContext } from "expo-sqlite";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";
import InboxTabs from "@/components/inbox/tabs-button";
import Search from "@/components/inbox/search";
import TicketItem from "@/components/inbox/ticket-item";
import { useAuth } from "@/contexts/AuthContext";
import { Ticket } from "@/database/dao/types/ticket";
import TicketSyncService from "@/services/ticketSync";

const Tabs = {
  PENDING: "open",
  RESPONDED: "resolved",
} as const;

const Inbox: React.FC = () => {
  const router = useRouter();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [activeTab, setActiveTab] = useState<(typeof Tabs)[keyof typeof Tabs]>(
    Tabs.PENDING,
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
  const db = useSQLiteContext();

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tickets.filter((t: Ticket) => {
      const isResolved = !!t.resolvedAt;
      if (activeTab === Tabs.PENDING && isResolved) return false;
      if (activeTab === Tabs.RESPONDED && !isResolved) return false;

      if (!q) return true;
      const inName = t.customer?.name.toString().includes(q);
      const inContent = (t.message?.body.toString() || "").includes(q);
      const inTicketId = t.ticketNumber.toLowerCase().includes(q);
      return inName || inContent || inTicketId;
    });
  }, [tickets, activeTab, query]);
  const { user } = useAuth();

  const onPressTicket = (ticket: Ticket) => {
    // Navigate to the chat screen, passing ticketNumber as query param
    router.push(
      `/chat?ticketNumber=${encodeURIComponent(ticket.ticketNumber)}`,
    );
  };

  const fetchTickets = useCallback(
    async (
      tab: (typeof Tabs)[keyof typeof Tabs],
      p: number,
      append: boolean = false,
      isRefreshing: boolean = false,
    ) => {
      // Prevent concurrent fetches
      if (isFetchingRef.current) return;

      if (!user?.accessToken) return;

      isFetchingRef.current = true;

      try {
        setError(null);
        if (isRefreshing) setRefreshing(true);
        else setLoading(true);

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
    if (page === 1) return;
    // Skip if refreshing
    if (refreshing) return;
    // Skip if there's an error
    if (error) return;

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
          if (loading || !hasMore) return;
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
