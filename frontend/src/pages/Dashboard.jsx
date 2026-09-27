import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context';
import { campaignService, getApiErrorMessage } from '../api/campaignService';
import { creativeService } from '../api/creativeService';
import { CampaignTable } from '../components/CampaignTable';
import { ConfirmDialog } from '../components/ConfirmDialog';

export const Dashboard = () => {
  const { user } = useAuth();
  const location = useLocation();
  const [campaigns, setCampaigns] = useState([]);
  const [campaignsLoading, setCampaignsLoading] = useState(true);
  const [campaignsError, setCampaignsError] = useState('');
  const [creativeCount, setCreativeCount] = useState(null);
  const [successMessage, setSuccessMessage] = useState(location.state?.successMessage || '');
  const [campaignToDelete, setCampaignToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const loadCampaigns = async () => {
    setCampaignsLoading(true);
    setCampaignsError('');
    try {
      const data = await campaignService.getCampaigns();
      setCampaigns(data.campaigns || []);
    } catch (error) {
      setCampaignsError(getApiErrorMessage(error, 'Unable to load campaigns.'));
    } finally {
      setCampaignsLoading(false);
    }
  };

  useEffect(() => {
    let active = true;

    const fetchCampaigns = async () => {
      try {
        const data = await campaignService.getCampaigns();
        if (active) setCampaigns(data.campaigns || []);
      } catch (error) {
        if (active) setCampaignsError(getApiErrorMessage(error, 'Unable to load campaigns.'));
      } finally {
        if (active) setCampaignsLoading(false);
      }
    };

    fetchCampaigns();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let isActive = true;

    Promise.all(
      campaigns.map(async (campaign) => {
        try {
          const result = await creativeService.listCreatives(campaign.id);
          return result.total ?? result.creatives?.length ?? 0;
        } catch {
          return null;
        }
      }),
    ).then((counts) => {
      if (isActive) {
        setCreativeCount(counts.some((count) => count === null)
          ? null
          : counts.reduce((total, count) => total + count, 0));
      }
    });

    return () => {
      isActive = false;
    };
  }, [campaigns]);

  const handleConfirmDelete = async () => {
    if (!campaignToDelete) {
      return;
    }
    setIsDeleting(true);
    try {
      await campaignService.deleteCampaign(campaignToDelete.id);
      setSuccessMessage('Campaign deleted successfully.');
      setCampaignToDelete(null);
      await loadCampaigns();
    } catch (error) {
      setCampaignsError(getApiErrorMessage(error, 'Unable to delete this campaign.'));
      setCampaignToDelete(null);
    } finally {
      setIsDeleting(false);
    }
  };

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const activeCampaigns = campaigns.filter((campaign) => campaign.status?.toLowerCase() === 'active').length;

  return (
    <div className="dashboard-container">
      <section className="welcome-banner">
        <div className="welcome-content">
          <h1 className="welcome-title">
            {greeting}, <span className="highlight-text">{user?.name?.split(' ')[0] || 'there'}</span>
          </h1>
          <p className="welcome-desc">
            Create and manage intelligent advertising campaigns with AI-powered creative generation and marketing insights.
          </p>
        </div>
        <Link to="/campaigns/new" className="btn-primary dashboard-create-action"><span aria-hidden="true">+</span> Create Campaign</Link>
      </section>

      {successMessage && (
        <div className="alert alert-success" role="status">
          <span>{successMessage}</span>
        </div>
      )}

      <section className="dashboard-summary" aria-label="Campaign summary">
        <article className="summary-card">
          <span>Total campaigns</span>
          <strong>{campaignsLoading || campaignsError ? '—' : campaigns.length}</strong>
          <small>Across your workspace</small>
        </article>
        <article className="summary-card">
          <span>AI creatives</span>
          <strong>{creativeCount === null ? '—' : creativeCount}</strong>
          <small>Saved campaign assets</small>
        </article>
        <article className="summary-card summary-card-accent">
          <span>Active campaigns</span>
          <strong>{campaignsLoading || campaignsError ? '—' : activeCampaigns}</strong>
          <small>Currently in market</small>
        </article>
      </section>

      <section className="dashboard-section" id="campaigns">
        <div className="section-header">
          <div><p className="page-kicker">Workspace</p><h2>Your Campaigns</h2></div>
          <Link to="/campaigns/new" className="btn-secondary">+ Create Campaign</Link>
        </div>

        {campaignsLoading && (
          <div className="state-card">
            <div className="auth-spinner"></div>
            <p>Loading your campaigns...</p>
          </div>
        )}

        {!campaignsLoading && campaignsError && (
          <div className="state-card state-error">
            <h3>Could not load campaigns</h3>
            <p>{campaignsError}</p>
            <button type="button" className="btn-secondary" onClick={loadCampaigns}>Try again</button>
          </div>
        )}

        {!campaignsLoading && !campaignsError && campaigns.length === 0 && (
          <div className="state-card dashboard-empty-state">
            <h3>No campaigns yet</h3>
            <p>Create your first campaign to get started.</p>
            <Link to="/campaigns/new" className="btn-primary">Create Campaign</Link>
          </div>
        )}

        {!campaignsLoading && !campaignsError && campaigns.length > 0 && (
          <CampaignTable campaigns={campaigns} onDelete={setCampaignToDelete} />
        )}
      </section>

      <ConfirmDialog
        open={Boolean(campaignToDelete)}
        title="Delete campaign"
        message="Are you sure you want to delete this campaign?"
        confirmLabel="Delete Campaign"
        isBusy={isDeleting}
        onConfirm={handleConfirmDelete}
        onCancel={() => setCampaignToDelete(null)}
      />
    </div>
  );
};

export default Dashboard;
