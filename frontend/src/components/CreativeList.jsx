import { useEffect, useState } from 'react';
import { creativeService } from '../api/creativeService';

const SavedCreativeCard = ({ creative, campaignId, campaignName, onOpenCreative }) => {
  const [previewUrl, setPreviewUrl] = useState('');
  const content = creative.generated_content || {};
  const preview = content.headline || content.title || content.final_cta || 'AI-generated creative';

  useEffect(() => {
    if (creative.type !== 'image' || !creative.image_url) return undefined;

    let active = true;
    let objectUrl = '';
    creativeService.getAdvertisementImage(campaignId, creative.id).then((blob) => {
      objectUrl = URL.createObjectURL(blob);
      if (active) setPreviewUrl(objectUrl);
      else URL.revokeObjectURL(objectUrl);
    }).catch(() => {});

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [campaignId, creative.id, creative.image_url, creative.type]);

  return (
    <article className="creative-item saved-creative-card">
      <div className="saved-creative-preview">
        {previewUrl ? (
          <img src={previewUrl} alt={`${preview} advertisement`} />
        ) : (
          <div className={`saved-creative-placeholder ${creative.type === 'video' ? 'video-placeholder' : ''}`}>
            <span>{creative.type === 'image' ? 'Image brief' : creative.video_url ? 'Rendered video saved' : `${content.scenes?.length || 0} scenes`}</span>
          </div>
        )}
      </div>
      <div className="creative-item-head">
        <span className="creative-badge">{creative.type === 'image' ? 'Image Ad' : 'Video Ad'}</span>
        <span className="creative-date">{new Date(creative.created_at).toLocaleDateString()}</span>
      </div>
      <h3>{preview}</h3>
      <p className="saved-creative-campaign">{campaignName}</p>
      <p>
        {creative.type === 'image' && creative.image_url
          ? [creative.image_aspect_ratio, creative.image_style].filter(Boolean).join(' · ') || 'Advertisement image saved'
          : creative.type === 'image'
            ? content.primary_text || content.description || 'Image brief ready for editing.'
            : creative.video_url
              ? `Rendered video saved · ${content.scenes?.length || 0} scenes`
              : (content.scenes && content.scenes.length ? `${content.scenes.length} scenes` : 'Video script ready for editing.')}
      </p>
      <button type="button" className="btn-secondary" onClick={() => onOpenCreative(creative)}>
        {creative.type === 'video' && creative.video_url ? 'View / Edit' : 'Open / Edit'}
      </button>
    </article>
  );
};

export const CreativeList = ({ creatives = [], campaignId, campaignName, onOpenCreative }) => {
  if (!creatives.length) {
    return (
      <div className="empty-state muted-state">
        <p>No saved creatives yet for this campaign.</p>
      </div>
    );
  }

  return (
    <div className="creative-list">
      {creatives.map((creative) => (
        <SavedCreativeCard
          key={creative.id}
          creative={creative}
          campaignId={campaignId}
          campaignName={campaignName}
          onOpenCreative={onOpenCreative}
        />
      ))}
    </div>
  );
};

export default CreativeList;
