import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', fontFamily: 'system-ui', maxWidth: '600px', margin: '0 auto' }}>
          <h2 style={{ color: '#dc2626' }}>Fehler beim Laden</h2>
          <p>{this.state.error?.message}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{ padding: '0.5rem 1rem', marginTop: '1rem', cursor: 'pointer' }}
          >
            Seite neu laden
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
