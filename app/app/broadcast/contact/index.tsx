import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
} from "react-native";
import { useRouter } from "expo-router";
import Feather from "@expo/vector-icons/Feather";
import { Checkbox } from "expo-checkbox";

import Search from "@/components/search";
import Avatar from "@/components/avatar";
import { api } from "@/services/api";
import { useAuth } from "@/contexts/AuthContext";
import { useBroadcast } from "@/contexts/BroadcastContext";
import { AGE_GROUPS } from "@/constants/customer";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";
import { initialsFromName } from "@/utils/string";

// Constants
const PAGE_SIZE = 10;
const DEBOUNCE_DELAY = 300;

// Types
interface CropType {
  id: number;
  name: string;
}
interface Customer {
  id: number;
  full_name: string | null;
  phone_number: string;
  language: string;
  age_group: string | null;
  administrative: {
    id: number | null;
    name: string | null;
    path: string | null;
  };
  crop_type: CropType | null;
}

interface CustomerListResponse {
  customers: Customer[];
  total: number;
  page: number;
  size: number;
}

// Helper functions
const capitalizeFirstLetter = (str: string | null): string => {
  if (!str) {
    return "";
  }
  return str.charAt(0).toUpperCase() + str.slice(1).replace("_", " ");
};

const BroadcastFarmerListTab = () => {
  const router = useRouter();
  const { user } = useAuth();
  const { setSelectedMembers } = useBroadcast();
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
  const [cropTypes, setCropTypes] = useState<CropType[]>([]);
  const [selectedCropTypes, setSelectedCropTypes] = useState<number[]>([]);
  const [selectedAgeGroups, setSelectedAgeGroups] = useState<string[]>([]);
  const [selectedAdminIds, setSelectedAdminIds] = useState<number[]>([]);
  const [showFilterModal, setShowFilterModal] = useState(false);

  // Fetch crop types on mount
  const fetchCropTypes = useCallback(async () => {
    try {
      const response = await api.getCropTypes();
      // API returns array directly, not wrapped in object
      setCropTypes(response);
    } catch (err) {
      console.error("Error fetching crop types:", err);
    }
  }, []);

  useEffect(() => {
    fetchCropTypes();
  }, [fetchCropTypes]);

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

        const response: CustomerListResponse =
          await api.getCustomersList(params);

        if (isLoadingMore) {
          setCustomers((prev) => [...prev, ...response.customers]);
        } else {
          setCustomers(response.customers);
        }

        setHasMore(response.customers.length === PAGE_SIZE);
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
      debouncedSearch,
      selectedCropTypes,
      selectedAgeGroups,
      selectedAdminIds,
      isAdmin,
    ],
  );

  // Reset and fetch on filter/search change
  useEffect(() => {
    setPage(1);
    setCustomers([]);
    setSelectedIds(new Set()); // Clear selections when filters change
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
  const toggleSelection = useCallback((id: number) => {
    setSelectedIds((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  }, []);

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
         * Set single crop type selection
         */
        return cropTypeIds.includes(cropTypeID) ? [] : [cropTypeID];
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
    const selectedCustomers = customers.filter((c) => selectedIds.has(c.id));

    // Update context with selected members and navigate after state is committed
    setSelectedMembers(selectedCustomers, () => {
      router.push("/broadcast/create");
    });
  }, [selectedIds, customers, setSelectedMembers, router]);

  // Render item
  const renderItem = useCallback(
    ({ item }: { item: Customer }) => {
      const isSelected = selectedIds.has(item.id);
      const displayName = item.full_name || item.phone_number;
      const initials = initialsFromName(displayName);

      return (
        <TouchableOpacity
          style={[
            styles.customerCard,
            isSelected && styles.customerCardSelected,
          ]}
          onPress={() => toggleSelection(item.id)}
          activeOpacity={0.7}
        >
          <View style={styles.customerBody}>
            <Checkbox
              value={isSelected}
              onValueChange={() => toggleSelection(item.id)}
              color={isSelected ? themeColors["green-500"] : undefined}
              style={styles.checkbox}
            />
            <View style={styles.avatarContainer}>
              <Avatar initials={initials} size={48} />
            </View>
            <View style={styles.customerInfo}>
              <Text
                style={[
                  typography.label1,
                  typography.bold,
                  { color: themeColors.textPrimary },
                ]}
                numberOfLines={1}
              >
                {displayName}
              </Text>
              {item.administrative?.path && isAdmin && (
                <Text
                  style={[
                    typography.body3,
                    { color: themeColors.textSecondary, marginBottom: 8 },
                  ]}
                >
                  {item.administrative.path}
                </Text>
              )}

              <Text style={[typography.body4, { color: themeColors.dark4 }]}>
                {item?.crop_type?.name
                  ? capitalizeFirstLetter(item.crop_type.name)
                  : item.phone_number}
              </Text>
            </View>
          </View>
        </TouchableOpacity>
      );
    },
    [selectedIds, isAdmin, toggleSelection],
  );

  const keyExtractor = useCallback((item: Customer) => item.id.toString(), []);

  // List header with Select All
  const ListHeaderComponent = useMemo(
    () => (
      <View style={styles.listHeader}>
        <TouchableOpacity style={styles.selectAllRow} onPress={toggleSelectAll}>
          <Checkbox
            value={isAllSelected}
            onValueChange={toggleSelectAll}
            color={isAllSelected ? themeColors["green-500"] : undefined}
            style={styles.checkbox}
          />
          <Text
            style={[
              typography.label2,
              { color: themeColors.textPrimary, marginLeft: 8 },
            ]}
          >
            Select All ({customers.length} visible)
          </Text>
        </TouchableOpacity>
        {selectedIds.size > 0 && (
          <Text
            style={[
              typography.body3,
              { color: themeColors["green-500"], marginTop: 8 },
            ]}
          >
            {selectedIds.size} customer(s) selected
          </Text>
        )}
      </View>
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

  const ListSelectedCropTypes = useMemo(() => {
    return cropTypes.filter((cropType) =>
      selectedCropTypes.includes(cropType.id),
    );
  }, [selectedCropTypes, cropTypes]);

  return (
    <View style={styles.container}>
      {/* Search and Filter */}
      <View style={styles.header}>
        <View style={styles.headerRow}>
          <View style={styles.searchWrapper}>
            <Search value={searchQuery} onChange={setSearchQuery} />
          </View>
          <View style={styles.filterWrapper}>
            <TouchableOpacity
              style={[
                styles.filterButton,
                hasActiveFilters && styles.filterButtonActive,
              ]}
              onPress={() => setShowFilterModal(true)}
            >
              <Feather
                name="sliders"
                size={24}
                color={
                  hasActiveFilters
                    ? themeColors.white
                    : themeColors["green-500"]
                }
              />
              {hasActiveFilters && (
                <Text style={[styles.filterBadge]}>
                  {selectedCropTypes.length +
                    selectedAgeGroups.length +
                    selectedAdminIds.length}
                </Text>
              )}
            </TouchableOpacity>
          </View>
        </View>

        {/* Selected Filter Pills */}
        {hasActiveFilters && (
          <View style={styles.filterPillsContainer}>
            <View style={styles.filterPillsRow}>
              {/* Crop Type Pills */}
              {ListSelectedCropTypes.map((cropType) => (
                <TouchableOpacity
                  key={`crop-${cropType.id}`}
                  style={styles.filterPill}
                  onPress={() => toggleCropType(cropType.id)}
                  testID={`selected-filter-pill-crop-${cropType.id}`}
                  accessibilityLabel={`Remove ${cropType.name} filter`}
                  accessibilityRole="button"
                >
                  <Text
                    style={[typography.body4, { color: themeColors.dark4 }]}
                  >
                    {capitalizeFirstLetter(cropType.name)}
                  </Text>
                  <Feather
                    name="x"
                    size={14}
                    color={themeColors.dark4}
                    style={{ marginLeft: 4 }}
                  />
                </TouchableOpacity>
              ))}

              {/* Age Group Pills */}
              {selectedAgeGroups.map((ageGroup) => (
                <TouchableOpacity
                  key={`age-${ageGroup}`}
                  style={styles.filterPill}
                  onPress={() => toggleAgeGroup(ageGroup)}
                  testID={`selected-filter-pill-age-${ageGroup}`}
                  accessibilityLabel={`Remove ${ageGroup} filter`}
                  accessibilityRole="button"
                >
                  <Text
                    style={[typography.body4, { color: themeColors.dark4 }]}
                  >
                    {ageGroup}
                  </Text>
                  <Feather
                    name="x"
                    size={14}
                    color={themeColors.dark4}
                    style={{ marginLeft: 4 }}
                  />
                </TouchableOpacity>
              ))}

              {/* Administrative Area Pills */}
              {selectedAdminIds.map((adminId) => (
                <TouchableOpacity
                  key={`admin-${adminId}`}
                  style={styles.filterPill}
                  onPress={() =>
                    setSelectedAdminIds((prev) =>
                      prev.filter((id) => id !== adminId),
                    )
                  }
                  testID={`selected-filter-pill-admin-${adminId}`}
                  accessibilityLabel={`Remove Area ${adminId} filter`}
                  accessibilityRole="button"
                >
                  <Text
                    style={[typography.body4, { color: themeColors.dark4 }]}
                  >
                    Area {adminId}
                  </Text>
                  <Feather
                    name="x"
                    size={14}
                    color={themeColors.dark4}
                    style={{ marginLeft: 4 }}
                  />
                </TouchableOpacity>
              ))}
            </View>

            {/* Clear All Button */}
            <TouchableOpacity
              style={styles.clearAllButton}
              onPress={clearFilters}
              testID="clear-filters-button"
              accessibilityLabel="Clear all filters"
              accessibilityRole="button"
            >
              <Text style={[typography.label3, { color: themeColors.error }]}>
                Clear
              </Text>
            </TouchableOpacity>
          </View>
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
          disabled={selectedIds.size === 0}
          activeOpacity={0.8}
        >
          <Text style={[typography.label1, { color: themeColors.white }]}>
            Next ({selectedIds.size})
          </Text>
          <Feather name="arrow-right" size={20} color={themeColors.white} />
        </TouchableOpacity>
      </View>

      {/* Filter Modal */}
      <Modal
        visible={showFilterModal}
        animationType="slide"
        transparent
        onRequestClose={() => setShowFilterModal(false)}
      >
        <Pressable
          style={styles.modalOverlay}
          onPress={() => setShowFilterModal(false)}
        >
          <Pressable
            style={styles.modalContent}
            onPress={(e) => e.stopPropagation()}
          >
            <View style={styles.modalHeader}>
              <Text
                style={[
                  typography.heading5,
                  { color: themeColors.textPrimary },
                ]}
              >
                Filter Customers
              </Text>
              <TouchableOpacity onPress={() => setShowFilterModal(false)}>
                <Feather name="x" size={24} color={themeColors.dark4} />
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.modalBody}>
              {/* Crop Types */}
              <View style={styles.filterSection}>
                <Text
                  style={[
                    typography.label1,
                    { color: themeColors.textPrimary, marginBottom: 12 },
                  ]}
                >
                  Crop Types
                </Text>
                <View style={styles.filterPillsRow}>
                  {cropTypes.map((cropType) => (
                    <TouchableOpacity
                      key={cropType.id}
                      style={[
                        styles.filterPill,
                        selectedCropTypes.includes(cropType.id) &&
                          styles.filterPillActive,
                      ]}
                      onPress={() => toggleCropType(cropType.id)}
                    >
                      <Text
                        style={[
                          typography.body2,
                          {
                            color: selectedCropTypes.includes(cropType.id)
                              ? themeColors.white
                              : themeColors.textPrimary,
                          },
                        ]}
                      >
                        {capitalizeFirstLetter(cropType.name)}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>

              {/* Age Groups */}
              <View style={styles.filterSection}>
                <Text
                  style={[
                    typography.label1,
                    { color: themeColors.textPrimary, marginBottom: 12 },
                  ]}
                >
                  Age Groups
                </Text>
                {AGE_GROUPS.map((ageGroup) => (
                  <TouchableOpacity
                    key={ageGroup}
                    style={styles.checkboxRow}
                    onPress={() => toggleAgeGroup(ageGroup)}
                  >
                    <Checkbox
                      value={selectedAgeGroups.includes(ageGroup)}
                      onValueChange={() => toggleAgeGroup(ageGroup)}
                      color={
                        selectedAgeGroups.includes(ageGroup)
                          ? themeColors["green-500"]
                          : undefined
                      }
                    />
                    <Text
                      style={[
                        typography.body2,
                        { color: themeColors.textPrimary, marginLeft: 8 },
                      ]}
                    >
                      {ageGroup}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              {/* Admin-only: Administrative Areas - Placeholder for future implementation */}
              {/*isAdmin && (
                <View style={styles.filterSection}>
                  <Text
                    style={[
                      typography.label1,
                      { color: themeColors.textPrimary, marginBottom: 12 },
                    ]}
                  >
                    Administrative Areas
                  </Text>
                  <Text
                    style={[typography.body3, { color: themeColors.dark4 }]}
                  >
                    Administrative area filtering will be implemented in a
                    future update.
                  </Text>
                </View>
              )*/}
            </ScrollView>

            <View style={styles.modalFooter}>
              <TouchableOpacity
                style={styles.applyButton}
                onPress={applyFilters}
              >
                <Text style={[typography.label1, { color: themeColors.white }]}>
                  Show Results
                </Text>
              </TouchableOpacity>
            </View>
          </Pressable>
        </Pressable>
      </Modal>
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
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8, // Add gap between search and filter
  },
  searchWrapper: {
    width: "100%",
    flex: 11, // Takes 11/12 of the space
    paddingRight: 16,
  },
  filterWrapper: {
    flex: 1, // Takes 1/12 of the space
    alignItems: "flex-end",
  },
  filterButton: {
    position: "relative",
    minWidth: 42,
    height: 42,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 8,
    borderRadius: 40,
    borderWidth: 1,
    borderColor: themeColors["green-500"],
    backgroundColor: themeColors.white,
  },
  filterButtonActive: {
    backgroundColor: themeColors["green-500"],
    borderColor: themeColors["green-500"],
  },
  filterPillsContainer: {
    marginTop: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  filterPillsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    flex: 1,
  },
  filterPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: themeColors.background,
    borderRadius: 16,
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginRight: 8,
    marginBottom: 8,
  },
  filterPillActive: {
    backgroundColor: themeColors["green-500"],
    color: themeColors.white,
  },
  clearAllButton: {
    marginLeft: "auto",
    paddingVertical: 6,
  },
  filterBadge: {
    ...typography.label3,
    position: "absolute",
    top: -4,
    right: -4,
    backgroundColor: themeColors.error,
    borderRadius: 40,
    paddingHorizontal: 8,
    paddingVertical: 4,
    color: themeColors.white,
    marginLeft: 4,
  },
  clearFiltersButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
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
  listHeader: {
    marginBottom: 16,
    paddingLeft: 12,
  },
  selectAllRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  customerCard: {
    backgroundColor: themeColors.white,
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: themeColors.cardBorder,
  },
  customerCardSelected: {
    borderColor: themeColors["green-500"],
    backgroundColor: themeColors["green-50"],
  },
  customerBody: {
    flexDirection: "row",
    alignItems: "center",
  },
  avatarContainer: {
    marginHorizontal: 12,
  },
  customerInfo: {
    flex: 1,
  },
  checkbox: {
    borderRadius: 4,
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
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    justifyContent: "flex-end",
  },
  modalContent: {
    backgroundColor: themeColors.white,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: "80%",
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: themeColors.mutedBorder,
  },
  modalBody: {
    padding: 20,
  },
  filterSection: {
    marginBottom: 24,
  },
  checkboxRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
  },
  modalFooter: {
    padding: 20,
    borderTopWidth: 1,
    borderTopColor: themeColors.mutedBorder,
    marginBottom: 36,
  },
  applyButton: {
    backgroundColor: themeColors["green-500"],
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: "center",
  },
});

export default BroadcastFarmerListTab;
