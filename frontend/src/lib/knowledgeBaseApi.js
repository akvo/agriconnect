import api from "./api";

const knowledgeBaseApi = {
  // Create a new knowledge base entry with file upload
  create: async (formData) => {
    // For FormData, we need to exclude Content-Type to let axios handle it
    const config = {
      headers: {
        // Explicitly remove Content-Type for FormData uploads
        "Content-Type": undefined,
      },
    };

    try {
      const response = await api.post("/kb", formData, config);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Get list of knowledge bases with pagination and search
  getList: async (page = 1, size = 10, search = null) => {
    let url = `/kb?page=${page}&size=${size}`;
    if (search) {
      url += `&search=${encodeURIComponent(search)}`;
    }
    try {
      const response = await api.get(url);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Get a specific knowledge base by ID
  getById: async (id) => {
    const response = await api.get(`/kb/${id}`);
    return response.data;
  },

  // Update knowledge base metadata
  update: async (id, data) => {
    const response = await api.put(`/kb/${id}`, data);
    return response.data;
  },

  // Delete knowledge base
  delete: async (id) => {
    const response = await api.delete(`/kb/${id}`);
    return response.data;
  },

  // Update knowledge base status
  updateStatus: async (id, status) => {
    const response = await api.patch(`/kb/${id}/status`, { status });
    return response.data;
  },
};

export default knowledgeBaseApi;
