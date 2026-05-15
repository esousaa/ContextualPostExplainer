export type ApiError = {
  error: string;
  message: string;
  status?: number;
};

export class ApiClientError extends Error {
  readonly error: string;
  readonly status?: number;

  constructor(payload: ApiError) {
    super(payload.message);
    this.name = "ApiClientError";
    this.error = payload.error;
    this.status = payload.status;
  }
}

export function normalizeApiError(error: unknown): ApiError {
  if (error instanceof ApiClientError) {
    return {
      error: error.error,
      message: error.message,
      status: error.status
    };
  }

  if (error instanceof DOMException && error.name === "AbortError") {
    return {
      error: "timeout",
      message: "The request took too long. Try again when the backend is available."
    };
  }

  if (error instanceof TypeError) {
    return {
      error: "network_error",
      message: "The backend could not be reached."
    };
  }

  if (error instanceof Error) {
    return {
      error: "unexpected_error",
      message: error.message
    };
  }

  return {
    error: "unexpected_error",
    message: "Unexpected frontend error."
  };
}
