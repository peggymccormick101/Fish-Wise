import { Link, Route, Routes } from "react-router-dom";
import Home from "./pages/Home.jsx";
import SearchDetail from "./pages/SearchDetail.jsx";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/" className="brand">
          🎣 FishWise
        </Link>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/searches/:id" element={<SearchDetail />} />
        </Routes>
      </main>
    </div>
  );
}
