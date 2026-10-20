import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useLocation } from 'react-router-dom';
import { campaignService, getApiErrorMessage } from '../api/campaignService';
import { creativeService } from '../api/creativeService';
import { createVideoPlaybackUrl, isTerminalVideoStatus } from '../utils/videoPlayback';
import { CampaignStatusBadge } from '../components/CampaignStatusBadge';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { CreativeList } from '../components/CreativeList';
import { CreativeModal } from '../components/CreativeModal';
import { CreativeWorkspace } from '../components/CreativeWorkspace';

const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    return new Date(dateString).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateString;
  }
};

const formatBudget = (budget) => {
  if (budget === null || budget === undefined || budget === '') {
    return 'Not set';
  }
  const amount = Number(budget);
  if (Number.isNaN(amount)) {
    return String(budget);
  }
  return amount.toLocaleString(undefined, { style: 'currency', currency: 'USD' });
};

export const CampaignDetails = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [campaign, setCampaign] = useState(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState(location.state?.successMessage || '');
  const [deleteTarget, setDeleteTarget] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [creativeModalOpen, setCreativeModalOpen] = useState(false);
  const [creativeType, setCreativeType] = useState('image');
  const [creativeContent, setCreativeContent] = useState(null);
  const [creativeError, setCreativeError] = useState('');
  const [isGeneratingCreative, setIsGeneratingCreative] = useState(false);
  const [isGeneratingImage, setIsGeneratingImage] = useState(false);
  const [savedCreatives, setSavedCreatives] = useState([]);
  const [lastSavedCreative, setLastSavedCreative] = useState(null);
  const [imageConfig, setImageConfig] = useState({ aspect_ratios: ['1:1', '4:5', '9:16', '16:9', '3:4'], styles: ['AI Recommended', 'Photographic', 'Minimal', 'Editorial', 'Bold Graphic', 'Luxury', 'Playful'] });
  const [imageSettings, setImageSettings] = useState({ aspectRatio: '4:5', style: 'Photographic' });
  const [generatedImage, setGeneratedImage] = useState(null);
  const generatedImageUrlRef = useRef(null);
  const selectedCreativeIdRef = useRef(null);
  const imageRequestInFlightRef = useRef(false);
  const videoUrlRef = useRef(null);
  const videoPollRef = useRef(null);
  const [videoRender, setVideoRender] = useState(null);
  const [isStartingVideoRender, setIsStartingVideoRender] = useState(false);

  const setImagePreview = (image, blob) => {
    if (generatedImageUrlRef.current) {
      URL.revokeObjectURL(generatedImageUrlRef.current);
    }
    const previewUrl = URL.createObjectURL(blob);
    generatedImageUrlRef.current = previewUrl;
    setGeneratedImage({ ...image, previewUrl });
  };

  const clearImagePreview = () => {
    if (generatedImageUrlRef.current) {
      URL.revokeObjectURL(generatedImageUrlRef.current);
      generatedImageUrlRef.current = null;
    }
    setGeneratedImage(null);
  };

  useEffect(() => () => {
    if (generatedImageUrlRef.current) {
      URL.revokeObjectURL(generatedImageUrlRef.current);
    }
    if (videoUrlRef.current) URL.revokeObjectURL(videoUrlRef.current);
    if (videoPollRef.current) window.clearInterval(videoPollRef.current);
  }, []);

  const loadRenderedVideo = async (creativeId, videoUrl) => {
    const blob = await creativeService.getRenderedVideo(campaign.id, creativeId, videoUrl);
    if (videoUrlRef.current) URL.revokeObjectURL(videoUrlRef.current);
    videoUrlRef.current = createVideoPlaybackUrl(blob);
    setVideoRender((previous) => ({ ...previous, status: 'completed', videoUrl: videoUrlRef.current }));
  };

  const pollVideoRender = (creativeId) => {
    if (videoPollRef.current) window.clearInterval(videoPollRef.current);
    videoPollRef.current = window.setInterval(async () => {
      try {
        const statusResponse = await creativeService.getVideoRenderStatus(campaign.id, creativeId);
        setVideoRender(statusResponse);
        if (statusResponse.status === 'completed') {
          window.clearInterval(videoPollRef.current);
          videoPollRef.current = null;
          if (!statusResponse.video_url) {
            throw new Error('The video completed, but the API returned no playback URL.');
          }
          await loadRenderedVideo(creativeId, statusResponse.video_url);
          await loadSavedCreatives();
        } else if (isTerminalVideoStatus(statusResponse.status)) {
          window.clearInterval(videoPollRef.current);
          videoPollRef.current = null;
        }
      } catch (error) {
        window.clearInterval(videoPollRef.current);
        videoPollRef.current = null;
        setVideoRender((previous) => previous ? { ...previous, status: 'failed' } : previous);
        setCreativeError(getApiErrorMessage(error, 'Unable to check video render status.'));
      }
    }, 5000);
  };

  const handleStartVideoRender = async () => {
    if (isStartingVideoRender || !selectedCreativeIdRef.current) {
      setCreativeError('Save the video script before rendering it.');
      return;
    }
    if (!window.confirm('Generate this video? JSON2Video rendering consumes credits.')) return;
    setIsStartingVideoRender(true);
    setCreativeError('');
    try {
      const response = await creativeService.startVideoRender(campaign.id, selectedCreativeIdRef.current);
      setVideoRender(response);
      pollVideoRender(selectedCreativeIdRef.current);
    } catch (error) {
      setCreativeError(getApiErrorMessage(error, 'Unable to start video rendering.'));
    } finally {
      setIsStartingVideoRender(false);
    }
  };

  const loadSavedCreatives = async () => {
    if (!id) return;
    try {
      const data = await creativeService.listCreatives(id);
      setSavedCreatives(data.creatives || []);
    } catch {
      setSavedCreatives([]);
    }
  };

  useEffect(() => {
    let isActive = true;

    const fetchCampaign = async () => {
      setLoading(true);
      setErrorMessage('');
      try {
        const data = await campaignService.getCampaign(id);
        if (isActive) {
          setCampaign(data);
        }
      } catch (error) {
        if (isActive) {
          setErrorMessage(getApiErrorMessage(error, 'Unable to load this campaign.'));
        }
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    fetchCampaign();
    return () => {
      isActive = false;
    };
  }, [id]);

  useEffect(() => {
    if (!campaign?.id) return undefined;
    let active = true;

    const fetchCreatives = async () => {
      try {
        const data = await creativeService.listCreatives(campaign.id);
        if (active) setSavedCreatives(data.creatives || []);
      } catch {
        if (active) setSavedCreatives([]);
      }
    };

    fetchCreatives();
    return () => { active = false; };
  }, [campaign?.id]);

  useEffect(() => {
    const fetchImageConfig = async () => {
      try {
        const config = await creativeService.getImageGenerationConfig();
        setImageConfig(config);
        if (config?.aspect_ratios?.length) {
          setImageSettings((previous) => ({ ...previous, aspectRatio: config.aspect_ratios.includes(previous.aspectRatio) ? previous.aspectRatio : config.aspect_ratios[0] }));
        }
      } catch {
        setImageConfig({ aspect_ratios: ['1:1', '4:5', '9:16', '16:9', '3:4'], styles: ['AI Recommended', 'Photographic', 'Minimal', 'Editorial', 'Bold Graphic', 'Luxury', 'Playful'] });
      }
    };

    fetchImageConfig();
  }, []);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await campaignService.deleteCampaign(id);
      navigate('/dashboard', {
        replace: true,
        state: { successMessage: 'Campaign deleted successfully.' },
      });
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error, 'Unable to delete this campaign.'));
      setDeleteTarget(false);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleGenerateCreative = async () => {
    if (!campaign?.id) return;
    selectedCreativeIdRef.current = null;
    setCreativeError('');
    setIsGeneratingCreative(true);

    try {
      const payload =
        creativeType === 'image'
          ? await creativeService.generateImageBrief(campaign.id)
          : await creativeService.generateVideoScript(campaign.id);
      setCreativeContent(payload.generated_content || payload);
      setLastSavedCreative(null);
    } catch (error) {
      setCreativeError(getApiErrorMessage(error, 'Unable to generate the creative right now. Please try again.'));
    } finally {
      setIsGeneratingCreative(false);
    }
  };

  const handleRegenerateCreative = () => {
    handleGenerateCreative();
  };

  const handleSaveCreative = async () => {
    if (!campaign?.id || !creativeContent) {
      setCreativeError('Generate content first before saving.');
      return;
    }

    setCreativeError('');
    try {
      const saved = await creativeService.saveCreative({
        campaign_id: Number(campaign.id),
        type: creativeType,
        content: creativeContent,
      });
      setLastSavedCreative(saved);
      selectedCreativeIdRef.current = saved.id;
      await loadSavedCreatives();
      setSuccessMessage(
        creativeType === 'image'
          ? 'Image creative saved successfully.'
          : 'Video script saved successfully.'
      );
    } catch (error) {
      setCreativeError(getApiErrorMessage(error, 'Unable to save this creative.'));
    }
  };

  const handleGenerateAdvertisementImage = async () => {
    if (imageRequestInFlightRef.current) return;
    if (!campaign?.id || !savedCreatives.length || creativeType !== 'image'){
      setCreativeError('Save an image creative before generating an ad image.');
      return;
    }

    const sourceCreative = savedCreatives.find((creative) => creative.id === selectedCreativeIdRef.current)
      || savedCreatives.find((creative) => creative.type === 'image' && creative.generated_content && Object.keys(creative.generated_content).length > 0);
    if (!sourceCreative) {
      setCreativeError('Generate and save an image creative before creating the advertisement.');
      return;
    }

    setCreativeError('');
    imageRequestInFlightRef.current = true;
    setIsGeneratingImage(true);

    try {
      const response = await creativeService.generateAdvertisementImage({
        campaign_id: Number(campaign.id),
        creative_id: Number(sourceCreative.id),
        aspect_ratio: imageSettings.aspectRatio,
        style: imageSettings.style,
      });
      const imageBlob = await creativeService.getAdvertisementImage(campaign.id, sourceCreative.id);
      setImagePreview(response, imageBlob);
      selectedCreativeIdRef.current = sourceCreative.id;
      await loadSavedCreatives();
      setSuccessMessage('Advertisement image generated successfully.');
    } catch (error) {
      setCreativeError(getApiErrorMessage(error, 'Unable to generate the advertisement image. Please try again.'));
    } finally {
      imageRequestInFlightRef.current = false;
      setIsGeneratingImage(false);
    }
  };

  const handleImageSettingsChange = (field, value) => {
    setImageSettings((previous) => ({ ...previous, [field]: value }));
  };

  const handleSaveGeneratedImage = async () => {
    if (!generatedImage?.creative_id) return;
    await loadSavedCreatives();
    setSuccessMessage('Advertisement image is saved to this campaign.');
  };

  const handleDownloadGeneratedImage = () => {
    if (!generatedImage?.previewUrl) return;
    const link = document.createElement('a');
    link.href = generatedImage.previewUrl;
    link.download = `adgenie-campaign-${campaign.id}-image.jpg`;
    link.click();
  };

  const handleDownloadRenderedVideo = () => {
    if (!videoUrlRef.current) return;
    const link = document.createElement('a');
    link.href = videoUrlRef.current;
    link.download = `adgenie-campaign-${campaign.id}-video.mp4`;
    link.click();
  };

  const handleOpenCreative = async (creative) => {
    setCreativeType(creative.type);
    setCreativeContent(creative.generated_content || {});
    setCreativeError('');
    selectedCreativeIdRef.current = creative.id;
    setLastSavedCreative(creative);
    clearImagePreview();
    setVideoRender(null);

    if (creative.type === 'image' && creative.image_url) {
      try {
        const imageBlob = await creativeService.getAdvertisementImage(campaign.id, creative.id);
        setImagePreview({
          creative_id: creative.id,
          image_url: creative.image_url,
          aspect_ratio: creative.image_aspect_ratio,
          style: creative.image_style,
        }, imageBlob);
      } catch (error) {
        setCreativeError(getApiErrorMessage(error, 'Unable to load the saved advertisement image.'));
      }
    }
    if (creative.type === 'video' && creative.video_project_id) {
      setVideoRender({
        campaign_id: campaign.id,
        creative_id: creative.id,
        project_id: creative.video_project_id,
        status: creative.video_status || 'submitted',
        duration: creative.video_duration,
      });
      if (creative.video_status === 'completed') {
        try {
          await loadRenderedVideo(creative.id, creative.video_url);
        } catch (error) {
          setVideoRender((previous) => previous ? { ...previous, status: 'failed' } : previous);
          setCreativeError(getApiErrorMessage(error, 'Unable to load the rendered video.'));
        }
      } else {
        pollVideoRender(creative.id);
      }
    }
  };

  const handleSelectCreativeType = (type) => {
    setCreativeType(type);
    setCreativeContent(null);
    selectedCreativeIdRef.current = null;
    clearImagePreview();
    setCreativeError('');
    setLastSavedCreative(null);
    setCreativeModalOpen(false);
  };

  if (loading) {
    return (
      <div className="campaign-page">
        <div className="state-card">
          <div className="auth-spinner"></div>
          <p>Loading campaign details...</p>
        </div>
      </div>
    );
  }

  if (errorMessage && !campaign) {
    return (
      <div className="campaign-page">
        <div className="state-card state-error">
          <h2>Campaign unavailable</h2>
          <p>{errorMessage}</p>
          <Link to="/dashboard" className="btn-secondary">Back to Campaigns</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="campaign-page campaign-workspace-page">
      <Link to="/dashboard#campaigns" className="campaign-back-link"><span aria-hidden="true">←</span> Back to Campaigns</Link>
      <header className="campaign-titlebar">
        <div>
          <p className="page-kicker">Campaign workspace</p>
          <h1>{campaign.name}</h1>
          <p className="page-subtitle">{campaign.product_name}</p>
        </div>
        <div className="page-header-actions">
          <Link to={`/campaigns/${campaign.id}/edit`} className="btn-secondary">Edit campaign</Link>
          <button type="button" className="btn-danger-sm" onClick={() => setDeleteTarget(true)}>Delete</button>
        </div>
      </header>

      {successMessage && (
        <div className="alert alert-success" role="status">
          <span>{successMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="alert alert-error" role="alert">
          <span>{errorMessage}</span>
        </div>
      )}

      <div className="campaign-meta-strip">
        <div><span>Platform</span><strong>{campaign.platform}</strong></div>
        <div><span>Objective</span><strong>{campaign.objective}</strong></div>
        <div><span>Status</span><CampaignStatusBadge status={campaign.status} /></div>
        <div><span>Tone</span><strong>{campaign.tone}</strong></div>
        <div><span>Budget</span><strong>{formatBudget(campaign.budget)}</strong></div>
      </div>

      <section className="campaign-overview-section">
        <div className="workspace-section-heading">
          <div><p className="page-kicker">Campaign context</p><h2>Campaign Overview</h2></div>
          <span className="overview-date">Updated {formatDate(campaign.updated_at)}</span>
        </div>
        <div className="campaign-overview-grid">
          <article className="overview-detail overview-detail-wide">
            <span className="meta-label">Description</span>
            <p>{campaign.description}</p>
          </article>
          <article className="overview-detail">
            <span className="meta-label">Target Audience</span>
            <p>{campaign.target_audience}</p>
          </article>
          {campaign.keywords && (
            <article className="overview-detail">
              <span className="meta-label">Keywords</span>
              <p>{campaign.keywords}</p>
            </article>
          )}
        </div>
      </section>

      <section className="creative-studio-section" id="creative-studio">
        <div className="studio-heading-row">
          <div>
            <p className="page-kicker">Campaign assets</p>
            <h2>AI Creative Studio</h2>
            <p>Create AI-powered advertising content for this campaign.</p>
          </div>
          <div className="creative-type-control" role="tablist" aria-label="Creative type">
            <button type="button" role="tab" aria-selected={creativeType === 'image'} className={creativeType === 'image' ? 'selected' : ''} onClick={() => creativeType !== 'image' && handleSelectCreativeType('image')}>Image Ad</button>
            <button type="button" role="tab" aria-selected={creativeType === 'video'} className={creativeType === 'video' ? 'selected' : ''} onClick={() => creativeType !== 'video' && handleSelectCreativeType('video')}>Video Ad</button>
          </div>
        </div>

        {creativeType && (
          <CreativeWorkspace
            type={creativeType}
            campaign={campaign}
            isGenerating={isGeneratingCreative}
            isGeneratingImage={isGeneratingImage}
            generatedContent={creativeContent}
            errorMessage={creativeError}
            onGenerate={handleGenerateCreative}
            onRegenerate={handleRegenerateCreative}
            onSave={handleSaveCreative}
            onContentChange={setCreativeContent}
            savedCreative={lastSavedCreative}
            imageConfig={imageConfig}
            imageSettings={imageSettings}
            onImageSettingsChange={handleImageSettingsChange}
            generatedImage={generatedImage}
            onGenerateImage={handleGenerateAdvertisementImage}
            onSaveImage={handleSaveGeneratedImage}
            onDownloadImage={handleDownloadGeneratedImage}
            videoRender={videoRender}
            isStartingVideoRender={isStartingVideoRender}
            onStartVideoRender={handleStartVideoRender}
            onDownloadVideo={handleDownloadRenderedVideo}
          />
        )}
      </section>

      <section className="saved-creatives-section">
        <div className="workspace-section-heading">
          <div><p className="page-kicker">Campaign library</p><h2>Saved Creatives</h2></div>
          <span className="saved-count">{savedCreatives.length} {savedCreatives.length === 1 ? 'asset' : 'assets'}</span>
        </div>
        <CreativeList
          creatives={savedCreatives}
          campaignId={campaign.id}
          campaignName={campaign.name}
          onOpenCreative={handleOpenCreative}
        />
      </section>

      <CreativeModal
        open={creativeModalOpen}
        onClose={() => setCreativeModalOpen(false)}
        onSelectType={handleSelectCreativeType}
      />

      <ConfirmDialog
        open={deleteTarget}
        title="Delete campaign"
        message="Are you sure you want to delete this campaign?"
        confirmLabel="Delete Campaign"
        isBusy={isDeleting}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(false)}
      />
    </div>
  );
};

export default CampaignDetails;
