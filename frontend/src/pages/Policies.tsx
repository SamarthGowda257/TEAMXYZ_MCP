import { useEffect, useState } from "react";
import { ChevronDown, Link2 } from "lucide-react";
import { api } from "../lib/api";
import { ChatCta } from "../components/WellNestAI";

type Policy = { id: string; title: string; body: string };

/**
 * Hospital policies, read from /api/policies — the same passages the Info agent reads out on chat and voice.
 * One source means the website and the phone line can never contradict each other.
 */
export function Policies() {
  const [list, setList] = useState<Policy[] | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Hospital policies — WellNest Hospitals";
    api<{ policies: Policy[] }>("/api/policies")
      .then((d) => {
        setList(d.policies);
        const hash = window.location.hash.replace("#", "");
        if (hash && d.policies.some((p) => p.id === hash)) setOpen(hash);
        else if (d.policies.length) setOpen(d.policies[0].id);
      })
      .catch(() => setError("We couldn't load the policies just now. Please call the hospital, or try again shortly."));
  }, []);

  return (
    <div className="pol-page">
      <div className="wrap">
        <header className="pol-head">
          <h1 className="serif">Hospital policies</h1>
          <p className="lead">
            The rules our front desk works to, in the words our assistant uses. Ask WellNest AI about any of them
            on chat or on the phone and you will hear exactly what you read here.
          </p>
        </header>

        {error && <p className="error-text">{error}</p>}

        {!list && !error && <div className="pol-skel">{Array.from({ length: 6 }, (_, i) => <i key={i} />)}</div>}

        {list && (
          <>
            <nav className="pol-jump" aria-label="Policies">
              {list.map((p) => (
                <a key={p.id} href={`#${p.id}`} onClick={() => setOpen(p.id)}>{p.title}</a>
              ))}
            </nav>

            <ul className="pol-list">
              {list.map((p) => {
                const isOpen = open === p.id;
                return (
                  <li key={p.id} id={p.id} className={isOpen ? "is-open" : ""}>
                    <h2>
                      <button type="button" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : p.id)}>
                        <span>{p.title}</span>
                        <ChevronDown size={20} aria-hidden="true" />
                      </button>
                    </h2>
                    {isOpen && (
                      <div className="pol-body">
                        <p>{p.body}</p>
                        <a className="pol-anchor" href={`#${p.id}`}><Link2 size={14} aria-hidden="true" /> Link to this policy</a>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>

            <div className="pol-ask">
              <div>
                <h2>Something not covered here?</h2>
                <p>Ask the assistant. If it can't answer, it will pass you to someone at the hospital.</p>
              </div>
              <ChatCta label="Ask WellNest AI" />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
