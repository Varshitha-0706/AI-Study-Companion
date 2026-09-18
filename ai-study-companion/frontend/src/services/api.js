/**
 * Central API client for AI Study Companion.
 * Automatically injects JWT Bearer tokens and handles error responses.
 */

const API_BASE = '/api/v1';

export const getAuthToken = () => localStorage.getItem('asc_token');
export const setAuthToken = (token) => localStorage.setItem('asc_token', token);
export const removeAuthToken = () => {
  localStorage.removeItem('asc_token');
  localStorage.removeItem('asc_user');
};

export const getCurrentUserLocal = () => {
  const user = localStorage.getItem('asc_user');
  return user ? JSON.parse(user) : null;
};

export const setCurrentUserLocal = (user) => {
  localStorage.setItem('asc_user', JSON.stringify(user));
};

async function request(path, options = {}) {
  const token = getAuthToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Handle FormData (don't override Content-Type)
  if (options.body instanceof FormData) {
    delete headers['Content-Type'];
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    // If not on login, clear token
    if (!path.includes('/auth/login') && !path.includes('/auth/register')) {
      removeAuthToken();
      window.dispatchEvent(new Event('auth:unauthorized'));
    }
  }

  if (response.status === 204) {
    return null;
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const errorMsg = data.detail || response.statusText || 'An unexpected error occurred';
    throw new Error(errorMsg);
  }

  return data;
}

// ──────────────────────────────────────────────
// API Modules
// ──────────────────────────────────────────────

export const authApi = {
  login: async (email, password) => {
    const data = await request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setAuthToken(data.access_token);
    setCurrentUserLocal({ id: data.user_id, display_name: data.display_name, role: data.role });
    return data;
  },
  register: async (email, password, display_name) => {
    const data = await request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name }),
    });
    setAuthToken(data.access_token);
    setCurrentUserLocal({ id: data.user_id, display_name: data.display_name, role: data.role });
    return data;
  },
  getMe: () => request('/auth/me'),
};

export const spacesApi = {
  list: () => request('/spaces'),
  get: (id) => request(`/spaces/${id}`),
  create: (body) => request('/spaces', { method: 'POST', body: JSON.stringify(body) }),
  update: (id, body) => request(`/spaces/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id) => request(`/spaces/${id}`, { method: 'DELETE' }),
};

export const projectsApi = {
  list: (spaceId) => request(`/spaces/${spaceId}/projects`),
  get: (projectId) => request(`/projects/${projectId}`),
  getDashboard: (projectId) => request(`/projects/${projectId}/dashboard`),
  create: (spaceId, body) => request(`/spaces/${spaceId}/projects`, { method: 'POST', body: JSON.stringify(body) }),
  update: (spaceId, projectId, body) => request(`/spaces/${spaceId}/projects/${projectId}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (spaceId, projectId) => request(`/spaces/${spaceId}/projects/${projectId}`, { method: 'DELETE' }),
};

export const materialsApi = {
  list: (projectId) => request(`/materials?project_id=${projectId}`),
  get: (materialId) => request(`/materials/${materialId}`),
  upload: (projectId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return request(`/materials/upload?project_id=${projectId}`, {
      method: 'POST',
      body: formData,
    });
  },
  getChunks: (materialId) => request(`/materials/${materialId}/chunks`),
};

export const tutorApi = {
  getHistory: (projectId) => request(`/tutor/projects/${projectId}/history`),
  sendMessage: (projectId, message) => request(`/tutor/projects/${projectId}/chat`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  }),
  clearHistory: (projectId) => request(`/tutor/projects/${projectId}/history`, { method: 'DELETE' }),
};

export const quizApi = {
  startAdaptiveQuiz: (projectId, questionCount = 5) => request(`/quiz/start?project_id=${projectId}&question_count=${questionCount}`, {
    method: 'POST',
  }),
  getQuiz: (quizId) => request(`/quiz/${quizId}`),
  submitAnswer: (quizId, questionId, selectedOption, openEndedAnswer) => request(`/quiz/${quizId}/answer`, {
    method: 'POST',
    body: JSON.stringify({
      question_id: questionId,
      selected_option: selectedOption,
      open_ended_answer: openEndedAnswer,
    }),
  }),
  completeQuiz: (quizId) => request(`/quiz/${quizId}/complete`, { method: 'POST' }),
};

export const masteryApi = {
  getOverview: (projectId) => request(`/mastery/projects/${projectId}/overview`),
  getHistory: (projectId, conceptId) => request(`/mastery/projects/${projectId}/history${conceptId ? `?concept_id=${conceptId}` : ''}`),
  getRecommendations: (projectId) => request(`/mastery/projects/${projectId}/recommendations`),
  getGrowth: (projectId) => request(`/mastery/projects/${projectId}/growth`),
  getContext: (projectId) => request(`/mastery/projects/${projectId}/context`),
};

export const adminApi = {
  getOverview: () => request('/admin/overview'),
  getUsers: (skip = 0, limit = 50) => request(`/admin/users?skip=${skip}&limit=${limit}`),
  getActivity: (limit = 50) => request(`/admin/activity?limit=${limit}`),
  getAiStats: () => request('/admin/ai-stats'),
  getJobs: () => request('/admin/jobs'),
  getHealth: () => request('/admin/health'),
};
