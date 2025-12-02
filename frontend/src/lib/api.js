import axios from "axios";

const defaultConfig = {
  baseURL: "",
  headers: {
    "Content-Type": "application/json",
  },
};

const API = () => {
  const axiosInstance = axios.create();

  const getConfig = () => {
    return api?.token
      ? {
          ...defaultConfig,
          headers: {
            ...defaultConfig.headers,
            Authorization: `Bearer ${api.token}`,
          },
        }
      : defaultConfig;
  };

  const buildUrl = (url) => {
    // URLs should start with /api for the backend
    const cleanUrl = url.startsWith("/") ? url : `/${url}`;
    const apiUrl = `/api${cleanUrl}`;
    // Ensure trailing slash is preserved if present in original URL
    return apiUrl;
  };

  // Add response interceptor to handle authentication errors and token refresh
  axiosInstance.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config;

      // Only handle auth errors for actual API calls, not navigation
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;

        // Don't try to refresh if this is already a refresh request
        if (
          originalRequest.url?.includes("/auth/refresh") ||
          originalRequest.url?.includes("/auth/login")
        ) {
          if (typeof window !== "undefined" && window.clearUserSession) {
            window.clearUserSession();
          }
          // Only redirect if we're not already on login page
          if (
            typeof window !== "undefined" &&
            !window.location.pathname.includes("/login") &&
            window.location.pathname !== "/"
          ) {
            window.location.href = "/";
          }
          return Promise.reject(error);
        }

        // Try to refresh the access token
        try {
          if (typeof window !== "undefined" && window.refreshAccessToken) {
            const newAccessToken = await window.refreshAccessToken();

            // Update the original request with new token
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
            }

            // Retry the original request
            return axiosInstance(originalRequest);
          }
        } catch (refreshError) {
          // Refresh failed, clear user session and redirect
          if (typeof window !== "undefined" && window.clearUserSession) {
            window.clearUserSession();
          }
          // Only redirect if we're not already on login page and this was a user-initiated request
          if (
            typeof window !== "undefined" &&
            !window.location.pathname.includes("/login") &&
            window.location.pathname !== "/" &&
            // Only redirect for auth-related endpoints or profile requests
            (originalRequest.url?.includes("/auth/") ||
              originalRequest.url?.includes("/profile") ||
              originalRequest.url?.includes("/admin/") ||
              originalRequest.url?.includes("/customers/") ||
              originalRequest.url?.includes("/kb/"))
          ) {
            window.location.href = "/";
          }
          return Promise.reject(refreshError);
        }
      }

      // For other 401/403 errors, only clear session and redirect if it's an auth-related request
      if (error.response?.status === 401 || error.response?.status === 403) {
        // Only handle auth errors for actual authenticated endpoints
        if (
          originalRequest.url?.includes("/auth/") ||
          originalRequest.url?.includes("/profile") ||
          originalRequest.url?.includes("/admin/") ||
          originalRequest.url?.includes("/customers/") ||
          originalRequest.url?.includes("/kb/")
        ) {
          if (typeof window !== "undefined" && window.clearUserSession) {
            window.clearUserSession();
          }
          if (
            typeof window !== "undefined" &&
            !window.location.pathname.includes("/login") &&
            window.location.pathname !== "/"
          ) {
            window.location.href = "/";
          }
        }
      }

      return Promise.reject(error);
    }
  );

  return {
    get: (url, requestConfig = {}) => {
      const baseConfig = getConfig();
      return axiosInstance.get(buildUrl(url), {
        ...baseConfig,
        ...requestConfig,
        headers: {
          ...baseConfig.headers,
          ...requestConfig.headers,
        },
      });
    },
    post: (url, data, requestConfig = {}) => {
      const baseConfig = getConfig();
      let headers = { ...baseConfig.headers, ...requestConfig.headers };
      // Remove default Content-Type if sending FormData
      if (data instanceof FormData) {
        delete headers["Content-Type"];
      }
      const finalConfig = {
        ...baseConfig,
        ...requestConfig,
        headers,
      };
      return axiosInstance.post(buildUrl(url), data, finalConfig);
    },
    put: (url, data, requestConfig = {}) => {
      const baseConfig = getConfig();
      return axiosInstance.put(buildUrl(url), data, {
        ...baseConfig,
        ...requestConfig,
        headers: {
          ...baseConfig.headers,
          ...requestConfig.headers,
        },
      });
    },
    patch: (url, data, requestConfig = {}) => {
      const baseConfig = getConfig();
      return axiosInstance.patch(buildUrl(url), data, {
        ...baseConfig,
        ...requestConfig,
        headers: {
          ...baseConfig.headers,
          ...requestConfig.headers,
        },
      });
    },
    delete: (url, requestConfig = {}) => {
      const baseConfig = getConfig();
      return axiosInstance.delete(buildUrl(url), {
        ...baseConfig,
        ...requestConfig,
        headers: {
          ...baseConfig.headers,
          ...requestConfig.headers,
        },
      });
    },
    setToken: (token) => {
      api.token = token;
    },
  };
};

const api = API();

export default api;
