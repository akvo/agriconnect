"use client";

import { useState, useEffect, useCallback } from "react";
import api from "../../lib/api";
import { XMarkIcon } from "@heroicons/react/24/outline";

export default function EditUserModal({
  user,
  onClose,
  onUserUpdated,
  isSelfUpdate = false,
}) {
  const [formData, setFormData] = useState({
    full_name: user.full_name || "",
    phone_number: user.phone_number || "",
    user_type: user.user_type || "eo",
    administrative_id: user.administrative_location?.id || null,
    current_password: "",
    new_password: "",
    confirm_password: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  const [showPasswordFields, setShowPasswordFields] = useState(false);

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
    if (name === "user_type" && value === "admin") {
      setFormData((prev) => ({
        ...prev,
        administrative_id: null,
      }));
      setSelectedLocation({});
      setAvailableLocations({});
    }
  };

  const loadChildLocations = useCallback(async (parentId, levelIndex) => {
    try {
      const response = await api.get(`/administrative/?parent_id=${parentId}`);
      setAvailableLocations((prev) => ({
        ...prev,
        [levelIndex]: response.data.administrative,
      }));
    } catch (err) {
      console.error("Error loading child locations:", err);
    }
  }, []);

  const loadStartingLocations = useCallback(async (levelName, levelIndex) => {
    try {
      const response = await api.get(`/administrative/?level=${levelName}`);
      setAvailableLocations((prev) => ({
        ...prev,
        [levelIndex]: response.data.administrative,
      }));
    } catch (err) {
      console.error("Error loading starting locations:", err);
    }
  }, []);

  const loadUserAdministrativeHierarchy = useCallback(
    async (administrativeId, levels) => {
      try {
        // Build hierarchy by traversing up the parent_id chain
        const hierarchy = [];
        let currentId = administrativeId;

        while (currentId) {
          const response = await api.get(`/administrative/${currentId}`);
          const adminArea = response.data;
          hierarchy.unshift(adminArea); // Add to beginning
          currentId = adminArea.parent_id;
        }

        // Skip country (first element) and set up the dropdowns
        const newSelectedLocation = {};
        const levelsToUse = levels || administrativeLevels;

        for (let i = 1; i < hierarchy.length; i++) {
          const area = hierarchy[i];
          // Find the level index for this area
          const levelIndex = levelsToUse.findIndex(
            (l) => l.toLowerCase() === area.level?.name?.toLowerCase()
          );

          if (levelIndex >= 0) {
            newSelectedLocation[levelIndex] = area.id;

            // Load sibling locations for this level
            if (hierarchy[i - 1]) {
              await loadChildLocations(hierarchy[i - 1].id, levelIndex);
            }
          }
        }

        // Load children of the assigned area (for next level dropdown)
        const assignedArea = hierarchy[hierarchy.length - 1];
        if (assignedArea) {
          const assignedLevelIndex = levelsToUse.findIndex(
            (l) => l.toLowerCase() === assignedArea.level?.name?.toLowerCase()
          );
          if (
            assignedLevelIndex >= 0 &&
            assignedLevelIndex + 1 < levelsToUse.length
          ) {
            await loadChildLocations(assignedArea.id, assignedLevelIndex + 1);
          }
        }

        setSelectedLocation(newSelectedLocation);
      } catch (err) {
        console.error("Error loading user administrative hierarchy:", err);
      }
    },
    [administrativeLevels, loadChildLocations]
  );

  const loadAdministrativeLevels = useCallback(async () => {
    try {
      setLoadingLocations(true);
      const response = await api.get("/administrative/levels");
      setAdministrativeLevels(response.data);
      setIsDataLoaded(true);

      // If user has existing administrative location, load the hierarchy first
      // This ensures dropdowns show with correct values from the start
      if (user.administrative_location?.id) {
        await loadUserAdministrativeHierarchy(
          user.administrative_location.id,
          response.data
        );
      } else {
        // Only load starting locations if no existing assignment
        const startIndex = 1; // Start from level after country (index 0)
        if (startIndex < response.data.length) {
          const startLevel = response.data[startIndex];
          await loadStartingLocations(startLevel, startIndex);
        }
      }
    } catch (err) {
      console.error("Error loading administrative levels:", err);
    } finally {
      setLoadingLocations(false);
    }
  }, [user, loadUserAdministrativeHierarchy, loadStartingLocations]);

  // Load administrative levels and starting location data
  useEffect(() => {
    if (!isSelfUpdate && !isDataLoaded && formData.user_type === "eo") {
      loadAdministrativeLevels();
    }
  }, [
    isSelfUpdate,
    isDataLoaded,
    formData.user_type,
    loadAdministrativeLevels,
  ]);

  const handleLocationChange = (levelIndex, locationId) => {
    const newSelectedLocation = { ...selectedLocation };
    const newAvailableLocations = { ...availableLocations };

    if (locationId) {
      newSelectedLocation[levelIndex] = parseInt(locationId);
      setFormData((prev) => ({
        ...prev,
        administrative_id: parseInt(locationId),
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
        setFormData((prev) => ({
          ...prev,
          administrative_id: newSelectedLocation[parentLevelIndex],
        }));
      } else {
        setFormData((prev) => ({
          ...prev,
          administrative_id: null,
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

    try {
      if (isSelfUpdate) {
        // Handle self-update with password validation
        if (showPasswordFields) {
          if (!formData.current_password) {
            setError("Current password is required");
            setLoading(false);
            return;
          }
          if (!formData.new_password) {
            setError("New password is required");
            setLoading(false);
            return;
          }
          if (formData.new_password !== formData.confirm_password) {
            setError("New passwords do not match");
            setLoading(false);
            return;
          }
          if (formData.new_password.length < 8) {
            setError("New password must be at least 8 characters long");
            setLoading(false);
            return;
          }
        }

        // Prepare self-update data
        const updateData = {};
        if (formData.full_name !== user.full_name) {
          updateData.full_name = formData.full_name;
        }
        if (formData.phone_number !== user.phone_number) {
          updateData.phone_number = formData.phone_number;
        }
        if (
          showPasswordFields &&
          formData.current_password &&
          formData.new_password
        ) {
          updateData.current_password = formData.current_password;
          updateData.new_password = formData.new_password;
        }

        if (Object.keys(updateData).length === 0) {
          onClose();
          return;
        }

        await api.put("/auth/profile", updateData);
      } else {
        // Handle admin update with administrative location
        const changedData = {};
        const fieldsToCheck = ["full_name", "phone_number", "user_type"];
        fieldsToCheck.forEach((key) => {
          if (formData[key] !== user[key]) {
            changedData[key] = formData[key];
          }
        });

        // Handle administrative location changes for extension officers
        if (formData.user_type === "eo") {
          const currentAdminId = user.administrative_location?.id;
          if (formData.administrative_id !== currentAdminId) {
            changedData.administrative_id = formData.administrative_id;
          }
        }

        if (Object.keys(changedData).length === 0) {
          onClose();
          return;
        }

        await api.put(`/admin/users/${user.id}`, changedData);
      }

      onUserUpdated();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update user");
    } finally {
      setLoading(false);
    }
  };

  const getUserTypeLabel = (userType) => {
    switch (userType) {
      case "admin":
        return "Administrator";
      case "eo":
        return "Extension Officer";
      default:
        return userType;
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="fixed inset-0 bg-secondary-900/50 backdrop-blur-sm overflow-y-auto h-full w-full z-50 flex items-center justify-center p-4">
      <div
        className="bg-white/90 backdrop-blur-md w-full max-w-[42rem] animate-scale-in p-8"
        style={{ borderRadius: "5px", border: "1px solid rgb(191, 219, 254)" }}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900">
            {showDetails
              ? isSelfUpdate
                ? "Profile Details"
                : "User Details"
              : isSelfUpdate
                ? "Edit Profile"
                : "Edit User"}
          </h3>
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={() => setShowDetails(!showDetails)}
              className="text-sm text-indigo-600 hover:text-indigo-500"
            >
              {showDetails ? "Edit" : "View Details"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>
        </div>

        {showDetails ? (
          <div className="space-y-4">
            <div className="bg-gray-50 p-4" style={{ borderRadius: "5px" }}>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    User ID
                  </label>
                  <p className="mt-1 text-sm text-gray-900">#{user.id}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Status
                  </label>
                  <span
                    className={`mt-1 inline-flex items-center px-2.5 py-0.5 text-xs font-medium ${
                      user.is_active === "true"
                        ? "bg-green-100 text-green-800"
                        : "bg-red-100 text-red-800"
                    }`}
                    style={{ borderRadius: "5px" }}
                  >
                    {user.is_active === "true" ? "Active" : "Inactive"}
                  </span>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Full Name
                  </label>
                  <p className="mt-1 text-sm text-gray-900">{user.full_name}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Email
                  </label>
                  <p className="mt-1 text-sm text-gray-900">{user.email}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Phone Number
                  </label>
                  <p className="mt-1 text-sm text-gray-900">
                    {user.phone_number}
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    User Type
                  </label>
                  <span
                    className={`mt-1 inline-flex items-center px-2.5 py-0.5 text-xs font-medium ${
                      user.user_type === "admin"
                        ? "bg-purple-100 text-purple-800"
                        : "bg-blue-100 text-blue-800"
                    }`}
                    style={{ borderRadius: "5px" }}
                  >
                    {getUserTypeLabel(user.user_type)}
                  </span>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Created At
                  </label>
                  <p className="mt-1 text-sm text-gray-900">
                    {formatDate(user.created_at)}
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Updated At
                  </label>
                  <p className="mt-1 text-sm text-gray-900">
                    {formatDate(user.updated_at)}
                  </p>
                </div>
              </div>
            </div>
            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="bg-gray-600 text-white py-2 px-4 hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
                style={{ borderRadius: "5px" }}
              >
                Close
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
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
                  Full Name
                </label>
                <input
                  type="text"
                  id="full_name"
                  name="full_name"
                  value={formData.full_name}
                  onChange={handleChange}
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
                  Email Address
                </label>
                <input
                  type="email"
                  id="email"
                  value={user.email}
                  disabled
                  className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white bg-gray-50 cursor-not-allowed"
                  style={{ borderRadius: "5px" }}
                />
                <p className="mt-1 text-xs text-gray-500">
                  Email cannot be changed
                </p>
              </div>

              <div>
                <label
                  htmlFor="phone_number"
                  className="block text-sm font-medium text-gray-700"
                >
                  Phone Number
                </label>
                <input
                  type="tel"
                  id="phone_number"
                  name="phone_number"
                  value={formData.phone_number}
                  onChange={handleChange}
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
                  User Type
                </label>
                {isSelfUpdate ? (
                  <div className="mt-1">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 text-xs font-medium ${
                        user.user_type === "admin"
                          ? "bg-purple-100 text-purple-800"
                          : "bg-blue-100 text-blue-800"
                      }`}
                      style={{ borderRadius: "5px" }}
                    >
                      {getUserTypeLabel(user.user_type)}
                    </span>
                    <p className="mt-1 text-xs text-gray-500">
                      User type cannot be changed by yourself
                    </p>
                  </div>
                ) : (
                  <select
                    id="user_type"
                    name="user_type"
                    value={formData.user_type}
                    onChange={handleChange}
                    className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                    style={{ borderRadius: "5px" }}
                  >
                    <option value="eo">Extension Officer</option>
                    <option value="admin">Administrator</option>
                  </select>
                )}
              </div>

              {!isSelfUpdate && formData.user_type === "eo" && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Administrative Location
                    </label>

                    {loadingLocations ? (
                      <div className="text-sm text-gray-500">
                        Loading locations...
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {/* Show first level dropdown (index 1, after country) */}
                        {administrativeLevels.length > 1 &&
                          availableLocations[1] && (
                            <div>
                              <label className="block text-sm font-medium text-gray-600">
                                {getLevelName(1)}
                              </label>
                              <select
                                value={
                                  selectedLocation[1] ||
                                  user.administrative_location?.id ||
                                  ""
                                }
                                onChange={(e) =>
                                  handleLocationChange(1, e.target.value)
                                }
                                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                                style={{ borderRadius: "5px" }}
                              >
                                <option value="">
                                  Select {getLevelName(1)}
                                </option>
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
                              onChange={(e) =>
                                handleLocationChange(2, e.target.value)
                              }
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
                              onChange={(e) =>
                                handleLocationChange(3, e.target.value)
                              }
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
                        {administrativeLevels.length > 1 &&
                          !availableLocations[1] && (
                            <div className="text-sm text-gray-500">
                              No administrative locations available
                            </div>
                          )}

                        {/* Show current assignment level indicator */}
                        {formData.administrative_id && (
                          <div
                            className="mt-3 p-3 bg-green-50 border border-green-200"
                            style={{ borderRadius: "5px" }}
                          >
                            <p className="text-sm text-green-800">
                              <strong>Assignment Level:</strong>{" "}
                              {getLevelName(
                                Object.keys(selectedLocation).length
                              )}
                            </p>
                            <p className="text-xs text-green-600 mt-1">
                              This user will have access to all subordinate
                              areas.
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {isSelfUpdate && (
                <div
                  className="bg-gray-50 p-4 mt-4"
                  style={{ borderRadius: "5px" }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-medium text-gray-700">
                      Change Password
                    </h4>
                    <button
                      type="button"
                      onClick={() => {
                        setShowPasswordFields(!showPasswordFields);
                        if (showPasswordFields) {
                          setFormData((prev) => ({
                            ...prev,
                            current_password: "",
                            new_password: "",
                            confirm_password: "",
                          }));
                        }
                      }}
                      className="text-sm text-indigo-600 hover:text-indigo-500"
                    >
                      {showPasswordFields ? "Cancel" : "Change Password"}
                    </button>
                  </div>

                  {showPasswordFields && (
                    <div className="space-y-4">
                      <div>
                        <label
                          htmlFor="current_password"
                          className="block text-sm font-medium text-gray-700"
                        >
                          Current Password
                        </label>
                        <input
                          type="password"
                          id="current_password"
                          name="current_password"
                          value={formData.current_password}
                          onChange={handleChange}
                          className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                          style={{ borderRadius: "5px" }}
                          placeholder="Enter current password"
                        />
                      </div>

                      <div>
                        <label
                          htmlFor="new_password"
                          className="block text-sm font-medium text-gray-700"
                        >
                          New Password
                        </label>
                        <input
                          type="password"
                          id="new_password"
                          name="new_password"
                          value={formData.new_password}
                          onChange={handleChange}
                          className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                          style={{ borderRadius: "5px" }}
                          placeholder="Enter new password"
                        />
                        <p className="mt-1 text-xs text-gray-500">
                          Must be at least 8 characters long
                        </p>
                      </div>

                      <div>
                        <label
                          htmlFor="confirm_password"
                          className="block text-sm font-medium text-gray-700"
                        >
                          Confirm New Password
                        </label>
                        <input
                          type="password"
                          id="confirm_password"
                          name="confirm_password"
                          value={formData.confirm_password}
                          onChange={handleChange}
                          className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                          style={{ borderRadius: "5px" }}
                          placeholder="Confirm new password"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="mt-6 flex space-x-3">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 bg-white py-2 px-4 bg-gray-50 focus:bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                style={{ borderRadius: "5px" }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 bg-green-600 py-2 px-4 border border-transparent text-sm font-medium text-white hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ borderRadius: "5px" }}
              >
                {loading
                  ? "Updating..."
                  : isSelfUpdate
                    ? "Update Profile"
                    : "Update User"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
