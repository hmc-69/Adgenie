import { useMemo, useState } from 'react';

export const CreativeModal = ({ open, onClose, onSelectType }) => {
  const [selectedType, setSelectedType] = useState(null);

  const options = useMemo(
    () => [
      {
        type: 'image',
        emoji: '🖼️',
        title: 'Image Ad',
        description: 'Build an editable image-ad brief and generate an advertisement image.',
      },
      {
        type: 'video',
        emoji: '🎬',
        title: 'Video Ad',
        description: 'Create an editable, scene-by-scene video advertisement script up to 15 seconds.',
      },
    ],
    []
  );

  if (!open) {
    return null;
  }

  return (
    <div className="confirm-overlay" role="presentation" onClick={onClose}>
      <div
        className="confirm-dialog creative-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="creative-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="creative-modal-title">What do you want to create?</h2>
        <div className="creative-choice-grid">
          {options.map((option) => (
            <button
              key={option.type}
              type="button"
              className={`creative-choice ${selectedType === option.type ? 'selected' : ''}`}
              onClick={() => {
                setSelectedType(option.type);
                onSelectType(option.type);
              }}
            >
              <div className="creative-choice-emoji">{option.emoji}</div>
              <div className="creative-choice-copy">
                <strong>{option.title}</strong>
                <span>{option.description}</span>
              </div>
            </button>
          ))}
        </div>
        <div className="confirm-dialog-actions">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

export default CreativeModal;
