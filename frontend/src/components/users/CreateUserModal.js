"use client";

import { useState, useEffect } from "react";
import api from "../../lib/api";
import {
  CheckIcon,
  ExclamationTriangleIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";

export default function CreateUserModal({ onClose, onUserCreated }) {
  const [formData, setFormData] = useState({
    full_name: "",
    email: "",
    phone_number: "",
    user_type: "eo",
    administrative_id: null,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [createdUser, setCreatedUser] = useState(null);
  const [invitationStatus, setInvitationStatus] = useState(null);

  // Administrative location states
  const [administrativeLevels, setAdministrativeLevels] = useState([]);
  const [availableLocations, setAvailableLocations] = useState({});
  const [selectedLocation, setSelectedLocation] = useState({});
  const [loadingLocations, setLoadingLocations] = useState(false);
  const [isDataLoaded, setIsDataLoaded] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));

    // Clear administrative location if user type is changed to admin
    if (name === 'user_type' && value === 'admin') {
      setFormData(prev => ({
        ...prev,
        administrative_id: null
      }));
      setSelectedLocation({});
      setAvailableLocations({});
    }
  };

  // Load administrative levels and starting location data
  useEffect(() => {
    if (!isDataLoaded) {
      loadAdministrativeLevels();
    }
  }, [isDataLoaded]);

  const loadAdministrativeLevels = async () => {
    try {
      setLoadingLocations(true);
      const response = await api.get('/administrative/levels');
      setAdministrativeLevels(response.data);
      setIsDataLoaded(true);

      // Load starting locations (skip country level)
      const startIndex = 1; // Start from level after country (index 0)
      if (startIndex < response.data.length) {
        const startLevel = response.data[startIndex];
        loadStartingLocations(startLevel, startIndex);
      }
    } catch (err) {
      console.error('Error loading administrative levels:', err);
    } finally {
      setLoadingLocations(false);
    }
  };

  const loadStartingLocations = async (levelName, levelIndex) => {
    try {
      const response = await api.get(`/administrative/?level=${levelName}`);
      setAvailableLocations(prev => ({
        ...prev,
        [levelIndex]: response.data.administrative
      }));
    } catch (err) {
      console.error('Error loading starting locations:', err);
    }
  };

  const loadChildLocations = async (parentId, levelIndex) => {
    try {
      const response = await api.get(`/administrative/?parent_id=${parentId}`);
      setAvailableLocations(prev => ({
        ...prev,
        [levelIndex]: response.data.administrative
      }));
    } catch (err) {
      console.error('Error loading child locations:', err);
    }
  };

  const handleLocationChange = (levelIndex, locationId) => {
    const newSelectedLocation = { ...selectedLocation };
    const newAvailableLocations = { ...availableLocations };

    if (locationId) {
      newSelectedLocation[levelIndex] = parseInt(locationId);
      setFormData(prev => ({
        ...prev,
        administrative_id: parseInt(locationId)
      }));

      // Clear all deeper levels
      for (let i = levelIndex + 1; i < administrativeLevels.length; i++) {
        delete newSelectedLocation[i];
        delete newAvailableLocations[i];
      }

      // Load child locations for the next level
      const nextLevelIndex = levelIndex + 1;
      if (nextLevelIndex < administrativeLevels.length) {
        loadChildLocations(locationId, nextLevelIndex);
      }
    } else {
      // Clear this level and all deeper levels
      for (let i = levelIndex; i < administrativeLevels.length; i++) {
        delete newSelectedLocation[i];
        delete newAvailableLocations[i];
      }

      // Set administrative_id to the parent level or null
      const parentLevelIndex = levelIndex - 1;
      if (parentLevelIndex >= 0 && newSelectedLocation[parentLevelIndex]) {
        setFormData(prev => ({
          ...prev,
          administrative_id: newSelectedLocation[parentLevelIndex]
        }));
      } else {
        setFormData(prev => ({
          ...prev,
          administrative_id: null
        }));
      }
    }

    setSelectedLocation(newSelectedLocation);
    setAvailableLocations(newAvailableLocations);
  };

  const getLevelName = (levelIndex) => {
    return administrativeLevels[levelIndex] || `Level ${levelIndex + 1}`;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    // Validate administrative location for extension officers
    if (formData.user_type === "eo" && !formData.administrative_id) {
      setError("Administrative location is required for extension officers");
      setLoading(false);
      return;
    }

    // Ensure admin users don't have administrative_id set
    const submitData = { ...formData };
    if (submitData.user_type === "admin") {
      submitData.administrative_id = null;
    }

    try {
      const response = await api.post("/admin/users/", submitData);
      setCreatedUser(response.data.user);
      setInvitationStatus({
        sent: response.data.invitation_sent,
        url: response.data.invitation_url,
        message: response.data.message,
      });
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create user");
    } finally {
      setLoading(false);
    }
  };

  const handleComplete = () => {
    onUserCreated();
    onClose();
  };

  if (createdUser && invitationStatus) {
    return (
      <div className="fixed inset-0 bg-secondary-900/50 backdrop-blur-sm overflow-y-auto h-full w-full z-50 flex items-center justify-center p-4">
        <div
          className="bg-white/90 backdrop-blur-md w-full max-w-[32rem] animate-scale-in p-8"
          style={{
            borderRadius: "5px",
            border: "1px solid rgb(191, 219, 254)",
          }}
        >
          <div className="text-center">
            <div
              className="flex items-center justify-center w-16 h-16 mx-auto bg-gradient-success mb-6"
              style={{ borderRadius: "5px" }}
            >
              <CheckIcon className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-2xl font-bold text-secondary-900 mb-3">
              User Created Successfully! 🎉
            </h3>
            <p className="text-secondary-600 mb-6">
              The new user account has been created and is ready to use.
            </p>

            <div
              className="bg-yellow-50 border border-yellow-200 p-4 mb-4"
              style={{ borderRadius: "5px" }}
            >
              <div className="flex">
                <div>
                  <h4 className="text-sm font-medium text-yellow-800 flex justify-center">
                    <ExclamationTriangleIcon className="w-5 h-5 text-yellow-400 mt-0.5 mr-2" />
                    Next Steps
                  </h4>
                  <p className="text-sm text-yellow-700 mt-1">
                    The user will receive an invitation email to set up their
                    account. If the email fails, you can resend it from the user
                    list.
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  User Email
                </label>
                <p
                  className="mt-1 text-sm text-gray-900 font-mono bg-gray-50 p-2 border"
                  style={{ borderRadius: "5px" }}
                >
                  {createdUser.email}
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Invitation Status
                </label>
                <p
                  className="mt-1 text-sm text-gray-900 bg-gray-50 p-2 border"
                  style={{ borderRadius: "5px" }}
                >
                  {invitationStatus.sent ? (
                    <>
                      ✅ Invitation sent successfully!
                      <br />
                      {invitationStatus.url && (
                        <span className="text-xs text-gray-600 font-mono break-all">
                          {invitationStatus.url}
                        </span>
                      )}
                    </>
                  ) : (
                    <>
                      ⚠️ User created but invitation email failed to send
                      <br />
                      <span className="text-xs text-gray-600">
                        Admin can resend invitation from user list
                      </span>
                    </>
                  )}
                </p>
              </div>
            </div>

            <div className="mt-6">
              <button
                onClick={handleComplete}
                className="w-full bg-green-600 text-white py-2 px-4 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 cursor-pointer transition-colors duration-200"
                style={{ borderRadius: "5px" }}
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-secondary-900/50 backdrop-blur-sm overflow-y-auto h-full w-full z-50 flex items-center justify-center p-4">
      <div
        className="bg-white/90 backdrop-blur-md w-full max-w-[32rem] animate-scale-in p-8"
        style={{ borderRadius: "5px", border: "1px solid rgb(191, 219, 254)" }}
      >
        <form onSubmit={handleSubmit}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">
              Create New User
            </h3>
            <button
              type="button"
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 cursor-pointer"
            >
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>

          {error && (
            <div
              className="bg-red-50 border border-red-200 p-3 mb-4"
              style={{ borderRadius: "5px" }}
            >
              <div className="text-red-700 text-sm">{error}</div>
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label
                htmlFor="full_name"
                className="block text-sm font-medium text-gray-700"
              >
                Full Name *
              </label>
              <input
                type="text"
                id="full_name"
                name="full_name"
                value={formData.full_name}
                onChange={handleChange}
                required
                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                style={{ borderRadius: "5px" }}
                placeholder="Enter full name"
              />
            </div>

            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-gray-700"
              >
                Email Address *
              </label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                required
                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                style={{ borderRadius: "5px" }}
                placeholder="user@example.com"
              />
            </div>

            <div>
              <label
                htmlFor="phone_number"
                className="block text-sm font-medium text-gray-700"
              >
                Phone Number *
              </label>
              <input
                type="tel"
                id="phone_number"
                name="phone_number"
                value={formData.phone_number}
                onChange={handleChange}
                required
                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                style={{ borderRadius: "5px" }}
                placeholder="+1234567890"
              />
              <p className="mt-1 text-xs text-gray-500">
                Must start with + and be at least 10 characters
              </p>
            </div>

            <div>
              <label
                htmlFor="user_type"
                className="block text-sm font-medium text-gray-700"
              >
                User Type *
              </label>
              <select
                id="user_type"
                name="user_type"
                value={formData.user_type}
                onChange={handleChange}
                required
                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                style={{ borderRadius: "5px" }}
              >
                <option value="eo">Extension Officer</option>
                <option value="admin">Administrator</option>
              </select>
            </div>

            {formData.user_type === "eo" && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Administrative Location *
                  </label>

                  {loadingLocations ? (
                    <div className="text-sm text-gray-500">Loading locations...</div>
                  ) : (
                    <div className="space-y-3">
                      {/* Show first level dropdown (index 1, after country) */}
                      {administrativeLevels.length > 1 && availableLocations[1] && (
                        <div>
                          <label className="block text-sm font-medium text-gray-600">
                            {getLevelName(1)}
                          </label>
                          <select
                            value={selectedLocation[1] || ""}
                            onChange={(e) => handleLocationChange(1, e.target.value)}
                            className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                            style={{ borderRadius: "5px" }}
                          >
                            <option value="">Select {getLevelName(1)}</option>
                            {availableLocations[1].map((location) => (
                              <option key={location.id} value={location.id}>
                                {location.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}

                      {/* Show second level dropdown only if first level is selected */}
                      {selectedLocation[1] && availableLocations[2] && (
                        <div>
                          <label className="block text-sm font-medium text-gray-600">
                            {getLevelName(2)}
                          </label>
                          <select
                            value={selectedLocation[2] || ""}
                            onChange={(e) => handleLocationChange(2, e.target.value)}
                            className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                            style={{ borderRadius: "5px" }}
                          >
                            <option value="">Select {getLevelName(2)}</option>
                            {availableLocations[2].map((location) => (
                              <option key={location.id} value={location.id}>
                                {location.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}

                      {/* Show third level dropdown only if second level is selected */}
                      {selectedLocation[2] && availableLocations[3] && (
                        <div>
                          <label className="block text-sm font-medium text-gray-600">
                            {getLevelName(3)}
                          </label>
                          <select
                            value={selectedLocation[3] || ""}
                            onChange={(e) => handleLocationChange(3, e.target.value)}
                            className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                            style={{ borderRadius: "5px" }}
                          >
                            <option value="">Select {getLevelName(3)}</option>
                            {availableLocations[3].map((location) => (
                              <option key={location.id} value={location.id}>
                                {location.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}

                      {/* Show message if no locations are available */}
                      {administrativeLevels.length > 1 && !availableLocations[1] && (
                        <div className="text-sm text-gray-500">
                          No administrative locations available
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="mt-6 flex space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 bg-white py-2 px-4 bg-gray-50 focus:bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 cursor-pointer transition-colors duration-200"
              style={{ borderRadius: "5px" }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-green-600 py-2 px-4 border border-transparent text-sm font-medium text-white hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors duration-200"
              style={{ borderRadius: "5px" }}
            >
              {loading ? "Creating..." : "Create User"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
