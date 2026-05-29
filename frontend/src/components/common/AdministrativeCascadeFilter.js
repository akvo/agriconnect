"use client";

import { useState, useEffect, useCallback } from "react";
import { MapPinIcon, XMarkIcon } from "@heroicons/react/24/outline";
import api from "../../lib/api";

export default function AdministrativeCascadeFilter({
  onChange,
  initialAdministrativeId = null,
  showClearButton = true,
}) {
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

  const loadAdministrativeHierarchy = useCallback(
    async (administrativeId, levels) => {
      try {
        const response = await api.get(`/administrative/${administrativeId}`);
        const admin = response.data;

        const getLevelIndex = (levelName) => {
          return levels.findIndex(
            (l) => l.toLowerCase() === levelName.toLowerCase()
          );
        };

        let currentId = admin.parent_id;
        const levelIndex = getLevelIndex(admin.level.name);

        const selectedAdmins = {
          [levelIndex]: admin.id,
        };

        while (currentId) {
          const ancestorResponse = await api.get(
            `/administrative/${currentId}`
          );
          const ancestor = ancestorResponse.data;
          const ancestorLevelIndex = getLevelIndex(ancestor.level.name);
          if (ancestorLevelIndex + 1 < levels.length) {
            await loadChildLocations(ancestor.id, ancestorLevelIndex + 1);
          }
          selectedAdmins[ancestorLevelIndex] = ancestor.id;
          currentId = ancestor.parent_id;
        }
        setSelectedLocation(selectedAdmins);
      } catch (err) {
        console.error("Error loading administrative hierarchy:", err);
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

      if (initialAdministrativeId) {
        await loadAdministrativeHierarchy(
          initialAdministrativeId,
          response.data
        );
      }
    } catch (err) {
      console.error("Error loading administrative levels:", err);
    } finally {
      setLoadingLocations(false);
    }
  }, [
    initialAdministrativeId,
    loadAdministrativeHierarchy,
    loadStartingLocations,
  ]);

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

    // Notify parent of selection change
    // Find the deepest selected level
    const deepestSelectedId =
      id || findDeepestSelectedId(selectedLocation, levelIndex);
    if (onChange) {
      onChange({
        administrativeId: deepestSelectedId,
        levelIndex: id ? levelIndex : levelIndex - 1,
        selectedLocation: { ...selectedLocation, [levelIndex]: id },
      });
    }
  };

  const findDeepestSelectedId = (locations, maxLevel) => {
    for (let i = maxLevel - 1; i >= 1; i--) {
      if (locations[i]) return locations[i];
    }
    return null;
  };

  const handleClear = () => {
    setSelectedLocation({});
    setAvailableLocations((prev) => {
      const newState = {};
      if (prev[1]) {
        newState[1] = prev[1];
      }
      return newState;
    });
    if (onChange) {
      onChange({
        administrativeId: null,
        levelIndex: null,
        selectedLocation: {},
      });
    }
  };

  const getLevelName = (levelIndex) => {
    return administrativeLevels[levelIndex] || "";
  };

  const hasSelection = Object.values(selectedLocation).some((v) => v);

  if (loadingLocations) {
    return (
      <div className="flex items-center space-x-2 text-sm text-gray-500">
        <MapPinIcon className="h-5 w-5 animate-pulse" />
        <span>Loading locations...</span>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center text-gray-600">
        <MapPinIcon className="h-5 w-5 mr-1" />
        <span className="text-sm font-medium">Filter by Location:</span>
      </div>

      {/* Region dropdown (level 1) */}
      {administrativeLevels.length > 1 && availableLocations[1] && (
        <select
          value={selectedLocation[1] || ""}
          onChange={(e) => handleLocationChange(1, e.target.value)}
          className="px-3 py-1.5 text-sm bg-gray-50 border border-gray-300 focus:bg-white focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500"
          style={{ borderRadius: "5px" }}
        >
          <option value="">All {getLevelName(1)}s</option>
          {availableLocations[1].map((location) => (
            <option key={location.id} value={location.id}>
              {location.name}
            </option>
          ))}
        </select>
      )}

      {/* District dropdown (level 2) */}
      {selectedLocation[1] && availableLocations[2] && (
        <select
          value={selectedLocation[2] || ""}
          onChange={(e) => handleLocationChange(2, e.target.value)}
          className="px-3 py-1.5 text-sm bg-gray-50 border border-gray-300 focus:bg-white focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500"
          style={{ borderRadius: "5px" }}
        >
          <option value="">All {getLevelName(2)}s</option>
          {availableLocations[2].map((location) => (
            <option key={location.id} value={location.id}>
              {location.name}
            </option>
          ))}
        </select>
      )}

      {/* Ward dropdown (level 3) */}
      {selectedLocation[2] && availableLocations[3] && (
        <select
          value={selectedLocation[3] || ""}
          onChange={(e) => handleLocationChange(3, e.target.value)}
          className="px-3 py-1.5 text-sm bg-gray-50 border border-gray-300 focus:bg-white focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500"
          style={{ borderRadius: "5px" }}
        >
          <option value="">All {getLevelName(3)}s</option>
          {availableLocations[3].map((location) => (
            <option key={location.id} value={location.id}>
              {location.name}
            </option>
          ))}
        </select>
      )}

      {/* Clear button */}
      {showClearButton && hasSelection && (
        <button
          onClick={handleClear}
          className="flex items-center px-2 py-1.5 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 transition-colors"
          style={{ borderRadius: "5px" }}
        >
          <XMarkIcon className="h-4 w-4 mr-1" />
          Clear
        </button>
      )}
    </div>
  );
}
