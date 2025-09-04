import axios from "axios";

export const config = {
  baseURL: "",
  headers: {
    "Content-Type": "application/json",
  },
};

const API = () => {
  const getConfig = () => {
    return api?.token
      ? {
          ...config,
          headers: {
            ...config.headers,
            Authorization: `Bearer ${api.token}`,
          },
        }
      : config;
  };
  
  const buildUrl = (url) => {
    // URLs should start with /api for the backend
    const cleanUrl = url.startsWith('/') ? url : `/${url}`;
    return `/api${cleanUrl}`;
  };

  return {
    get: (url, requestConfig = {}) => axios.get(buildUrl(url), {
      ...getConfig(),
      ...requestConfig 
    }),
    post: (url, data, requestConfig = {}) => axios.post(buildUrl(url), data, {
      ...getConfig(),
      ...requestConfig 
    }),
    put: (url, data, requestConfig = {}) => axios.put(buildUrl(url), data, {
      ...getConfig(),
      ...requestConfig 
    }),
    patch: (url, data, requestConfig = {}) => axios.patch(buildUrl(url), data, {
      ...getConfig(),
      ...requestConfig 
    }),
    delete: (url, requestConfig = {}) => axios.delete(buildUrl(url), {
      ...getConfig(),
      ...requestConfig 
    }),
    setToken: (token) => {
      api.token = token;
    },
  };
};

const api = API();

export default api;