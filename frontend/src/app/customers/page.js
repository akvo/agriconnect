"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../../contexts/AuthContext";
import api from "../../lib/api";
import CustomerList from "../../components/customers/CustomerList";
import CreateCustomerModal from "../../components/customers/CreateCustomerModal";
import EditCustomerModal from "../../components/customers/EditCustomerModal";
import DeleteCustomerModal from "../../components/customers/DeleteCustomerModal";
import EditUserModal from "../../components/users/EditUserModal";
import HeaderNav from "../../components/HeaderNav";
import { useRouter } from "next/navigation";
import {
  MagnifyingGlassIcon,
  ArrowPathIcon,
  ArrowDownTrayIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from "@heroicons/react/24/outline";
import AdministrativeCascadeFilter from "../../components/common/AdministrativeCascadeFilter";

const PAGE_SIZE = 10;

export default function CustomersPage() {
  const { user, loading: authLoading, refreshUser } = useAuth();
  const router = useRouter();
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [locationFilter, setLocationFilter] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCustomers, setTotalCustomers] = useState(0);
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);
  const searchTimeoutRef = useRef(null);

  // Redirect non-admins (for now, both admin and eo can access customers)
  useEffect(() => {
    if (user && user.user_type !== "admin" && user.user_type !== "eo") {
      router.push("/");
      return;
    }
  }, [user, router]);

  // Debounce search term
  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    searchTimeoutRef.current = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setCurrentPage(1);
    }, 300);
    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchTerm]);

  // Reset to page 1 when location filter changes
  useEffect(() => {
    setCurrentPage(1);
  }, [locationFilter]);

  const fetchCustomers = useCallback(async () => {
    // Don't fetch if still loading auth or user doesn't have access
    if (
      authLoading ||
      !user ||
      (user.user_type !== "admin" && user.user_type !== "eo")
    ) {
      return;
    }

    try {
      setLoading(true);
      const params = new URLSearchParams();
      params.append("page", currentPage.toString());
      params.append("size", PAGE_SIZE.toString());
      if (locationFilter) {
        params.append("administrative_ids", locationFilter);
      }
      if (debouncedSearchTerm) {
        params.append("search", debouncedSearchTerm);
      }
      const url = `/customers/list?${params.toString()}`;

      const response = await api.get(url);
      setCustomers(response.data.customers);
      setTotalCustomers(response.data.total);
      setError(null);
      setInitialLoadComplete(true);
    } catch (err) {
      console.error("Error fetching customers:", err);
      setError(err.response?.data?.detail || "Failed to fetch customers");
    } finally {
      setLoading(false);
    }
  }, [authLoading, user, locationFilter, currentPage, debouncedSearchTerm]);

  useEffect(() => {
    if (
      !authLoading &&
      (user?.user_type === "admin" || user?.user_type === "eo")
    ) {
      fetchCustomers();
    }
  }, [fetchCustomers, user, authLoading]);

  const handleSearch = (term) => {
    setSearchTerm(term);
  };

  const handleCreateCustomer = () => {
    setShowCreateModal(true);
  };

  const handleEditCustomer = (customer) => {
    setSelectedCustomer(customer);
    setShowEditModal(true);
  };

  const handleDeleteCustomer = (customer) => {
    setSelectedCustomer(customer);
    setShowDeleteModal(true);
  };

  const handleDeleteConfirmed = async (customerId) => {
    try {
      await api.delete(`/customers/${customerId}`);
      fetchCustomers(); // Refresh the list
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to delete customer");
      throw err; // Re-throw to let the modal handle the error state
    }
  };

  const handleCustomerCreated = () => {
    setShowCreateModal(false);
    fetchCustomers();
  };

  const handleCustomerUpdated = () => {
    setShowEditModal(false);
    setSelectedCustomer(null);
    fetchCustomers();
  };

  const handleProfileClick = () => {
    setShowProfileModal(true);
  };

  const handleProfileUpdate = () => {
    setShowProfileModal(false);
    if (refreshUser) {
      refreshUser();
    }
  };

  const handleLocationFilterChange = (filterData) => {
    setLocationFilter(filterData.administrativeId);
  };

  const handleExportCSV = async () => {
    try {
      setExporting(true);
      const params = new URLSearchParams();
      if (locationFilter) {
        params.append("administrative_id", locationFilter);
      }
      if (searchTerm) {
        params.append("search", searchTerm);
      }
      const queryString = params.toString();
      const url = `/customers/export${queryString ? `?${queryString}` : ""}`;

      const response = await api.get(url, {
        responseType: "blob",
      });

      // Create download link
      const blob = new Blob([response.data], { type: "text/csv" });
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      const timestamp = new Date().toISOString().split("T")[0];
      link.download = `customers_${timestamp}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err) {
      console.error("Error exporting customers:", err);
      alert(err.response?.data?.detail || "Failed to export customers");
    } finally {
      setExporting(false);
    }
  };

  // Don't render if user doesn't have access
  if (user && user.user_type !== "admin" && user.user_type !== "eo") {
    return null;
  }

  if (authLoading || (loading && !initialLoadComplete)) {
    return (
      <div className="min-h-screen bg-gradient-brand flex items-center justify-center">
        <div className="text-center animate-fade-in">
          <div className="relative">
            <ArrowPathIcon className="animate-spin h-16 w-16 text-primary-600 mx-auto mb-6" />
            <div
              className="absolute inset-0 bg-gradient-primary opacity-20 blur-lg animate-pulse"
              style={{ borderRadius: "5px" }}
            ></div>
          </div>
          <p className="text-secondary-700 font-medium text-lg">
            Loading customers...
          </p>
          <p className="text-secondary-500 text-sm mt-2">
            Please wait while we fetch the customer data
          </p>
        </div>
      </div>
    );
  }

  const totalPages = Math.ceil(totalCustomers / PAGE_SIZE);

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setCurrentPage(newPage);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-brand">
      <HeaderNav
        breadcrumbs={[
          { label: "Dashboard", path: "/" },
          { label: "Customer Management" },
        ]}
        onProfileClick={handleProfileClick}
      />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div
            className="bg-red-50 border border-red-200 p-4 mb-6"
            style={{ borderRadius: "5px" }}
          >
            <div className="text-red-700">{error}</div>
          </div>
        )}

        <div className="bg-white shadow-lg" style={{ borderRadius: "5px" }}>
          {/* Header with search and create button */}
          <div className="px-6 py-4 border-b border-gray-600">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-lg font-medium text-gray-900">
                  Customers ({totalCustomers})
                </h2>
                <p className="mt-1 text-sm text-gray-600">
                  Manage customer information and communication preferences
                </p>
              </div>
              <div className="mt-4 sm:mt-0">
                {user.user_type === "admin" && (
                  <button
                    onClick={handleCreateCustomer}
                    className="bg-green-600 text-white px-4 py-2 text-sm hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 cursor-pointer transition-colors duration-200"
                    style={{ borderRadius: "5px" }}
                  >
                    Create Customer
                  </button>
                )}
              </div>
            </div>

            {/* Search */}
            <div className="mt-4">
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search customers by name, phone, or ID..."
                  value={searchTerm}
                  onChange={(e) => handleSearch(e.target.value)}
                  className="block w-full pl-10 pr-3 py-2 bg-gray-50 leading-5 placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-2 focus:ring-green-500 focus:bg-white cursor-text"
                  style={{ borderRadius: "5px" }}
                />
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
                </div>
              </div>
            </div>

            {/* Location Filter and Export */}
            <div className="mt-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <AdministrativeCascadeFilter
                onChange={handleLocationFilterChange}
                showClearButton={true}
              />
              <button
                onClick={handleExportCSV}
                disabled={exporting || totalCustomers === 0}
                className="flex items-center px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors duration-200"
                style={{ borderRadius: "5px" }}
              >
                <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
                {exporting ? "Exporting..." : "Export CSV"}
              </button>
            </div>
          </div>

          {/* Customer List */}
          <CustomerList
            customers={customers}
            loading={loading}
            onEditCustomer={handleEditCustomer}
            onDeleteCustomer={handleDeleteCustomer}
          />

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
              <div className="text-sm text-gray-700">
                Showing{" "}
                <span className="font-medium">
                  {(currentPage - 1) * PAGE_SIZE + 1}
                </span>{" "}
                to{" "}
                <span className="font-medium">
                  {Math.min(currentPage * PAGE_SIZE, totalCustomers)}
                </span>{" "}
                of <span className="font-medium">{totalCustomers}</span>{" "}
                customers
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1}
                  className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200"
                  style={{ borderRadius: "5px" }}
                >
                  <ChevronLeftIcon className="h-4 w-4 mr-1" />
                  Previous
                </button>
                <span className="px-4 py-2 text-sm text-gray-700">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage === totalPages}
                  className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200"
                  style={{ borderRadius: "5px" }}
                >
                  Next
                  <ChevronRightIcon className="h-4 w-4 ml-1" />
                </button>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Modals */}
      {showCreateModal && (
        <CreateCustomerModal
          onClose={() => setShowCreateModal(false)}
          onCustomerCreated={handleCustomerCreated}
        />
      )}

      {showEditModal && selectedCustomer && (
        <EditCustomerModal
          customer={selectedCustomer}
          onClose={() => {
            setShowEditModal(false);
            setSelectedCustomer(null);
          }}
          onCustomerUpdated={handleCustomerUpdated}
        />
      )}

      {showDeleteModal && selectedCustomer && (
        <DeleteCustomerModal
          customer={selectedCustomer}
          onClose={() => {
            setShowDeleteModal(false);
            setSelectedCustomer(null);
          }}
          onDeleteConfirmed={handleDeleteConfirmed}
        />
      )}

      {/* Profile Modal - reuse the EditUserModal */}
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
