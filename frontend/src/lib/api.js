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
    return `/api${cleanUrl}`;
  };

  // Add response interceptor to handle authentication errors and token refresh
  axiosInstance.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config;
      
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;
        
        // Don't try to refresh if this is already a refresh request
        if (originalRequest.url?.includes('/auth/refresh') || originalRequest.url?.includes('/auth/login')) {
          if (typeof window !== 'undefined' && window.clearUserSession) {
            window.clearUserSession();
          }
          if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
            window.location.href = '/';
          }
          return Promise.reject(error);
        }
        
        // Try to refresh the access token
        try {
          if (typeof window !== 'undefined' && window.refreshAccessToken) {
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
          if (typeof window !== 'undefined' && window.clearUserSession) {
            window.clearUserSession();
          }
          if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
            window.location.href = '/';
          }
          return Promise.reject(refreshError);
        }
      }
      
      // For other 401/403 errors or if refresh is not available, clear session
      if (error.response?.status === 401 || error.response?.status === 403) {
        if (typeof window !== 'undefined' && window.clearUserSession) {
          window.clearUserSession();
        }
        if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
          window.location.href = '/';
        }
      }
      
      return Promise.reject(error);
    }
  );

  return {
    get: (url, requestConfig = {}) =>
      axiosInstance.get(buildUrl(url), {
        ...getConfig(),
        ...requestConfig,
      }),
    post: (url, data, requestConfig = {}) =>
      axiosInstance.post(buildUrl(url), data, {
        ...getConfig(),
        ...requestConfig,
      }),
    put: (url, data, requestConfig = {}) =>
      axiosInstance.put(buildUrl(url), data, {
        ...getConfig(),
        ...requestConfig,
      }),
    patch: (url, data, requestConfig = {}) =>
      axiosInstance.patch(buildUrl(url), data, {
        ...getConfig(),
        ...requestConfig,
      }),
    delete: (url, requestConfig = {}) =>
      axiosInstance.delete(buildUrl(url), {
        ...getConfig(),
        ...requestConfig,
      }),
    setToken: (token) => {
      api.token = token;
    },
  };
};

const api = API();

export default api;
