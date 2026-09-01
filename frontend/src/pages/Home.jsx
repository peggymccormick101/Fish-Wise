import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import WaterBodySearchForm from "../components/WaterBodySearchForm.jsx";
import { deleteSearch, listSearches } from "../api.js";
import heroImg from "../fishwise.png";

export default function Home() {
  const [searches, setSearches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    listSearches()
      .then(setSearches)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  function handleCreated(search) {
    navigate(`/searches/${search.id}`);
  }

  async function handleDelete(e, search) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(`Delete this search for ${search.species} at ${search.water_body}?`)) return;
    setDeletingId(search.id);
    setError(null);
    try {
      await deleteSearch(search.id);
      setSearches((prev) => prev.filter((s) => s.id !== search.id));
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="home-page">
      <div className="hero-section">
        <img
          src={heroImg}
          alt="FishWise — find your fishing spot"
          className="hero-illustration hero-photo"
        />
        <WaterBodySearchForm onCreated={handleCreated} />
      </div>
      {error && <p className="error">{error}</p>}

      <section className="search-list-section">
        <h2>Your searches</h2>
        {loading && <p>Loading...</p>}
        {!loading && searches.length === 0 && <p>No searches yet — find a fishing spot above.</p>}
        <ul className="search-list">
          {searches.map((s) => (
            <li key={s.id}>
              <a
                className="search-link"
                href={`/searches/${s.id}`}
                onClick={(e) => { e.preventDefault(); navigate(`/searches/${s.id}`); }}
              >
                <span className="search-title">
                  {s.species} — {s.water_body_normalized || s.water_body}
                </span>
                <span className="search-meta">{s.season}</span>
              </a>
              <button
                type="button"
                className="delete-button"
                onClick={(e) => handleDelete(e, s)}
                disabled={deletingId === s.id}
                aria-label={`Delete search for ${s.species} at ${s.water_body}`}
              >
                {deletingId === s.id ? "Deleting…" : "Delete"}
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
