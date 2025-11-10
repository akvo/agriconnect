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

  // Get list of documents by kbId with pagination and search
  getDocumentList: async (kbId = null, page = 1, size = 10, search = null) => {
    let url = `/documents?kb_id=${kbId}&page=${page}&size=${size}`;
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

  // Upload a document to a specific knowledge base
  uploadDocument: async (formData) => {
    const config = {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    };
    try {
      const response = await api.post(`/documents`, formData, config);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // update document metadata
  updateDocument: async (id, data) => {
    try {
      const response = await api.put(`/documents/${id}`, data);
      return response.data;
    } catch (error) {
      throw error;
    }
  },
};

export default knowledgeBaseApi;
