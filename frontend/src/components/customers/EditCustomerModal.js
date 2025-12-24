"use client";

import { useState, useEffect, useCallback } from "react";
import { XMarkIcon } from "@heroicons/react/24/outline";
import api from "../../lib/api";
import { CROP_TYPES } from "@/lib/config";

export default function EditCustomerModal({
  customer,
  onClose,
  onCustomerUpdated,
}) {
  const [formData, setFormData] = useState({
    full_name: customer.full_name || "",
    language: customer.language || "en",
    crop_type: customer.crop_type || "",
    gender: customer.gender || "",
    age: customer.age || "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Administrative location states
  const [administrativeLevels, setAdministrativeLevels] = useState([]);
  const [availableLocations, setAvailableLocations] = useState({});
  const [selectedLocation, setSelectedLocation] = useState({});
  const [loadingLocations, setLoadingLocations] = useState(false);
  const [isDataLoaded, setIsDataLoaded] = useState(false);

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

  const loadCustomerAdministrativeHierarchy = useCallback(
    async (administrativeId) => {
      try {
        // Get the ward administrative details first
        const response = await api.get(`/administrative/${administrativeId}`);
        const wardAdmin = response.data;

        // Set the ward level selection
        let currentId = wardAdmin.parent_id;

        // Collect all ancestors up to country level
        const selectedAdmins = {
          [wardAdmin.level.id - 1]: wardAdmin.id,
        };
        while (currentId) {
          const ancestorResponse = await api.get(
            `/administrative/${currentId}`
          );
          const ancestor = ancestorResponse.data;
          const levelIndex = ancestor.level.id - 1;
          await loadChildLocations(ancestor.id, ancestor.level.id);
          selectedAdmins[levelIndex] = ancestor.id;
          currentId = ancestor.parent_id;
        }
        setSelectedLocation(selectedAdmins);
      } catch (err) {
        console.error("Error loading customer administrative hierarchy:", err);
      }
    },
    [loadChildLocations]
  );

  const loadAdministrativeLevels = useCallback(async () => {
    try {
      setLoadingLocations(true);
      const response = await api.get("/administrative/levels");
      setAdministrativeLevels(response.data);
      setIsDataLoaded(true);

      const startIndex = 1;
      if (startIndex < response.data.length) {
        const startLevel = response.data[startIndex];
        await loadStartingLocations(startLevel, startIndex);
      }

      if (customer.administrative?.id) {
        await loadCustomerAdministrativeHierarchy(customer.administrative.id);
      }
    } catch (err) {
      console.error("Error loading administrative levels:", err);
    } finally {
      setLoadingLocations(false);
    }
  }, [customer, loadCustomerAdministrativeHierarchy, loadStartingLocations]);

  useEffect(() => {
    if (!isDataLoaded) {
      loadAdministrativeLevels();
    }
  }, [isDataLoaded, loadAdministrativeLevels]);

  const handleLocationChange = (levelIndex, locationId) => {
    const id = locationId ? parseInt(locationId) : null;

    setSelectedLocation((prev) => {
      const newState = { ...prev };
      newState[levelIndex] = id;

      for (let i = levelIndex + 1; i < administrativeLevels.length; i++) {
        delete newState[i];
      }
      return newState;
    });

    setAvailableLocations((prev) => {
      const newState = { ...prev };
      for (let i = levelIndex + 1; i < administrativeLevels.length; i++) {
        delete newState[i];
      }
      return newState;
    });

    if (id && levelIndex + 1 < administrativeLevels.length) {
      loadChildLocations(id, levelIndex + 1);
    }
  };

  const getLevelName = (levelIndex) => {
    return administrativeLevels[levelIndex] || "";
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const submitData = {
        full_name: formData.full_name.trim(),
        language: formData.language,
        crop_type: formData.crop_type || null,
        gender: formData.gender || null,
        age: formData.age ? parseInt(formData.age) : null,
      };

      // Add ward_id from the last selected location (ward level)
      const wardLevelIndex = 3; // Assuming Region(1), District(2), Ward(3)
      if (selectedLocation[wardLevelIndex]) {
        submitData.ward_id = selectedLocation[wardLevelIndex];
      }

      await api.put(`/customers/${customer.id}`, submitData);
      onCustomerUpdated();
    } catch (err) {
      console.error("Error updating customer:", err);
      setError(err.response?.data?.detail || "Failed to update customer");
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  return (
    <div className="fixed inset-0 bg-secondary-900/50 backdrop-blur-sm h-full w-full z-50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white/90 backdrop-blur-md w-full max-w-[32rem] animate-scale-in flex flex-col my-auto border border-gray-300 shadow-lg">
        <form onSubmit={handleSubmit} className="flex flex-col max-h-full">
          {/* Header - Fixed */}
          <div className="flex items-center justify-between p-8 pb-4 flex-shrink-0">
            <h3 className="text-lg font-medium text-gray-900">Edit Customer</h3>
            <button
              type="button"
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 cursor-pointer"
            >
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>

          {/* Scrollable Body */}
          <div className="flex-1 overflow-y-auto px-8 min-h-0">
            {error && (
              <div
                className="bg-red-50 border border-red-200 p-3 mb-4"
                style={{ borderRadius: "5px" }}
              >
                <div className="text-red-700 text-sm">{error}</div>
              </div>
            )}

            <div className="space-y-4 pb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Phone Number
                </label>
                <input
                  type="tel"
                  value={customer.phone_number}
                  disabled
                  className="w-full px-3 py-2 border border-gray-300 bg-gray-100 text-gray-500 cursor-not-allowed"
                  style={{ borderRadius: "5px" }}
                />
                <p className="text-xs text-gray-500 mt-1">
                  Phone number cannot be changed
                </p>
              </div>

              <div>
                <label
                  htmlFor="full_name"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Full Name
                </label>
                <input
                  type="text"
                  id="full_name"
                  name="full_name"
                  value={formData.full_name}
                  onChange={handleChange}
                  placeholder="Customer's full name"
                  className="w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                  style={{ borderRadius: "5px" }}
                />
              </div>

              <div>
                <label
                  htmlFor="language"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Preferred Language
                </label>
                <select
                  id="language"
                  name="language"
                  value={formData.language}
                  onChange={handleChange}
                  className="w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                  style={{ borderRadius: "5px" }}
                >
                  <option value="en">English</option>
                  <option value="sw">Swahili</option>
                </select>
              </div>

              {/* Crop type */}
              <div>
                <label
                  htmlFor="crop_type"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Crop Type
                </label>
                <select
                  id="crop_type"
                  name="crop_type"
                  value={formData.crop_type || ""}
                  onChange={handleChange}
                  className="w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                  style={{ borderRadius: "5px" }}
                >
                  <option value="">Select Crop Type</option>
                  {CROP_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
              </div>

              {/* Gender */}
              <div>
                <label
                  htmlFor="gender"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Gender
                </label>
                <select
                  id="gender"
                  name="gender"
                  value={formData.gender || ""}
                  onChange={handleChange}
                  className="w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                  style={{ borderRadius: "5px" }}
                >
                  <option value="">Select Gender</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                </select>
              </div>

              {/* Age  */}
              <div>
                <label
                  htmlFor="age"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Age
                </label>
                <input
                  type="number"
                  id="age"
                  name="age"
                  value={formData.age || ""}
                  onChange={handleChange}
                  placeholder="Customer's age"
                  className="w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                  style={{ borderRadius: "5px" }}
                />
              </div>

              {/* Cascade Administrative */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Administrative Location (Ward)
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
                            value={selectedLocation[1] || ""}
                            onChange={(e) =>
                              handleLocationChange(1, e.target.value)
                            }
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
                  </div>
                )}
              </div>

              <div className="bg-gray-50 p-3 rounded-md">
                <h4 className="text-sm font-medium text-gray-900 mb-2">
                  Customer Info
                </h4>
                <div className="text-sm text-gray-600 space-y-1">
                  <p>
                    <strong>ID:</strong> #{customer.id}
                  </p>
                  <p>
                    <strong>Created:</strong>{" "}
                    {new Date(customer.created_at).toLocaleDateString()}
                  </p>
                  {customer.updated_at &&
                    customer.updated_at !== customer.created_at && (
                      <p>
                        <strong>Last Updated:</strong>{" "}
                        {new Date(customer.updated_at).toLocaleDateString()}
                      </p>
                    )}
                </div>
              </div>
            </div>
          </div>

          {/* Footer - Fixed */}
          <div className="border-t border-gray-200 p-8 pt-4 bg-white/90 flex-shrink-0">
            <div className="flex space-x-3">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 bg-white py-2 px-4 bg-gray-50 focus:bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 cursor-pointer transition-colors duration-200"
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
                {loading ? "Updating..." : "Update Customer"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
