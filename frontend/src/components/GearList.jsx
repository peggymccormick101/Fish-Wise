export default function GearList({ items }) {
  if (!items?.length) return <p>No gear recommendations yet.</p>;

  const byCategory = items.reduce((acc, item) => {
    const key = item.category || "Other";
    acc[key] = acc[key] || [];
    acc[key].push(item);
    return acc;
  }, {});

  return (
    <div className="gear-list">
      {Object.entries(byCategory).map(([category, categoryItems]) => (
        <div className="gear-category" key={category}>
          <h3 className="gear-category-title">{category}</h3>
          <ul>
            {categoryItems.map((item) => (
              <li key={item.id}>
                <span className="gear-name">{item.name}</span>
                {item.notes && <span className="gear-notes"> — {item.notes}</span>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
