import React, { useMemo, useState, useCallback, useEffect } from "react";
import {
  StyleSheet,
  Text,
  View,
  FlatList,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";
import InboxTabs from "@/components/inbox/tabs-button";
import Search from "@/components/inbox/search";
import TicketItem, {
  Ticket as TicketType,
} from "@/components/inbox/ticket-item";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/services/api";

type Ticket = TicketType;

const Tabs = {
  PENDING: "open",
  RESPONDED: "resolved",
} as const;

const Inbox: React.FC = () => {
  const router = useRouter();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [activeTab, setActiveTab] = useState<(typeof Tabs)[keyof typeof Tabs]>(
    Tabs.PENDING
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

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tickets.filter((t: Ticket) => {
      const isResolved = !!t.resolved_at;
      if (activeTab === Tabs.PENDING && isResolved) return false;
      if (activeTab === Tabs.RESPONDED && !isResolved) return false;

      if (!q) return true;
      const inName = t.customer.name.toLowerCase().includes(q);
      const inContent = (t.message?.body || "").toLowerCase().includes(q);
      const inTicketId = t.ticket_number.toLowerCase().includes(q);
      return inName || inContent || inTicketId;
    });
  }, [tickets, activeTab, query]);
  const { user } = useAuth();

  const onPressTicket = (ticket: Ticket) => {
    // Navigate to the chat screen, passing ticket_number as query param
    router.push(
      `/chat?ticketNumber=${encodeURIComponent(ticket.ticket_number)}`
    );
  };

  const fetchTickets = useCallback(
    async (
      tab: (typeof Tabs)[keyof typeof Tabs],
      p: number,
      append: boolean = false,
      isRefreshing: boolean = false
    ) => {
      // Prevent concurrent fetches
      if (isFetchingRef.current) return;

      if (!user?.accessToken) return;

      isFetchingRef.current = true;

      try {
        setError(null);
        if (isRefreshing) setRefreshing(true);
        else setLoading(true);

        const apiData = await api.getTickets(
          user.accessToken,
          tab,
          p,
          pageSize
        );
        // API response shape: { tickets, total, page, size }
        const fetched: Ticket[] = apiData?.tickets || [];
        const total: number | undefined = apiData?.total;
        const size: number | undefined = apiData?.size || pageSize;
        const currentPage: number | undefined = apiData?.page || p;

        // if API provides total/size, compute hasMore using pages
        if (typeof total === "number" && typeof size === "number") {
          const totalPages = Math.ceil(total / size);
          setHasMore((currentPage ?? p) < totalPages);
        } else {
          setHasMore(fetched.length > 0);
        }

        setTickets((prev: Ticket[]) =>
          append ? [...prev, ...fetched] : fetched
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
    [user?.accessToken, pageSize]
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

    fetchTickets(activeTab, page, true);
  }, [page, activeTab, fetchTickets, refreshing]);

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
