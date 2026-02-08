// API Clients for AI Video Factory
// - Next.js API Routes: Database operations (channels, videos, characters)
// - Python FastAPI: AI generation tasks (scripts, images, videos)

const PYTHON_API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    // FastAPI returns validation errors as an array in error.detail
    let message: string;
    if (Array.isArray(error.detail)) {
      message = error.detail.map((e: { msg?: string; message?: string }) => e.msg || e.message || JSON.stringify(e)).join(', ');
    } else if (typeof error.detail === 'object') {
      message = JSON.stringify(error.detail);
    } else {
      message = error.detail || error.message || error.error || 'Request failed';
    }
    throw new ApiError(response.status, message);
  }
  return response.json();
}

// ============================================
// Next.js API Client (Database Operations)
// ============================================
export const db = {
  async get<T>(endpoint: string): Promise<T> {
    const response = await fetch(`/api${endpoint}`, {
      headers: { 'Content-Type': 'application/json' },
    });
    return handleResponse<T>(response);
  },

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    const response = await fetch(`/api${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: data ? JSON.stringify(data) : undefined,
    });
    return handleResponse<T>(response);
  },

  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    const response = await fetch(`/api${endpoint}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: data ? JSON.stringify(data) : undefined,
    });
    return handleResponse<T>(response);
  },

  async delete<T>(endpoint: string): Promise<T> {
    const response = await fetch(`/api${endpoint}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
    });
    return handleResponse<T>(response);
  },
};

// ============================================
// Python FastAPI Client (AI Generation Tasks)
// ============================================
export const ai = {
  async get<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${PYTHON_API_BASE}${endpoint}`, {
      headers: { 'Content-Type': 'application/json' },
    });
    return handleResponse<T>(response);
  },

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    const response = await fetch(`${PYTHON_API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: data ? JSON.stringify(data) : undefined,
    });
    return handleResponse<T>(response);
  },

  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    const response = await fetch(`${PYTHON_API_BASE}${endpoint}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: data ? JSON.stringify(data) : undefined,
    });
    return handleResponse<T>(response);
  },

  async delete<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${PYTHON_API_BASE}${endpoint}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
    });
    return handleResponse<T>(response);
  },
};

// Legacy export for backwards compatibility
export const api = ai;

export { ApiError };
