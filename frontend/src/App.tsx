import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import SourceForm from "./pages/SourceForm";
import DigestPreview from "./pages/DigestPreview";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <nav style={{ padding: "12px 24px", borderBottom: "1px solid #ddd", display: "flex", gap: "16px" }}>
        <NavLink to="/" end style={({ isActive }) => ({ fontWeight: isActive ? "bold" : undefined })}>
          ダッシュボード
        </NavLink>
        <NavLink to="/settings" style={({ isActive }) => ({ fontWeight: isActive ? "bold" : undefined })}>
          設定
        </NavLink>
      </nav>
      <main style={{ padding: "24px" }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/sources/new" element={<SourceForm />} />
          <Route path="/sources/:id/edit" element={<SourceForm />} />
          <Route path="/sources/:id/preview" element={<DigestPreview />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
