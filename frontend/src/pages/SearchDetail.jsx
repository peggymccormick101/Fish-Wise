import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import TechniqueList from "../components/TechniqueList.jsx";
import GearList from "../components/GearList.jsx";
import { deleteSearch, getSearch } from "../api.js";

export default function SearchDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [search, setSearch] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    getSearch(id)
      .then(setSearch)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleDelete() {
    if (!window.confirm(`Delete this search for ${search.species}?`)) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteSearch(id);
      navigate("/");
    } catch (e) {
      setError(e.message);
      setDeleting(false);
    }
  }

  if (loading) return <p>Loading...</p>;
  if (error) return <p className="error">{error}</p>;
  if (!search) return null;

  return (
    <div className="search-detail">
      <div className="search-detail-header">
        <Link to="/" className="back-link">
          ← All searches
        </Link>
        <button type="button" className="delete-button" onClick={handleDelete} disabled={deleting}>
          {deleting ? "Deleting…" : "Delete search"}
        </button>
      </div>

      <h1>{search.species}</h1>
      <p className="search-subheading">
        {search.water_body_normalized || search.water_body} · {search.season}
      </p>

      {search.summary && (
        <div className="search-summary">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{search.summary}</ReactMarkdown>
        </div>
      )}

      {search.best_conditions && (
        <div className="best-conditions">
          <strong>Best conditions:</strong>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{search.best_conditions}</ReactMarkdown>
        </div>
      )}

      <section>
        <h2>Recommended gear</h2>
        <GearList items={search.gear_items} />
      </section>

      <section>
        <h2>Techniques</h2>
        <TechniqueList techniques={search.techniques} />
      </section>
    </div>
  );
}
