import { TechnicalError } from "../domain/errors";

interface TechnicalErrorPanelProps {
  error?: TechnicalError;
}

export function TechnicalErrorPanel({ error }: TechnicalErrorPanelProps) {
  if (!error) {
    return null;
  }
  return (
    <div className="panel panel-error">
      <h4>Technical Error</h4>
      <p>
        <strong>Code:</strong> <code>{error.code}</code>
      </p>
      {typeof error.status === "number" ? (
        <p>
          <strong>Status:</strong> {error.status}
        </p>
      ) : null}
      <p>
        <strong>Message:</strong> {error.message}
      </p>
      {error.hint ? (
        <p>
          <strong>Hint:</strong> {error.hint}
        </p>
      ) : null}
    </div>
  );
}
