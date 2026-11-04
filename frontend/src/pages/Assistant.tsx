import { useEffect } from "react";
import { ChatFrame, PromptRail } from "../components/WellNestAI";

export function Assistant() {
  useEffect(() => { document.title = "WellNest AI — WellNest Hospitals"; }, []);
  return (
    <div className="assistant-page">
      <div className="wrap">
        <header className="assistant-intro">
          <h1 className="serif">Ask WellNest AI</h1>
          <p className="lead">
            Book, move or cancel a visit, check a lab report, ask what your insurance covers, or ask for a person.
            The same assistant answers here, on the phone and on the hospital's chat line.
          </p>
        </header>
        <div className="assistant-grid">
          <ChatFrame variant="page" />
          <PromptRail />
        </div>
      </div>
    </div>
  );
}
