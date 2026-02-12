export interface TechnicalError {
  status?: number;
  code: string;
  message: string;
  hint?: string;
  cause?: unknown;
}

export class SevaUiError extends Error implements TechnicalError {
  status?: number;
  code: string;
  hint?: string;
  cause?: unknown;

  constructor(input: TechnicalError) {
    super(input.message);
    this.name = "SevaUiError";
    this.status = input.status;
    this.code = input.code;
    this.hint = input.hint;
    this.cause = input.cause;
  }
}

export function asTechnicalError(error: unknown): TechnicalError {
  if (error instanceof SevaUiError) {
    return {
      status: error.status,
      code: error.code,
      message: error.message,
      hint: error.hint,
      cause: error.cause
    };
  }

  if (error instanceof Error) {
    return {
      code: "ui.unexpected_error",
      message: error.message,
      cause: error
    };
  }

  return {
    code: "ui.unknown_error",
    message: String(error)
  };
}
