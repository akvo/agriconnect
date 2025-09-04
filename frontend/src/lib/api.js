import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api";

const api = axios.create({
	baseURL: API_BASE_URL,
	headers: {
		"Content-Type": "application/json",
	},
});

// Add request interceptor to include auth token
api.interceptors.request.use((config) => {
	const token = localStorage.getItem("token");
	if (token) {
		config.headers.Authorization = `Bearer ${token}`;
	}
	return config;
});

// Add response interceptor to handle auth errors
api.interceptors.response.use(
	(response) => response,
	(error) => {
		if (error.response?.status === 401) {
			localStorage.removeItem("token");
			localStorage.removeItem("user");
			window.location.href = "/login";
		}
		return Promise.reject(error);
	}
);

export const authAPI = {
	register: (userData) => api.post("/auth/register", userData),
	login: (credentials) => api.post("/auth/login", credentials),
};

export default api;