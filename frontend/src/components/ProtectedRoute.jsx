import { Navigate } from "react-router-dom";
import { isAuthenticated } from "../lib/auth";

export function ProtectedRoute({ children }) {
  if (!isAuthenticated()) return <Navigate to="/login" replace />;
  return children;
}

