import { useState } from "react";
import { createSearch, lookupWaterBody } from "../api.js";

const SEASONS = ["Spring", "Summer", "Fall", "Winter"];

function currentSeason() {
  const month = new Date().getMonth(); // 0-11
  if (month >= 2 && month <= 4) return "Spring";
  if (month >= 5 && month <= 7) return "Summer";
  if (month >= 8 && month <= 10) return "Fall";
  return "Winter";
}

export default function WaterBodySearchForm({ onCreated }) {
  const [waterBody, setWaterBody] = useState("");
  const [lookup, setLookup] = useState(null);
  const [selectedSpecies, setSelectedSpecies] = useState("");
  const [season, setSeason] = useState(currentSeason());
  const [findingWater, setFindingWater] = useState(false);
  const [gettingTips, setGettingTips] = useState(false);
  const [error, setError] = useState(null);

  async function handleFind(e) {
    e.preventDefault();
    if (!waterBody.trim()) return;
    setFindingWater(true);
    setError(null);
    setLookup(null);
    setSelectedSpecies("");
    try {
      const result = await lookupWaterBody(waterBody.trim());
      setLookup(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setFindingWater(false);
    }
  }

  async function handleGetTips() {
    if (!selectedSpecies || !season) return;
    setGettingTips(true);
    setError(null);
    try {
      const search = await createSearch({
        water_body: waterBody.trim(),
        water_body_normalized: lookup.water_body_normalized,
        species: selectedSpecies,
        season,
      });
      onCreated(search);
    } catch (e) {
      setError(e.message);
    } finally {
      setGettingTips(false);
    }
  }

  return (
    <div className="water-search">
      <h2>Find your fishing spot</h2>
      <form className="water-body-form" onSubmit={handleFind}>
        <label>
          Body of water
          <input
            type="text"
            placeholder="e.g. Lake Travis, TX"
            value={waterBody}
            onChange={(e) => setWaterBody(e.target.value)}
            required
          />
        </label>
        <button type="submit" disabled={findingWater || !waterBody.trim()}>
          {findingWater ? "Finding..." : "Find it"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {lookup && (
        <div className="lookup-result">
          <p className="water-body-confirmed">📍 {lookup.water_body_normalized}</p>

          {(lookup.temperature_f != null || lookup.sunrise) && (
            <p className="conditions-now">
              {lookup.temperature_f != null && (
                <span>🌡️ {Math.round(lookup.temperature_f)}°F</span>
              )}
              {lookup.wind_mph != null && (
                <span> · 💨 {Math.round(lookup.wind_mph)} mph</span>
              )}
              {lookup.sunrise && <span> · 🌅 {lookup.sunrise}</span>}
              {lookup.sunset && <span> · 🌇 {lookup.sunset}</span>}
            </p>
          )}

          <div className="species-picker">
            <span className="picker-label">What are you fishing for?</span>
            <div className="species-chips">
              {lookup.species.map((s) => (
                <button
                  type="button"
                  key={s}
                  className={`chip ${selectedSpecies === s ? "chip-selected" : ""}`}
                  onClick={() => setSelectedSpecies(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div className="season-picker">
            <label>
              Season
              <select value={season} onChange={(e) => setSeason(e.target.value)}>
                {SEASONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <button
            type="button"
            className="get-tips-button"
            onClick={handleGetTips}
            disabled={!selectedSpecies || gettingTips}
          >
            {gettingTips ? "Getting tips..." : "Get tips"}
          </button>
        </div>
      )}
    </div>
  );
}
