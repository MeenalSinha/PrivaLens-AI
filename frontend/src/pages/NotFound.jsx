import { Link } from "react-router-dom";
import { Button } from "../components/UI.jsx";

export default function NotFound() {
  return (
    <div className="px-8 py-24 flex flex-col items-center text-center">
      <div className="text-text-muted font-mono text-sm mb-3">404</div>
      <h1 className="font-display text-2xl font-semibold text-text-primary mb-2">Page not found</h1>
      <p className="text-text-secondary text-sm max-w-sm mb-6">
        That page doesn't exist. It may have moved, or the link was mistyped.
      </p>
      <Link to="/"><Button>Back to Home</Button></Link>
    </div>
  );
}
