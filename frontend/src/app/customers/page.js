"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../../contexts/AuthContext";
import api from "../../lib/api";
import CustomerList from "../../components/customers/CustomerList";
import CreateCustomerModal from "../../components/customers/CreateCustomerModal";
import EditCustomerModal from "../../components/customers/EditCustomerModal";
import EditUserModal from "../../components/users/EditUserModal";
import HeaderNav from "../../components/HeaderNav";
import { useRouter } from "next/navigation";
import {
  MagnifyingGlassIcon,
  ArrowPathIcon,
} from "@heroicons/react/24/outline";

export default function CustomersPage() {
  const { user, loading: authLoading, refreshUser } = useAuth();
  const router = useRouter();
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState(null);

  // Redirect non-admins (for now, both admin and eo can access customers)
  useEffect(() => {
    if (user && user.user_type !== "admin" && user.user_type !== "eo") {
      router.push("/");
      return;
    }
  }, [user, router]);

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
      const response = await api.get("/customers/");

      // Filter customers based on search term
      let filteredCustomers = response.data;
      if (searchTerm) {
        const lowerSearchTerm = searchTerm.toLowerCase();
        filteredCustomers = response.data.filter(
          (customer) =>
            customer.phone_number?.toLowerCase().includes(lowerSearchTerm) ||
            customer.full_name?.toLowerCase().includes(lowerSearchTerm) ||
            customer.id?.toString().includes(lowerSearchTerm)
        );
      }

      setCustomers(filteredCustomers);
      setError(null);
    } catch (err) {
      console.error("Error fetching customers:", err);
      setError(err.response?.data?.detail || "Failed to fetch customers");
    } finally {
      setLoading(false);
    }
  }, [authLoading, user, searchTerm]);

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

  const handleDeleteCustomer = async (customerId) => {
    if (!confirm("Are you sure you want to delete this customer?")) {
      return;
    }

    try {
      await api.delete(`/customers/${customerId}`);
      fetchCustomers(); // Refresh the list
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to delete customer");
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

  // Don't render if user doesn't have access
  if (user && user.user_type !== "admin" && user.user_type !== "eo") {
    return null;
  }

  if (authLoading || (loading && customers.length === 0)) {
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

  const filteredCustomers = customers.filter((customer) => {
    if (!searchTerm) return true;
    const lowerSearchTerm = searchTerm.toLowerCase();
    return (
      customer.phone_number?.toLowerCase().includes(lowerSearchTerm) ||
      customer.full_name?.toLowerCase().includes(lowerSearchTerm) ||
      customer.id?.toString().includes(lowerSearchTerm)
    );
  });

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
                  Customers ({filteredCustomers.length})
                </h2>
                <p className="mt-1 text-sm text-gray-600">
                  Manage customer information and communication preferences
                </p>
              </div>
              <div className="mt-4 sm:mt-0">
                <button
                  onClick={handleCreateCustomer}
                  className="bg-green-600 text-white px-4 py-2 text-sm hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 cursor-pointer transition-colors duration-200"
                  style={{ borderRadius: "5px" }}
                >
                  Create Customer
                </button>
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
          </div>

          {/* Customer List */}
          <CustomerList
            customers={filteredCustomers}
            loading={loading}
            onEditCustomer={handleEditCustomer}
            onDeleteCustomer={handleDeleteCustomer}
          />
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
