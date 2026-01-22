"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../contexts/AuthContext";
import HeaderNav from "../../components/HeaderNav";
import EditUserModal from "../../components/users/EditUserModal";
import TagBadge, { TAG_CONFIG } from "../../components/common/TagBadge";
import api from "../../lib/api";
import {
  ChartBarIcon,
  CalendarIcon,
  TagIcon,
  TicketIcon,
  ArrowPathIcon,
  FunnelIcon,
} from "@heroicons/react/24/outline";

export default function AnalyticsPage() {
  const { user, loading: authLoading, refreshUser } = useAuth();
  const router = useRouter();

  const [statistics, setStatistics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showProfileModal, setShowProfileModal] = useState(false);

  // Date filters
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const fetchStatistics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let url = "/admin/analytics/ticket-tags";
      const params = new URLSearchParams();
      if (startDate) params.append("start_date", startDate);
      if (endDate) params.append("end_date", endDate);
      if (params.toString()) url += `?${params.toString()}`;

      const response = await api.get(url);
      setStatistics(response.data);
    } catch (err) {
      console.error("Error fetching statistics:", err);
      setError(err.response?.data?.detail || "Failed to load statistics");
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate]);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/");
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (user) {
      fetchStatistics();
    }
  }, [user, fetchStatistics]);

  const handleProfileClick = () => {
    setShowProfileModal(true);
  };

  const handleProfileUpdate = () => {
    setShowProfileModal(false);
    if (refreshUser) {
      refreshUser();
    }
  };

  const handleApplyFilters = () => {
    fetchStatistics();
  };

  const handleClearFilters = () => {
    setStartDate("");
    setEndDate("");
  };

  // Calculate percentages for the bar chart
  const getPercentage = (count) => {
    if (!statistics || statistics.total_tagged === 0) return 0;
    return Math.round((count / statistics.total_tagged) * 100);
  };

  // Get max count for scaling bars
  const getMaxCount = () => {
    if (!statistics?.statistics) return 1;
    return Math.max(...statistics.statistics.map((s) => s.count), 1);
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-gradient-brand flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gradient-brand">
      <HeaderNav
        breadcrumbs={[
          { label: "Dashboard", path: "/" },
          { label: "Analytics" },
        ]}
        onProfileClick={handleProfileClick}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Page Header */}
        <div
          className="bg-white/80 backdrop-blur-md p-8 mb-6 animate-fade-in"
          style={{ borderRadius: "5px" }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <div
                className="flex items-center justify-center w-12 h-12 bg-gradient-to-br from-orange-500 to-orange-600 mr-4"
                style={{ borderRadius: "5px" }}
              >
                <ChartBarIcon className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-secondary-900">
                  Ticket Analytics
                </h1>
                <p className="text-secondary-600">
                  View ticket classification statistics and trends
                </p>
              </div>
            </div>
            <button
              onClick={fetchStatistics}
              disabled={loading}
              className="flex items-center px-4 py-2 bg-primary-600 text-white hover:bg-primary-700 transition-colors disabled:opacity-50 cursor-pointer"
              style={{ borderRadius: "5px" }}
            >
              <ArrowPathIcon
                className={`w-5 h-5 mr-2 ${loading ? "animate-spin" : ""}`}
              />
              Refresh
            </button>
          </div>
        </div>

        {/* Date Filters */}
        <div
          className="bg-white/80 backdrop-blur-md p-6 mb-6 animate-slide-up"
          style={{ borderRadius: "5px" }}
        >
          <div className="flex items-center mb-4">
            <FunnelIcon className="w-5 h-5 text-secondary-600 mr-2" />
            <h2 className="text-lg font-semibold text-secondary-900">
              Filter by Date
            </h2>
          </div>
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-1">
                Start Date
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="px-3 py-2 border border-secondary-300 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                style={{ borderRadius: "5px" }}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-1">
                End Date
              </label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="px-3 py-2 border border-secondary-300 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                style={{ borderRadius: "5px" }}
              />
            </div>
            <button
              onClick={handleApplyFilters}
              className="px-4 py-2 bg-primary-600 text-white hover:bg-primary-700 transition-colors cursor-pointer"
              style={{ borderRadius: "5px" }}
            >
              Apply Filters
            </button>
            {(startDate || endDate) && (
              <button
                onClick={handleClearFilters}
                className="px-4 py-2 bg-secondary-200 text-secondary-700 hover:bg-secondary-300 transition-colors cursor-pointer"
                style={{ borderRadius: "5px" }}
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {/* Error State */}
        {error && (
          <div
            className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 mb-6"
            style={{ borderRadius: "5px" }}
          >
            {error}
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
          </div>
        )}

        {/* Statistics Content */}
        {!loading && statistics && (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              <div
                className="bg-white/80 backdrop-blur-md p-6 animate-scale-in"
                style={{ borderRadius: "5px" }}
              >
                <div className="flex items-center">
                  <div
                    className="flex items-center justify-center w-12 h-12 bg-gradient-to-br from-green-500 to-green-600 mr-4"
                    style={{ borderRadius: "5px" }}
                  >
                    <TicketIcon className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <p className="text-sm text-secondary-600">Total Resolved</p>
                    <p className="text-3xl font-bold text-secondary-900">
                      {statistics.total_resolved}
                    </p>
                  </div>
                </div>
              </div>

              <div
                className="bg-white/80 backdrop-blur-md p-6 animate-scale-in"
                style={{ borderRadius: "5px", animationDelay: "0.1s" }}
              >
                <div className="flex items-center">
                  <div
                    className="flex items-center justify-center w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 mr-4"
                    style={{ borderRadius: "5px" }}
                  >
                    <TagIcon className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <p className="text-sm text-secondary-600">Tagged Tickets</p>
                    <p className="text-3xl font-bold text-secondary-900">
                      {statistics.total_tagged}
                    </p>
                  </div>
                </div>
              </div>

              <div
                className="bg-white/80 backdrop-blur-md p-6 animate-scale-in"
                style={{ borderRadius: "5px", animationDelay: "0.2s" }}
              >
                <div className="flex items-center">
                  <div
                    className="flex items-center justify-center w-12 h-12 bg-gradient-to-br from-gray-500 to-gray-600 mr-4"
                    style={{ borderRadius: "5px" }}
                  >
                    <CalendarIcon className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <p className="text-sm text-secondary-600">Untagged</p>
                    <p className="text-3xl font-bold text-secondary-900">
                      {statistics.untagged_count}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Tag Distribution Chart */}
            <div
              className="bg-white/80 backdrop-blur-md p-8 animate-slide-up"
              style={{ borderRadius: "5px" }}
            >
              <h2 className="text-xl font-bold text-secondary-900 mb-6">
                Ticket Categories Distribution
              </h2>

              {statistics.total_tagged === 0 ? (
                <div className="text-center py-12">
                  <TagIcon className="w-16 h-16 text-secondary-300 mx-auto mb-4" />
                  <p className="text-secondary-600">
                    No tagged tickets found for the selected period.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {statistics.statistics.map((stat) => {
                    const config =
                      TAG_CONFIG[stat.tag.toLowerCase()] || TAG_CONFIG.other;
                    const percentage = getPercentage(stat.count);
                    const barWidth = (stat.count / getMaxCount()) * 100;

                    return (
                      <div key={stat.tag} className="group">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center">
                            <TagBadge tag={stat.tag} size="sm" />
                            <span className="ml-3 text-secondary-600 text-sm">
                              {percentage}% of tagged tickets
                            </span>
                          </div>
                          <span className="text-lg font-semibold text-secondary-900">
                            {stat.count}
                          </span>
                        </div>
                        <div
                          className="w-full bg-secondary-100 overflow-hidden"
                          style={{ borderRadius: "5px", height: "12px" }}
                        >
                          <div
                            className={`h-full ${config.bgColor} transition-all duration-500 ease-out group-hover:opacity-80`}
                            style={{
                              width: `${barWidth}%`,
                              borderRadius: "5px",
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Tag Legend */}
            <div
              className="bg-white/80 backdrop-blur-md p-6 mt-6 animate-fade-in"
              style={{ borderRadius: "5px" }}
            >
              <h3 className="text-lg font-semibold text-secondary-900 mb-4">
                Tag Categories
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(TAG_CONFIG).map(([key, config]) => {
                  const Icon = config.icon;
                  return (
                    <div
                      key={key}
                      className={`flex items-start p-3 ${config.bgColor} border ${config.borderColor}`}
                      style={{ borderRadius: "5px" }}
                    >
                      <Icon
                        className={`w-5 h-5 ${config.textColor} mt-0.5 mr-3 flex-shrink-0`}
                      />
                      <div>
                        <p className={`font-medium ${config.textColor}`}>
                          {config.label}
                        </p>
                        <p className="text-xs text-secondary-600 mt-1">
                          {key === "fertilizer" &&
                            "Soil nutrients, composting, NPK ratios"}
                          {key === "pest" && "Insects, diseases, pest control"}
                          {key === "pre_planting" &&
                            "Seed selection, land preparation"}
                          {key === "harvesting" &&
                            "Harvest timing, storage, drying"}
                          {key === "irrigation" &&
                            "Watering, drought management"}
                          {key === "other" && "General farming advice"}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </main>

      {/* Profile Modal */}
      {showProfileModal && (
        <EditUserModal
          user={user}
          onClose={() => setShowProfileModal(false)}
          onUserUpdated={handleProfileUpdate}
          isSelfUpdate={true}
        />
      )}
    </div>
  );
}
