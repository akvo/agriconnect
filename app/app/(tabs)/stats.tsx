import React, { useEffect, useState, useMemo, useCallback } from "react";
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from "react-native";
import Feathericons from "@expo/vector-icons/Feather";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";
import { useDatabase } from "@/database";
import { DAOManager, UserStats } from "@/database/dao";
import { useNetwork } from "@/contexts/NetworkContext";
import { api } from "@/services/api";

type TimePeriod = "week" | "month" | "all";

const Stats: React.FC = () => {
  const db = useDatabase();
  const dao = useMemo(() => new DAOManager(db), [db]);
  const { isOnline } = useNetwork();

  const [stats, setStats] = useState<UserStats | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedPeriod, setSelectedPeriod] = useState<TimePeriod>("all");

  const fetchStats = useCallback(async () => {
    setIsLoading(true);
    try {
      if (isOnline) {
        const apiStats = await api.getUserStats();
        dao.userStats.saveFromApi(db, apiStats);
        const cachedStats = dao.userStats.get(db);
        setStats(cachedStats);
      } else {
        const cachedStats = dao.userStats.get(db);
        setStats(cachedStats);
      }
    } catch (error) {
      console.error("Error fetching user stats:", error);
      const cachedStats = dao.userStats.get(db);
      setStats(cachedStats);
    } finally {
      setIsLoading(false);
    }
  }, [isOnline, dao, db]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const getStatValue = (
    stat: "farmersReached" | "conversationsResolved" | "messagesSent",
    period: TimePeriod,
  ): number => {
    if (!stats) {
      return 0;
    }
    const periodMap = {
      week: "Week",
      month: "Month",
      all: "All",
    };
    const key = `${stat}${periodMap[period]}` as keyof UserStats;
    return (stats[key] as number) ?? 0;
  };

  const periodLabels: Record<TimePeriod, string> = {
    week: "This Week",
    month: "This Month",
    all: "All Time",
  };

  const statCards = [
    {
      key: "farmersReached" as const,
      label: "Farmers Reached",
      icon: "user-plus" as const,
      description: "Unique customers you have messaged",
    },
    {
      key: "conversationsResolved" as const,
      label: "Conversations Resolved",
      icon: "check-circle" as const,
      description: "Tickets you have resolved",
    },
    {
      key: "messagesSent" as const,
      label: "Messages Sent",
      icon: "message-circle" as const,
      description: "Total messages you have sent",
    },
  ];

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.contentContainer}
      refreshControl={
        <RefreshControl
          refreshing={isLoading}
          onRefresh={fetchStats}
          colors={[themeColors["green-500"]]}
          tintColor={themeColors["green-500"]}
        />
      }
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Your Statistics</Text>
        <Text style={styles.headerSubtitle}>
          Track your performance and impact
        </Text>
      </View>

      {/* Period Selector */}
      <View style={styles.periodSelector}>
        {(["week", "month", "all"] as TimePeriod[]).map((period) => (
          <TouchableOpacity
            key={period}
            style={[
              styles.periodButton,
              selectedPeriod === period && styles.periodButtonActive,
            ]}
            onPress={() => setSelectedPeriod(period)}
          >
            <Text
              style={[
                styles.periodButtonText,
                selectedPeriod === period && styles.periodButtonTextActive,
              ]}
            >
              {periodLabels[period]}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Stats Cards */}
      <View style={styles.statsContainer}>
        {statCards.map((stat) => (
          <View key={stat.key} style={styles.statCard}>
            <View style={styles.statHeader}>
              <View style={styles.statIconContainer}>
                <Feathericons
                  name={stat.icon}
                  size={24}
                  color={themeColors["green-500"]}
                />
              </View>
              <Text style={styles.statValue}>
                {getStatValue(stat.key, selectedPeriod)}
              </Text>
            </View>
            <Text style={styles.statLabel}>{stat.label}</Text>
            <Text style={styles.statDescription}>{stat.description}</Text>
          </View>
        ))}

        {/* Average Response Time Card (placeholder) */}
        <View style={[styles.statCard, styles.statCardDisabled]}>
          <View style={styles.statHeader}>
            <View
              style={[styles.statIconContainer, styles.statIconContainerMuted]}
            >
              <Feathericons
                name="clock"
                size={24}
                color={themeColors.textSecondary}
              />
            </View>
            <Text style={[styles.statValue, styles.statValueMuted]}>--</Text>
          </View>
          <Text style={[styles.statLabel, styles.statLabelMuted]}>
            Average Response Time
          </Text>
          <Text style={styles.statDescription}>Coming soon</Text>
        </View>
      </View>

      {/* Last updated */}
      {stats?.updatedAt && (
        <Text style={styles.lastUpdated}>
          Last updated: {new Date(stats.updatedAt).toLocaleString()}
        </Text>
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: themeColors.background,
  },
  contentContainer: {
    padding: 16,
    paddingBottom: 32,
  },
  header: {
    marginBottom: 24,
    paddingTop: 48,
  },
  headerTitle: {
    ...typography.heading4,
    fontWeight: "bold",
    color: themeColors.textPrimary,
    marginBottom: 4,
  },
  headerSubtitle: {
    ...typography.body2,
    color: themeColors.textSecondary,
  },
  periodSelector: {
    flexDirection: "row",
    backgroundColor: themeColors.white,
    borderRadius: 12,
    padding: 4,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: themeColors.mutedBorder,
  },
  periodButton: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 8,
    alignItems: "center",
  },
  periodButtonActive: {
    backgroundColor: themeColors["green-500"],
  },
  periodButtonText: {
    ...typography.label2,
    fontWeight: "600",
    color: themeColors.textSecondary,
  },
  periodButtonTextActive: {
    color: themeColors.white,
  },
  statsContainer: {
    gap: 16,
  },
  statCard: {
    backgroundColor: themeColors.white,
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: themeColors.cardBorder,
  },
  statCardDisabled: {
    opacity: 0.6,
  },
  statHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  statIconContainer: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: themeColors["green-50"],
    justifyContent: "center",
    alignItems: "center",
  },
  statIconContainerMuted: {
    backgroundColor: themeColors.mutedBorder,
  },
  statValue: {
    ...typography.heading3,
    fontWeight: "bold",
    color: themeColors["green-500"],
  },
  statValueMuted: {
    color: themeColors.textSecondary,
  },
  statLabel: {
    ...typography.label1,
    fontWeight: "bold",
    color: themeColors.textPrimary,
    marginBottom: 4,
  },
  statLabelMuted: {
    color: themeColors.textSecondary,
  },
  statDescription: {
    ...typography.body3,
    color: themeColors.textSecondary,
  },
  lastUpdated: {
    ...typography.caption1,
    color: themeColors.textSecondary,
    textAlign: "center",
    marginTop: 24,
  },
});

export default Stats;
