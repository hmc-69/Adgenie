import { useEffect, useMemo, useState } from 'react';

const emptyImage = {
  headline: '',
  primary_text: '',
  description: '',
  call_to_action: '',
  hashtags: '',
  visual_direction: '',
};

const emptyVideo = {
  title: '',
  duration: '30 seconds',
  scenes: [
    {
      scene_number: 1,
      duration: '0-5 seconds',
      visual: '',
      voiceover: '',
      on_screen_text: '',
    },
  ],
  final_cta: '',
};

const formatHashtags = (value) => {
  if (!value) return [];
  return value
    .split(/\s+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => (item.startsWith('#') ? item : `#${item}`));
};

export const CreativeWorkspace = ({
  type,
  isGenerating,
  isGeneratingImage,
  generatedContent,
  errorMessage,
  onGenerate,
  onRegenerate,
  onSave,
  onContentChange,
  savedCreative,
  imageConfig,
  imageSettings,
  onImageSettingsChange,
  generatedImage,
  onGenerateImage,
  onSaveImage,
  onDownloadImage,
}) => {
  const [localImage, setLocalImage] = useState(emptyImage);
  const [localVideo, setLocalVideo] = useState(emptyVideo);

  const hasGenerated = useMemo(() => {
    if (!generatedContent) return false;
    if (type === 'image') {
      return Boolean(generatedContent.headline || generatedContent.primary_text || generatedContent.description);
    }
    return Boolean(generatedContent.title || generatedContent.scenes?.length);
  }, [generatedContent, type]);

  useEffect(() => {
    if (!generatedContent) return;
    if (type === 'image') {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setLocalImage({
        headline: generatedContent.headline || '',
        primary_text: generatedContent.primary_text || '',
        description: generatedContent.description || '',
        call_to_action: generatedContent.call_to_action || '',
        hashtags: Array.isArray(generatedContent.hashtags) ? generatedContent.hashtags.join(' ') : '',
        visual_direction: generatedContent.visual_direction || '',
      });
    }
    if (type === 'video') {
      setLocalVideo({
        title: generatedContent.title || '',
        duration: generatedContent.duration || '30 seconds',
        scenes: Array.isArray(generatedContent.scenes) && generatedContent.scenes.length
          ? generatedContent.scenes.map((scene) => ({
              scene_number: scene.scene_number || 1,
              duration: scene.duration || '0-5 seconds',
              visual: scene.visual || '',
              voiceover: scene.voiceover || '',
              on_screen_text: scene.on_screen_text || '',
            }))
          : emptyVideo.scenes,
        final_cta: generatedContent.final_cta || '',
      });
    }
  }, [generatedContent, type]);

  const handleImageChange = (field, value) => {
    const nextImage = { ...localImage, [field]: value };
    setLocalImage(nextImage);
    onContentChange({
      ...generatedContent,
      ...nextImage,
      hashtags: formatHashtags(nextImage.hashtags),
    });
  };

  const handleSceneChange = (sceneIndex, field, value) => {
    const nextVideo = {
      ...localVideo,
      scenes: localVideo.scenes.map((scene, index) => (index === sceneIndex ? { ...scene, [field]: value } : scene)),
    };
    setLocalVideo(nextVideo);
    onContentChange({ ...generatedContent, ...nextVideo });
  };

  const handleVideoAddScene = () => {
    const nextVideo = {
      ...localVideo,
      scenes: [
        ...localVideo.scenes,
        {
          scene_number: localVideo.scenes.length + 1,
          duration: '0-5 seconds',
          visual: '',
          voiceover: '',
          on_screen_text: '',
        },
      ],
    };
    setLocalVideo(nextVideo);
    onContentChange({ ...generatedContent, ...nextVideo });
  };

  const handleVideoFieldChange = (field, value) => {
    const nextVideo = { ...localVideo, [field]: value };
    setLocalVideo(nextVideo);
    onContentChange({ ...generatedContent, ...nextVideo });
  };

  if (type === 'image') {
    return (
      <div className="creative-workspace">
        <div className="creative-workspace-header">
          <div>
            <p className="page-kicker">Image Creative</p>
            <h2>Creative Brief</h2>
          </div>
          <div className="creative-actions">
            <button type="button" className="btn-primary" onClick={onGenerate} disabled={isGenerating}>
              {isGenerating ? 'Generating...' : 'Generate'}
            </button>
            <button type="button" className="btn-secondary" onClick={onRegenerate} disabled={isGenerating || !hasGenerated}>
              Regenerate
            </button>
            <button type="button" className="btn-primary-sm" onClick={onSave} disabled={isGenerating || !hasGenerated}>
              Save Creative
            </button>
          </div>
        </div>

        {errorMessage && <div className="alert alert-error" role="alert"><span>{errorMessage}</span></div>}
        {savedCreative && <div className="alert alert-success" role="status"><span>Saved as {savedCreative.type} creative.</span></div>}

        <div className="creative-form-grid">
          <div className="form-group form-span-2">
            <label className="form-label">Headline</label>
            <input className="form-input form-input-plain" value={localImage.headline} onChange={(event) => handleImageChange('headline', event.target.value)} />
          </div>
          <div className="form-group form-span-2">
            <label className="form-label">Primary Text</label>
            <textarea className="form-textarea" rows={3} value={localImage.primary_text} onChange={(event) => handleImageChange('primary_text', event.target.value)} />
          </div>
          <div className="form-group form-span-2">
            <label className="form-label">Description</label>
            <textarea className="form-textarea" rows={3} value={localImage.description} onChange={(event) => handleImageChange('description', event.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Call To Action</label>
            <input className="form-input form-input-plain" value={localImage.call_to_action} onChange={(event) => handleImageChange('call_to_action', event.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Hashtags</label>
            <input className="form-input form-input-plain" value={localImage.hashtags} onChange={(event) => handleImageChange('hashtags', event.target.value)} />
          </div>
          <div className="form-group form-span-2">
            <label className="form-label">Visual Direction</label>
            <textarea className="form-textarea" rows={4} value={localImage.visual_direction} onChange={(event) => handleImageChange('visual_direction', event.target.value)} />
          </div>
        </div>

        <div className="image-settings-panel">
          <div className="image-settings-header">
            <h3>Image Format</h3>
          </div>

          <div className="settings-grid">
            <div className="settings-card">
              <label className="form-label">Aspect Ratio</label>
              <div className="option-pills">
                {(imageConfig?.aspect_ratios || ['1:1', '4:5', '9:16', '16:9', '3:4']).map((ratio) => (
                  <button
                    key={ratio}
                    type="button"
                    className={`option-pill ${imageSettings.aspectRatio === ratio ? 'selected' : ''}`}
                    aria-pressed={imageSettings.aspectRatio === ratio}
                    title={{ '1:1': 'Square social post', '4:5': 'Portrait social post', '9:16': 'Story or Reel', '16:9': 'Landscape or banner', '3:4': 'Portrait poster' }[ratio]}
                    onClick={() => onImageSettingsChange('aspectRatio', ratio)}
                  >
                    <span className="ratio-preview" style={{ aspectRatio: ratio.replace(':', ' / ') }} />
                    {ratio}
                  </button>
                ))}
              </div>
            </div>

            <div className="settings-card">
              <label className="form-label">Visual Style</label>
              <div className="option-pills">
                {(imageConfig?.styles || ['AI Recommended', 'Photographic', 'Minimal', 'Editorial', 'Bold Graphic', 'Luxury', 'Playful']).map((style) => (
                  <button
                    key={style}
                    type="button"
                    className={`option-pill ${imageSettings.style === style ? 'selected' : ''}`}
                    aria-pressed={imageSettings.style === style}
                    onClick={() => onImageSettingsChange('style', style)}
                  >
                    {style}
                  </button>
                ))}
              </div>
            </div>

          </div>

          <div className="image-action-row">
            <button type="button" className="btn-primary" onClick={onGenerateImage} disabled={isGenerating || isGeneratingImage}>
              {isGeneratingImage ? 'Generating your advertisement...' : 'Generate Advertisement'}
            </button>
          </div>
        </div>

        {isGeneratingImage && (
          <div className="loading-state" aria-live="polite" aria-busy="true">
            <div className="spinner" />
            <p>Generating your advertisement...</p>
          </div>
        )}

        {generatedImage?.previewUrl && (
          <div className="generated-image-panel">
            <div className="generated-image-header">
              <h3>Generated Advertisement</h3>
              <div className="generated-image-meta">
                <span>{generatedImage.aspect_ratio}</span>
                <span>{generatedImage.style}</span>
              </div>
            </div>
            <img src={generatedImage.previewUrl} alt="Generated advertisement" className="generated-image" />
            <div className="landing-actions">
              <button type="button" className="btn-secondary" onClick={onGenerateImage} disabled={isGenerating || isGeneratingImage}>
                Regenerate
              </button>
              <button type="button" className="btn-primary-sm" onClick={onSaveImage} disabled={isGenerating || isGeneratingImage}>
                Save
              </button>
              <button type="button" className="btn-secondary" onClick={onDownloadImage} disabled={isGenerating || isGeneratingImage}>
                Download
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="creative-workspace">
      <div className="creative-workspace-header">
        <div>
          <p className="page-kicker">Video Creative</p>
          <h2>AI Generated Script</h2>
        </div>
        <div className="creative-actions">
          <button type="button" className="btn-primary" onClick={onGenerate} disabled={isGenerating}>
            {isGenerating ? 'Generating...' : 'Generate Script'}
          </button>
          <button type="button" className="btn-secondary" onClick={onRegenerate} disabled={isGenerating || !hasGenerated}>
            Regenerate
          </button>
          <button type="button" className="btn-primary-sm" onClick={onSave} disabled={isGenerating || !hasGenerated}>
            Save Script
          </button>
        </div>
      </div>

      {errorMessage && <div className="alert alert-error" role="alert"><span>{errorMessage}</span></div>}
      {savedCreative && <div className="alert alert-success" role="status"><span>Saved as {savedCreative.type} creative.</span></div>}

      <div className="creative-form-grid">
        <div className="form-group">
          <label className="form-label">Title</label>
          <input className="form-input form-input-plain" value={localVideo.title} onChange={(event) => handleVideoFieldChange('title', event.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label">Duration</label>
          <input className="form-input form-input-plain" value={localVideo.duration} onChange={(event) => handleVideoFieldChange('duration', event.target.value)} />
        </div>
      </div>

      {localVideo.scenes.map((scene, index) => (
        <div key={scene.scene_number || index} className="video-scene-card">
          <div className="video-scene-title">Scene {index + 1}</div>
          <div className="creative-form-grid">
            <div className="form-group">
              <label className="form-label">Duration</label>
              <input className="form-input form-input-plain" value={scene.duration} onChange={(event) => handleSceneChange(index, 'duration', event.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">On-screen Text</label>
              <input className="form-input form-input-plain" value={scene.on_screen_text} onChange={(event) => handleSceneChange(index, 'on_screen_text', event.target.value)} />
            </div>
            <div className="form-group form-span-2">
              <label className="form-label">Visual</label>
              <textarea className="form-textarea" rows={3} value={scene.visual} onChange={(event) => handleSceneChange(index, 'visual', event.target.value)} />
            </div>
            <div className="form-group form-span-2">
              <label className="form-label">Voiceover / Dialogue</label>
              <textarea className="form-textarea" rows={3} value={scene.voiceover} onChange={(event) => handleSceneChange(index, 'voiceover', event.target.value)} />
            </div>
          </div>
        </div>
      ))}

      <button type="button" className="btn-secondary" onClick={handleVideoAddScene}>Add Scene</button>

      <div className="form-group form-span-2">
        <label className="form-label">Final CTA</label>
        <input className="form-input form-input-plain" value={localVideo.final_cta} onChange={(event) => handleVideoFieldChange('final_cta', event.target.value)} />
      </div>
    </div>
  );
};

export default CreativeWorkspace;
