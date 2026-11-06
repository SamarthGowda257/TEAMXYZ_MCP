import { Component, type ErrorInfo, type ReactNode } from "react";

/*
  A render error anywhere under here unmounts the whole React tree, which paints an empty page
  and tells the person nothing. The staff console is the worst place for that: it looks identical
  to a failed login. This catches the error, says so plainly, and offers the two things that
  actually recover — reload, and reload bypassing the cache.
*/
type Props = { children: ReactNode };
type State = { err: Error | null };

export class Boundary extends Component<Props, State> {
  state: State = { err: null };

  static getDerivedStateFromError(err: Error): State {
    return { err };
  }

  componentDidCatch(err: Error, info: ErrorInfo) {
    // Keep it in the console for whoever is debugging; there is no error reporting service here.
    console.error("WellNest render error:", err, info.componentStack);
  }

  render() {
    if (!this.state.err) return this.props.children;
    return (
      <div className="boom">
        <div className="boom-card">
          <h1>This screen didn&apos;t load</h1>
          <p>
            Something went wrong rendering this page. Nothing you were doing has been lost — the
            hospital record is on the server, not in this window.
          </p>
          <p className="boom-why">{this.state.err.message}</p>
          <div className="boom-acts">
            <button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>
              Reload the page
            </button>
            <button
              type="button"
              className="btn btn-quiet"
              onClick={() => {
                // a stale cached bundle is the most common cause, so offer the cache-skipping path
                try { sessionStorage.clear(); } catch { /* private mode */ }
                window.location.href = window.location.pathname + "?r=" + Date.now();
              }}
            >
              Reload without the cache
            </button>
          </div>
        </div>
      </div>
    );
  }
}
