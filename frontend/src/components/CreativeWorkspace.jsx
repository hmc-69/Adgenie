import { useEffect, useMemo, useState } from 'react';

const MAX_VIDEO_DURATION_SECONDS = 15;

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
  duration: 15,
  scenes: [
    {
      scene_number: 1,
      duration: 7,
      visual: '',
      voiceover: '',
      on_screen_text: '',
    },
    {
      scene_number: 2,
      duration: 8,
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
  errorRef,
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
  videoRender,
  isStartingVideoRender,
  onStartVideoRender,
  onDownloadVideo,
  onSaveVideo,
  isSavingVideo = false,
}) => {
  const [localImage, setLocalImage] = useState(emptyImage);
  const [localVideo, setLocalVideo] = useState(emptyVideo);
  const videoTotalDuration = useMemo(
    () => localVideo.scenes.reduce((total, scene) => total + (Number(scene.duration) || 0), 0),
    [localVideo.scenes],
  );

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
        duration: generatedContent.duration || 0,
        scenes: Array.isArray(generatedContent.scenes) && generatedContent.scenes.length
          ? generatedContent.scenes.map((scene) => ({
              scene_number: scene.scene_number || 1,
              duration: scene.duration || 0,
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
    nextVideo.duration = nextVideo.scenes.reduce((total, scene) => total + (Number(scene.duration) || 0), 0);
    setLocalVideo(nextVideo);
    onContentChange({ ...generatedContent, ...nextVideo });
  };

  const handleVideoAddScene = () => {
    if (localVideo.scenes.length >= 4) return;
    const nextVideo = {
      ...localVideo,
      scenes: [
        ...localVideo.scenes,
        {
          scene_number: localVideo.scenes.length + 1,
          duration: 1,
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
      <div className="creative-workspace image-creative-workspace">
        <div className="creative-workspace-header">
          <div><p className="page-kicker">Image Ad</p><h3>Creative brief</h3></div>
          <div className="creative-actions">
            <button type="button" className="btn-primary" onClick={onGenerate} disabled={isGenerating}>
              {isGenerating ? 'Generating brief...' : 'Generate Brief'}
            </button>
            <button type="button" className="btn-secondary" onClick={onRegenerate} disabled={isGenerating || !hasGenerated}>Regenerate Brief</button>
            <button type="button" className="btn-secondary" onClick={onSave} disabled={isGenerating || !hasGenerated}>Save Creative</button>
          </div>
        </div>
        {errorMessage && <div ref={errorRef} className="alert alert-error" role="alert"><span>{errorMessage}</span></div>}
        {savedCreative && <div className="alert alert-success" role="status"><span>Saved as {savedCreative.type} creative.</span></div>}

        <div className="creative-studio-layout">
          <section className="creative-brief-panel" aria-label="Editable image creative brief">
            <div className="creative-panel-heading"><div><p className="page-kicker">M4.1 output</p><h3>Creative Brief</h3></div><span>Editable</span></div>
            <div className="creative-form-grid">
              <div className="form-group form-span-2">
                <label className="form-label" htmlFor="image-headline">Headline</label>
                <input id="image-headline" className="form-input form-input-plain" value={localImage.headline} onChange={(event) => handleImageChange('headline', event.target.value)} />
              </div>
              <div className="form-group form-span-2">
                <label className="form-label" htmlFor="image-primary-text">Primary Text</label>
                <textarea id="image-primary-text" className="form-textarea" rows={3} value={localImage.primary_text} onChange={(event) => handleImageChange('primary_text', event.target.value)} />
              </div>
              <div className="form-group form-span-2">
                <label className="form-label" htmlFor="image-description">Description</label>
                <textarea id="image-description" className="form-textarea" rows={3} value={localImage.description} onChange={(event) => handleImageChange('description', event.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="image-cta">Call To Action</label>
                <input id="image-cta" className="form-input form-input-plain" value={localImage.call_to_action} onChange={(event) => handleImageChange('call_to_action', event.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="image-hashtags">Hashtags</label>
                <input id="image-hashtags" className="form-input form-input-plain" value={localImage.hashtags} onChange={(event) => handleImageChange('hashtags', event.target.value)} />
              </div>
              <div className="form-group form-span-2">
                <label className="form-label" htmlFor="image-visual-direction">Visual Direction</label>
                <textarea id="image-visual-direction" className="form-textarea" rows={4} value={localImage.visual_direction} onChange={(event) => handleImageChange('visual_direction', event.target.value)} />
              </div>
            </div>

            <div className="image-settings-panel">
              <div className="image-settings-header"><h3>Image settings</h3><span>Applied to the next render</span></div>
              <div className="settings-grid">
                <div className="settings-card">
                  <label className="form-label">Aspect Ratio</label>
                  <div className="option-pills">
                    {(imageConfig?.aspect_ratios || ['1:1', '4:5', '9:16', '16:9', '3:4']).map((ratio) => (
                      <button key={ratio} type="button" className={`option-pill ${imageSettings.aspectRatio === ratio ? 'selected' : ''}`} aria-pressed={imageSettings.aspectRatio === ratio} title={{ '1:1': 'Square social post', '4:5': 'Portrait social post', '9:16': 'Story or Reel', '16:9': 'Landscape or banner', '3:4': 'Portrait poster' }[ratio]} onClick={() => onImageSettingsChange('aspectRatio', ratio)}>
                        <span className="ratio-preview" style={{ aspectRatio: ratio.replace(':', ' / ') }} />{ratio}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="settings-card">
                  <label className="form-label">Visual Style</label>
                  <div className="option-pills">
                    {(imageConfig?.styles || ['AI Recommended', 'Photographic', 'Minimal', 'Editorial', 'Bold Graphic', 'Luxury', 'Playful']).map((style) => (
                      <button key={style} type="button" className={`option-pill ${imageSettings.style === style ? 'selected' : ''}`} aria-pressed={imageSettings.style === style} onClick={() => onImageSettingsChange('style', style)}>{style}</button>
                    ))}
                  </div>
                </div>
              </div>
              <button type="button" className="btn-primary image-generate-button" onClick={onGenerateImage} disabled={isGenerating || isGeneratingImage}>
                {isGeneratingImage ? 'Generating your advertisement...' : 'Generate Advertisement'}
              </button>
            </div>
          </section>

          <section className="creative-output-panel" aria-label="Generated advertisement preview">
            <div className="creative-panel-heading"><div><p className="page-kicker">M4.2 output</p><h3>Generated Creative</h3></div></div>
            {isGeneratingImage ? (
              <div className="creative-output-empty creative-output-loading" aria-live="polite" aria-busy="true">
                <div className="spinner" /><strong>Generating your advertisement...</strong><span>Preparing your image in {imageSettings.aspectRatio} format.</span>
              </div>
            ) : generatedImage?.previewUrl ? (
              <>
                <div className="generated-image-meta"><span>{generatedImage.aspect_ratio}</span><span>{generatedImage.style}</span></div>
                <img src={generatedImage.previewUrl} alt="Generated advertisement" className="generated-image" />
                <div className="landing-actions">
                  <button type="button" className="btn-secondary" onClick={onGenerateImage} disabled={isGenerating || isGeneratingImage}>Regenerate</button>
                  <button type="button" className="btn-primary-sm" onClick={onSaveImage} disabled={isGenerating || isGeneratingImage}>Save</button>
                  <button type="button" className="btn-secondary" onClick={onDownloadImage} disabled={isGenerating || isGeneratingImage}>Download</button>
                </div>
              </>
            ) : (
              <div className="creative-output-empty"><span className="output-mark" aria-hidden="true">✳</span><strong>Your generated advertisement will appear here.</strong><span>Create or open an image brief, choose a style and format, then generate your image.</span></div>
            )}
          </section>
        </div>
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
          <button
            type="button"
            className="btn-primary-sm"
            onClick={onStartVideoRender}
            disabled={isGenerating || isStartingVideoRender || !savedCreative}
          >
            {isStartingVideoRender ? 'Submitting...' : 'Generate Video'}
          </button>
        </div>
      </div>

      {errorMessage && <div ref={errorRef} className="alert alert-error" role="alert"><span>{errorMessage}</span></div>}
      {savedCreative && <div className="alert alert-success" role="status"><span>Saved as {savedCreative.type} creative.</span></div>}

      <div className="creative-form-grid">
        <div className="form-group">
          <label className="form-label">Title</label>
          <input className="form-input form-input-plain" value={localVideo.title} onChange={(event) => handleVideoFieldChange('title', event.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label">Total Duration (max 15 seconds)</label>
          <input className="form-input form-input-plain" type="number" min="0" max={MAX_VIDEO_DURATION_SECONDS} step="0.1" value={videoTotalDuration} readOnly />
        </div>
      </div>
      <p className="form-help">Maximum video duration: {MAX_VIDEO_DURATION_SECONDS} seconds. Calculated total: {videoTotalDuration} seconds.</p>

      {localVideo.scenes.map((scene, index) => (
        <div key={scene.scene_number || index} className="video-scene-card">
          <div className="video-scene-title">Scene {index + 1}</div>
          <div className="creative-form-grid">
            <div className="form-group">
              <label className="form-label">Duration</label>
              <input className="form-input form-input-plain" type="number" min="0.1" max={MAX_VIDEO_DURATION_SECONDS} step="0.1" value={scene.duration} onChange={(event) => handleSceneChange(index, 'duration', Number(event.target.value))} />
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

      <button type="button" className="btn-secondary" onClick={handleVideoAddScene} disabled={localVideo.scenes.length >= 4}>Add Scene</button>

      <div className="form-group form-span-2">
        <label className="form-label">Final CTA</label>
        <input className="form-input form-input-plain" value={localVideo.final_cta} onChange={(event) => handleVideoFieldChange('final_cta', event.target.value)} />
      </div>
      {videoRender && (
        <div className="creative-output-panel video-render-result">
          <strong>Video render: {videoRender.status}</strong>
          {videoRender.status === 'failed' ? (
            <p className="alert alert-error">{videoRender.error || 'The video is unavailable. See the error details above.'} No automatic retry was submitted.</p>
          ) : null}
          {videoRender.status === 'submitted' || videoRender.status === 'pending' || videoRender.status === 'rendering' || videoRender.status === 'running' ? (
            <p>{videoRender.status === 'pending' || videoRender.status === 'submitted' ? 'Video render is queued.' : 'Video render is in progress.'} JSON2Video credits are being used.</p>
          ) : null}
          {videoRender.videoUrl ? (
            <>
              <video controls className="generated-video" src={videoRender.videoUrl}>
                <track kind="captions" />
              </video>
              <button type="button" className="btn-primary-sm" onClick={onSaveVideo} disabled={isSavingVideo}>
                {isSavingVideo ? 'Saving…' : 'Save Video'}
              </button>
              <button type="button" className="btn-secondary" onClick={onDownloadVideo}>Download Video</button>
            </>
          ) : null}
        </div>
      )}
    </div>
  );
};

export default CreativeWorkspace;
