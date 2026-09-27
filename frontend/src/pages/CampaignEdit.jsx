import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { campaignService, getApiErrorMessage } from '../api/campaignService';
import { CampaignForm } from '../components/CampaignForm';
import { EMPTY_CAMPAIGN_FORM, campaignToFormValues } from '../constants/campaigns';

export const CampaignEdit = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [values, setValues] = useState(EMPTY_CAMPAIGN_FORM);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let isActive = true;

    const loadCampaign = async () => {
      setLoading(true);
      try {
        const campaign = await campaignService.getCampaign(id);
        if (isActive) {
          setValues(campaignToFormValues(campaign));
        }
      } catch (error) {
        if (isActive) {
          setErrorMessage(getApiErrorMessage(error, 'Unable to load this campaign for editing.'));
        }
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    loadCampaign();
    return () => {
      isActive = false;
    };
  }, [id]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setErrorMessage('');

    if (!values.name.trim() || !values.product_name.trim() || !values.description.trim() || !values.target_audience.trim()) {
      setErrorMessage('Please fill in all required campaign fields.');
      return;
    }

    if (values.budget !== '' && Number(values.budget) < 0) {
      setErrorMessage('Budget must be a valid non-negative number.');
      return;
    }

    setIsSubmitting(true);
    try {
      await campaignService.updateCampaign(id, values);
      navigate(`/campaigns/${id}`, {
        replace: true,
        state: { successMessage: 'Campaign updated successfully.' },
      });
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error, 'Unable to update campaign. Please check your input and try again.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="campaign-page">
        <div className="state-card">
          <div className="auth-spinner"></div>
          <p>Loading campaign...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="campaign-page">
      <div className="page-header">
        <div>
          <p className="page-kicker">Campaign Management</p>
          <h1>Edit Campaign</h1>
          <p className="page-subtitle">Refine the audience, objective, and direction for this campaign.</p>
        </div>
      </div>

      <div className="campaign-form-card">
        <CampaignForm
          values={values}
          onChange={setValues}
          onSubmit={handleSubmit}
          onCancel={() => navigate(`/campaigns/${id}`)}
          submitLabel="Save Changes"
          isSubmitting={isSubmitting}
          errorMessage={errorMessage}
          showStatus
        />
      </div>
    </div>
  );
};

export default CampaignEdit;
