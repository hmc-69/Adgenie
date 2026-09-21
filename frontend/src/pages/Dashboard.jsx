import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context';
import { healthAPI } from '../api/client';
import { campaignService, getApiErrorMessage } from '../api/campaignService';
import { CampaignTable } from '../components/CampaignTable';
import { ConfirmDialog } from '../components/ConfirmDialog';

export const Dashboard = () => {
  const { user } = useAuth();
  const location = useLocation();
  const [dbStatus, setDbStatus] = useState({ status: 'checking', message: 'Checking MySQL connection...' });
  const [apiStatus, setApiStatus] = useState({ status: 'checking', message: 'Checking API status...' });
  const [campaigns, setCampaigns] = useState([]);
  const [campaignsLoading, setCampaignsLoading] = useState(true);
  const [campaignsError, setCampaignsError] = useState('');
  const [successMessage, setSuccessMessage] = useState(location.state?.successMessage || '');
  const [campaignToDelete, setCampaignToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const checkSystemHealth = async () => {
      try {
        const apiRes = await healthAPI.checkBackend();
        setApiStatus({ status: 'online', message: apiRes.service || 'AdGenie Backend Online' });
      } catch {
        setApiStatus({ status: 'offline', message: 'Backend Disconnected' });
      }

      try {
        const dbRes = await healthAPI.checkDatabase();
        setDbStatus({ status: dbRes.status, message: `${dbRes.database} ${dbRes.message}` });
      } catch {
        setDbStatus({ status: 'error', message: 'Database unreachable' });
      }
    };

    checkSystemHealth();
  }, []);

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
    loadCampaigns();
  }, []);

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

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString(undefined, {
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

  return (
    <div className="dashboard-container">
      {/* Welcome Banner */}
      <section className="welcome-banner">
        <div className="welcome-content">
          <div className="welcome-badge">
            <span className="pulse-dot"></span>
            <span>Module 3 Active • Campaign Management</span>
          </div>
          <h1 className="welcome-title">
            Welcome, <span className="highlight-text">{user?.name || 'Marketer'}</span>
          </h1>
          <p className="welcome-desc">
            You are securely logged into your AdGenie AI-Powered Marketing Intelligence workspace.
          </p>
        </div>

        <div className="system-health-card">
          <h3 className="health-card-title">System & Security Status</h3>
          <div className="health-metrics">
            <div className="health-item">
              <span className={`status-indicator ${apiStatus.status === 'online' ? 'online' : 'offline'}`}></span>
              <div>
                <div className="health-label">FastAPI Backend</div>
                <div className="health-value">{apiStatus.message}</div>
              </div>
            </div>
            <div className="health-item">
              <span className={`status-indicator ${dbStatus.status === 'connected' ? 'online' : 'offline'}`}></span>
              <div>
                <div className="health-label">MySQL Database</div>
                <div className="health-value">{dbStatus.message}</div>
              </div>
            </div>
            <div className="health-item">
              <span className="status-indicator online"></span>
              <div>
                <div className="health-label">Auth Security</div>
                <div className="health-value">Argon2 Password Hash + JWT Session</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {successMessage && (
        <div className="alert alert-success" role="status">
          <span>{successMessage}</span>
        </div>
      )}

      <section className="dashboard-section" id="campaigns">
        <div className="section-header">
          <h2>Campaigns</h2>
          <Link to="/campaigns/new" className="btn-primary-sm">Create Campaign</Link>
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
          <div className="state-card">
            <h3>No campaigns yet</h3>
            <p>Create your first campaign to start building the foundation for AI ads, audience analysis, and performance insights.</p>
            <Link to="/campaigns/new" className="btn-primary-sm">Create Campaign</Link>
          </div>
        )}

        {!campaignsLoading && !campaignsError && campaigns.length > 0 && (
          <CampaignTable campaigns={campaigns} onDelete={setCampaignToDelete} />
        )}
      </section>

      {/* User Profile Card */}
      <section className="dashboard-section">
        <div className="section-header">
          <h2>User Account Details</h2>
          <span className="section-tag">Protected Endpoint (`/api/auth/me`)</span>
        </div>

        <div className="profile-grid">
          <div className="profile-card">
            <div className="profile-avatar-large">
              {user?.name ? user.name.charAt(0).toUpperCase() : 'U'}
            </div>
            <div className="profile-primary-info">
              <h3>{user?.name}</h3>
              <p>{user?.email}</p>
              <span className="role-pill">Verified Marketer</span>
            </div>
          </div>

          <div className="profile-meta-card">
            <div className="meta-row">
              <span className="meta-label">User ID</span>
              <span className="meta-value font-mono">#{user?.id}</span>
            </div>
            <div className="meta-row">
              <span className="meta-label">Primary Email</span>
              <span className="meta-value">{user?.email}</span>
            </div>
            <div className="meta-row">
              <span className="meta-label">Member Since</span>
              <span className="meta-value">{formatDate(user?.created_at)}</span>
            </div>
            <div className="meta-row">
              <span className="meta-label">Last Updated</span>
              <span className="meta-value">{formatDate(user?.updated_at)}</span>
            </div>
          </div>
        </div>
      </section>

      {/* Platform Features Grid */}
      <section className="dashboard-section">
        <div className="section-header">
          <h2>Marketing Intelligence Modules</h2>
          <span className="section-tag">AdGenie AI Platform</span>
        </div>

        <div className="modules-grid">
          <div className="module-card">
            <div className="module-icon icon-ai">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z"></path>
                <path d="M12 6v6l4 2"></path>
              </svg>
            </div>
            <h3>Campaign Optimization</h3>
            <p>Predictive budget allocation and performance forecasting driven by multi-channel AI modeling.</p>
            <span className="module-status active">Ready for Integration</span>
          </div>

          <div className="module-card">
            <div className="module-icon icon-audience">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                <circle cx="9" cy="7" r="4"></circle>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
              </svg>
            </div>
            <h3>Audience Intelligence</h3>
            <p>Cluster behavioral personas and hyper-target high-converting demographics across platforms.</p>
            <span className="module-status active">Ready for Integration</span>
          </div>

          <div className="module-card">
            <div className="module-icon icon-creative">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
              </svg>
            </div>
            <h3>AI Creative Engine</h3>
            <p>Automated copy generation, headline variants, and visual asset scoring for ad creatives.</p>
            <span className="module-status active">Ready for Integration</span>
          </div>

          <div className="module-card">
            <div className="module-icon icon-analytics">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="20" x2="18" y2="10"></line>
                <line x1="12" y1="20" x2="12" y2="4"></line>
                <line x1="6" y1="20" x2="6" y2="14"></line>
              </svg>
            </div>
            <h3>ROI & ROAS Forecasting</h3>
            <p>Real-time conversion attribution modeling and marketing return-on-ad-spend intelligence.</p>
            <span className="module-status active">Ready for Integration</span>
          </div>
        </div>
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
