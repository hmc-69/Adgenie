import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useLocation } from 'react-router-dom';
import { campaignService, getApiErrorMessage } from '../api/campaignService';
import { creativeService } from '../api/creativeService';
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
  }, []);

  const loadCampaign = async () => {
    setLoading(true);
    setErrorMessage('');
    try {
      const data = await campaignService.getCampaign(id);
      setCampaign(data);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error, 'Unable to load this campaign.'));
    } finally {
      setLoading(false);
    }
  };

  const loadSavedCreatives = async () => {
    if (!id) return;
    try {
      const data = await creativeService.listCreatives(id);
      setSavedCreatives(data.creatives || []);
    } catch (error) {
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
    if (campaign?.id) {
      loadSavedCreatives();
    }
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

  const handleOpenCreative = async (creative) => {
    setCreativeType(creative.type);
    setCreativeContent(creative.generated_content || {});
    setCreativeError('');
    selectedCreativeIdRef.current = creative.id;
    clearImagePreview();

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
    <div className="campaign-page">
      <div className="page-header">
        <div>
          <p className="page-kicker">Campaign Details</p>
          <h1>{campaign.name}</h1>
          <p className="page-subtitle">{campaign.product_name}</p>
        </div>
        <div className="page-header-actions">
          <Link to={`/campaigns/${campaign.id}/edit`} className="btn-primary-sm">Edit</Link>
          <button type="button" className="btn-primary-sm" onClick={() => setCreativeModalOpen(true)}>
            ✨ Create AI Creative
          </button>
          <button type="button" className="btn-danger-sm" onClick={() => setDeleteTarget(true)}>
            Delete
          </button>
          <Link to="/dashboard" className="btn-secondary">Back to Campaigns</Link>
        </div>
      </div>

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

      <section className="campaign-details-card">
        <div className="details-status-row">
          <CampaignStatusBadge status={campaign.status} />
          <span className="details-platform">{campaign.platform}</span>
        </div>

        <div className="details-grid">
          <div className="details-item">
            <span className="meta-label">Campaign Name</span>
            <span className="meta-value">{campaign.name}</span>
          </div>
          <div className="details-item">
            <span className="meta-label">Product / Service</span>
            <span className="meta-value">{campaign.product_name}</span>
          </div>
          <div className="details-item details-span-2">
            <span className="meta-label">Description</span>
            <p className="details-copy">{campaign.description}</p>
          </div>
          <div className="details-item details-span-2">
            <span className="meta-label">Target Audience</span>
            <p className="details-copy">{campaign.target_audience}</p>
          </div>
          <div className="details-item">
            <span className="meta-label">Platform</span>
            <span className="meta-value">{campaign.platform}</span>
          </div>
          <div className="details-item">
            <span className="meta-label">Objective</span>
            <span className="meta-value">{campaign.objective}</span>
          </div>
          <div className="details-item">
            <span className="meta-label">Tone</span>
            <span className="meta-value">{campaign.tone}</span>
          </div>
          <div className="details-item">
            <span className="meta-label">Budget</span>
            <span className="meta-value">{formatBudget(campaign.budget)}</span>
          </div>
          <div className="details-item details-span-2">
            <span className="meta-label">Keywords</span>
            <p className="details-copy">{campaign.keywords || 'None'}</p>
          </div>
          <div className="details-item">
            <span className="meta-label">Status</span>
            <span className="meta-value">{campaign.status}</span>
          </div>
          <div className="details-item">
            <span className="meta-label">Created Date</span>
            <span className="meta-value">{formatDate(campaign.created_at)}</span>
          </div>
          <div className="details-item">
            <span className="meta-label">Updated Date</span>
            <span className="meta-value">{formatDate(campaign.updated_at)}</span>
          </div>
        </div>
      </section>

      <section className="campaign-details-card creative-panel">
        <div className="section-header">
          <h2>AI Creative Studio</h2>
          <button type="button" className="btn-secondary" onClick={() => setCreativeModalOpen(true)}>
            Switch Type
          </button>
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
          />
        )}
      </section>

      <section className="campaign-intelligence">
        <div className="section-header">
          <h2>Saved Creatives</h2>
          <span className="section-tag">Campaign Assets</span>
        </div>
        <CreativeList
          creatives={savedCreatives}
          onOpenCreative={handleOpenCreative}
        />
      </section>

      <section className="campaign-intelligence" aria-label="Future campaign intelligence">
        <div className="section-header">
          <h2>Campaign Intelligence</h2>
          <span className="section-tag">Reserved for later modules</span>
        </div>
        <div className="intelligence-grid">
          <article className="intelligence-slot">
            <h3>Advertisements</h3>
            <p>AI-generated ads for this campaign will appear here in Module 4.</p>
          </article>
          <article className="intelligence-slot">
            <h3>Audience Analysis</h3>
            <p>Audience insights attached to this campaign will appear in a later module.</p>
          </article>
          <article className="intelligence-slot">
            <h3>Sentiment Analysis</h3>
            <p>Sentiment results will attach to this campaign without changing this layout.</p>
          </article>
          <article className="intelligence-slot">
            <h3>Performance Prediction</h3>
            <p>Forecasts and analytics will be added here once the campaign foundation is in use.</p>
          </article>
        </div>
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
