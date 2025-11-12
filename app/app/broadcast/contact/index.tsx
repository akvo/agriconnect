import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import Feather from "@expo/vector-icons/Feather";

import { api } from "@/services/api";
import { useAuth } from "@/contexts/AuthContext";
import { Customer, useBroadcast } from "@/contexts/BroadcastContext";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";

// Import broadcast components
import {
  CustomerCard,
  FilterModal,
  FilterPills,
  SearchFilterHeader,
  SelectAllHeader,
} from "@/components/broadcast";
import { useNetwork } from "@/contexts/NetworkContext";

// Constants
const PAGE_SIZE = 10;
const DEBOUNCE_DELAY = 300;

interface CustomerListResponse {
  customers: Customer[];
  total: number;
  page: number;
  size: number;
}

const BroadcastFarmerListTab = () => {
  const router = useRouter();
  const { user } = useAuth();
  const { cropTypes, selectedMembers, setSelectedMembers } = useBroadcast();
  const { isOnline } = useNetwork();
  const isAdmin = user?.userType === "admin";

  // State
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);

  // Filter state
  const [selectedCropTypes, setSelectedCropTypes] = useState<number[]>([]);
  const [selectedAgeGroups, setSelectedAgeGroups] = useState<string[]>([]);
  const [selectedAdminIds, setSelectedAdminIds] = useState<number[]>([]);
  const [showFilterModal, setShowFilterModal] = useState(false);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, DEBOUNCE_DELAY);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch customers
  const fetchCustomers = useCallback(
    async (currentPage: number, isLoadingMore: boolean = false) => {
      try {
        /**
         * Early return if offline
         */
        if (!isOnline) {
          return;
        }
        if (isLoadingMore) {
          setLoadingMore(true);
        } else {
          setLoading(true);
        }
        setError(null);

        const params: any = {
          page: currentPage,
          size: PAGE_SIZE,
        };

        if (debouncedSearch) {
          params.search = debouncedSearch;
        }

        if (selectedCropTypes.length > 0) {
          params.crop_types = selectedCropTypes;
        }

        if (selectedAgeGroups.length > 0) {
          params.age_groups = selectedAgeGroups;
        }

        // Only include administrative_id filter for admin users
        if (isAdmin && selectedAdminIds.length > 0) {
          params.administrative_id = selectedAdminIds;
        }

        const response: CustomerListResponse = await api.getCustomersList(
          user?.accessToken || "",
          params,
        );

        if (isLoadingMore) {
          // use the current customers array from context instead of an updater function
          setCustomers([...customers, ...response.customers]);
        } else {
          setCustomers(response.customers);
        }

        setHasMore(response.customers.length === PAGE_SIZE);

        if (selectedMembers.length) {
          setSelectedIds((prev) => {
            const newSet = new Set(prev);
            selectedMembers.forEach((member) => {
              newSet.add(member.customer_id);
            });
            return newSet;
          });
        }
      } catch (err) {
        console.error("Error fetching customers:", err);
        setError(
          err instanceof Error ? err.message : "Failed to fetch customers",
        );
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [
      isOnline,
      isAdmin,
      debouncedSearch,
      selectedCropTypes,
      selectedAgeGroups,
      selectedAdminIds,
      user?.accessToken,
      selectedMembers,
      customers,
      setCustomers,
    ],
  );

  // Reset and fetch on filter/search change
  useEffect(() => {
    setPage(1);
    setCustomers([]);
    setSelectedIds(new Set()); // Clear selections when filters change
    // setSelectedMembers([]); // Clear selected members in context
    fetchCustomers(1, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch, selectedCropTypes, selectedAgeGroups, selectedAdminIds]);

  // Load more handler
  const handleLoadMore = useCallback(() => {
    if (!loadingMore && !loading && hasMore) {
      const nextPage = page + 1;
      setPage(nextPage);
      fetchCustomers(nextPage, true);
    }
  }, [loadingMore, loading, hasMore, page, fetchCustomers]);

  // Selection handlers
  const toggleSelection = useCallback(
    (id: number) => {
      const newSet = new Set(selectedIds);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      setSelectedIds(newSet);
      setSelectedMembers(selectedMembers.filter((m) => m.customer_id !== id));
    },
    [selectedIds, selectedMembers, setSelectedMembers],
  );

  const toggleSelectAll = useCallback(() => {
    if (selectedIds.size === customers.length && customers.length > 0) {
      // Deselect all visible
      setSelectedIds(new Set());
    } else {
      // Select all visible
      const allVisibleIds = customers.map((c) => c.id);
      setSelectedIds(new Set(allVisibleIds));
    }
  }, [customers, selectedIds.size]);

  const isAllSelected =
    customers.length > 0 && selectedIds.size === customers.length;

  // Filter handlers
  const toggleCropType = useCallback(
    (cropTypeID: number) => {
      setSelectedCropTypes((cropTypeIds) => {
        const cropTypeObj = cropTypes.find((ct) => ct.id === cropTypeID);
        if (!cropTypeObj) {
          return cropTypeIds;
        }

        /**
         * Toggle multiple crop type selection
         */
        if (cropTypeIds.includes(cropTypeID)) {
          return cropTypeIds.filter((id) => id !== cropTypeID);
        } else {
          return [...cropTypeIds, cropTypeID];
        }
      });
    },
    [cropTypes],
  );

  const toggleAgeGroup = useCallback((ageGroup: string) => {
    setSelectedAgeGroups((prev) =>
      prev.includes(ageGroup)
        ? prev.filter((ag) => ag !== ageGroup)
        : [...prev, ageGroup],
    );
  }, []);

  const applyFilters = useCallback(() => {
    setShowFilterModal(false);
    // Filters will trigger useEffect to refetch
  }, []);

  const clearFilters = useCallback(() => {
    setSelectedCropTypes([]);
    setSelectedAgeGroups([]);
    setSelectedAdminIds([]);
  }, []);

  const hasActiveFilters =
    selectedCropTypes.length > 0 ||
    selectedAgeGroups.length > 0 ||
    selectedAdminIds.length > 0;

  // Navigation handler
  const handleNext = useCallback(() => {
    // Get selected customers from the full list
    const selectedCustomers = customers
      .map((c) => ({
        customer_id: c.id,
        phone_number: c.phone_number,
        full_name: c.full_name,
        crop_type: c.crop_type,
      }))
      .filter((c) => selectedIds.has(c.customer_id));

    // Update context with selected members
    // Note: crop_types and age_groups are now derived from actual members, not saved to group
    setSelectedIds(new Set()); // Clear local selections
    setSelectedMembers(selectedCustomers, () => {
      router.navigate("/broadcast/create");
    });
  }, [selectedIds, customers, setSelectedMembers, router]);

  // Render item
  const renderItem = useCallback(
    ({ item }: { item: Customer }) => {
      const isSelected = selectedIds.has(item.id);
      return (
        <CustomerCard
          customer={item}
          isSelected={isSelected}
          isAdmin={isAdmin}
          onToggle={toggleSelection}
        />
      );
    },
    [selectedIds, isAdmin, toggleSelection],
  );

  const keyExtractor = useCallback((item: Customer) => item.id.toString(), []);

  // List header with Select All
  const ListHeaderComponent = useMemo(
    () => (
      <SelectAllHeader
        isAllSelected={isAllSelected}
        onToggleAll={toggleSelectAll}
        totalCount={customers.length}
        selectedCount={selectedIds.size}
      />
    ),
    [isAllSelected, toggleSelectAll, selectedIds.size, customers.length],
  );

  // List footer
  const ListFooterComponent = useMemo(() => {
    if (loadingMore) {
      return (
        <View style={styles.footerLoader}>
          <ActivityIndicator size="small" color={themeColors["green-500"]} />
        </View>
      );
    }

    if (!hasMore && customers.length > 0) {
      return (
        <View style={styles.footerMessage}>
          <Text style={[typography.body3, { color: themeColors.dark4 }]}>
            You reached the end of the list
          </Text>
        </View>
      );
    }

    return null;
  }, [loadingMore, hasMore, customers.length]);

  // Empty component
  const ListEmptyComponent = useMemo(() => {
    if (loading) {
      return (
        <View style={styles.emptyContainer}>
          <ActivityIndicator size="large" color={themeColors["green-500"]} />
        </View>
      );
    }

    if (error) {
      return (
        <View style={styles.emptyContainer}>
          <Feather name="alert-circle" size={48} color={themeColors.error} />
          <Text
            style={[
              typography.body2,
              { color: themeColors.error, marginTop: 16 },
            ]}
          >
            {error}
          </Text>
          <TouchableOpacity
            style={styles.retryButton}
            onPress={() => fetchCustomers(1, false)}
          >
            <Text style={[typography.label2, { color: themeColors.white }]}>
              Retry
            </Text>
          </TouchableOpacity>
        </View>
      );
    }

    return (
      <View style={styles.emptyContainer}>
        <Feather name="inbox" size={48} color={themeColors.dark4} />
        <Text
          style={[
            typography.body2,
            { color: themeColors.dark4, marginTop: 16 },
          ]}
        >
          No customers found
        </Text>
      </View>
    );
  }, [loading, error, fetchCustomers]);

  const activeFiltersCount =
    selectedCropTypes.length +
    selectedAgeGroups.length +
    selectedAdminIds.length;

  return (
    <View style={styles.container}>
      {/* Search and Filter */}
      <View style={styles.header}>
        <SearchFilterHeader
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onFilterPress={() => setShowFilterModal(true)}
          hasActiveFilters={hasActiveFilters}
          activeFiltersCount={activeFiltersCount}
        />

        {/* Selected Filter Pills */}
        {hasActiveFilters && (
          <FilterPills
            selectedCropTypes={selectedCropTypes}
            selectedAgeGroups={selectedAgeGroups}
            selectedAdminIds={selectedAdminIds}
            cropTypes={cropTypes}
            onRemoveCropType={toggleCropType}
            onRemoveAgeGroup={toggleAgeGroup}
            onRemoveAdminId={(id) =>
              setSelectedAdminIds((prev) =>
                prev.filter((adminId) => adminId !== id),
              )
            }
            onClearAll={clearFilters}
          />
        )}
      </View>

      {/* Customer List */}
      <FlatList
        data={customers}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        ListHeaderComponent={customers.length > 0 ? ListHeaderComponent : null}
        ListFooterComponent={ListFooterComponent}
        ListEmptyComponent={ListEmptyComponent}
        onEndReached={handleLoadMore}
        onEndReachedThreshold={0.5}
        contentContainerStyle={styles.listContent}
        style={styles.list}
      />

      {/* Next Button */}
      <View style={styles.footer}>
        <TouchableOpacity
          style={[
            styles.nextButton,
            selectedIds.size === 0 && styles.nextButtonDisabled,
          ]}
          onPress={handleNext}
          disabled={selectedIds.size === 0 || !isOnline}
          activeOpacity={0.8}
        >
          <Text style={[typography.label1, { color: themeColors.white }]}>
            Next ({selectedIds.size})
          </Text>
          <Feather name="arrow-right" size={20} color={themeColors.white} />
        </TouchableOpacity>
      </View>

      {/* Filter Modal */}
      <FilterModal
        visible={showFilterModal}
        onClose={() => setShowFilterModal(false)}
        cropTypes={cropTypes}
        selectedCropTypes={selectedCropTypes}
        selectedAgeGroups={selectedAgeGroups}
        onToggleCropType={toggleCropType}
        onToggleAgeGroup={toggleAgeGroup}
        onApply={applyFilters}
        isAdmin={isAdmin}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: themeColors.background,
  },
  header: {
    width: "100%",
    padding: 16,
    backgroundColor: themeColors.white,
    borderBottomWidth: 1,
    borderBottomColor: themeColors.mutedBorder,
  },

  list: {
    flex: 1,
  },
  listContent: {
    flexGrow: 1,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 100,
  },

  footerLoader: {
    paddingVertical: 20,
    alignItems: "center",
  },
  footerMessage: {
    paddingVertical: 20,
    alignItems: "center",
  },
  emptyContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    minHeight: 400,
  },
  retryButton: {
    marginTop: 16,
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: themeColors["green-500"],
    borderRadius: 8,
  },
  footer: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 32,
    backgroundColor: themeColors.white,
    borderTopWidth: 1,
    borderTopColor: themeColors.mutedBorder,
  },
  nextButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: themeColors["green-500"],
    paddingVertical: 16,
    borderRadius: 12,
    gap: 8,
  },
  nextButtonDisabled: {
    backgroundColor: themeColors.dark4,
    opacity: 0.5,
  },
});

export default BroadcastFarmerListTab;
