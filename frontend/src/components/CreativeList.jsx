export const CreativeList = ({ creatives = [], onOpenCreative }) => {
  if (!creatives.length) {
    return (
      <div className="empty-state muted-state">
        <p>No saved creatives yet for this campaign.</p>
      </div>
    );
  }

  return (
    <div className="creative-list">
      {creatives.map((creative) => {
        const content = creative.generated_content || {};
        const preview =
          content.headline ||
          content.title ||
          content.final_cta ||
          'AI-generated creative';

        return (
          <article key={creative.id} className="creative-item">
            <div className="creative-item-head">
              <span className="creative-badge">{creative.type === 'image' ? 'Image' : 'Video'}</span>
              <span className="creative-date">{new Date(creative.created_at).toLocaleDateString()}</span>
            </div>
            <h3>{preview}</h3>
            <p>
              {creative.type === 'image'
                ? content.primary_text || content.description || 'Image brief ready for editing.'
                : (content.scenes && content.scenes.length ? `${content.scenes.length} scenes` : 'Video script ready for editing.')}
            </p>
            <button type="button" className="btn-secondary" onClick={() => onOpenCreative(creative)}>
              Open / Edit
            </button>
          </article>
        );
      })}
    </div>
  );
};

export default CreativeList;
